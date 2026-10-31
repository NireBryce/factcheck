"""fix-refs: rewrite references to files and directories you just moved
with `git mv`. A fixer, not a check: it writes files, never joins `check`.

  factcheck fix-refs apply   [OLD=NEW ...]
  factcheck fix-refs dry-run [OLD=NEW ...]

Run it after the moves, with the renames staged. It reads the renames from
`git diff --cached -M HEAD`, adds any `OLD=NEW` pairs (repo-relative
paths, for a move git did not detect), and rewrites, in every tracked text
file:

  markdown links    `[t](path)`, `[t](<path>)`, `[ref]: path`. The target is
                    resolved against the file's OLD location, mapped, and
                    re-relativised from its NEW one, so a link in a file that
                    moved is fixed even when its target stayed put (and the
                    reverse). Fragments are kept; links to anything that did
                    not exist at HEAD, and URLs, are left alone. Visible text
                    that was the old target (`[../a.md](../a.md)`) follows it.
  bare paths        a moved repo-relative path written out in prose, code or
                    a script (`docs/hosts.md`, `$root/docs/scripts/x.py`,
                    `../../docs/x.md`). Not matched when preceded by another
                    path segment, so `site/docs/x.md` is not `docs/x.md`.
                    Directories are inferred: a directory whose every file
                    moved to one common new location maps as a whole.

It does NOT rewrite paths a program builds from pieces. Those print as
`REVIEW` lines, because they are where a move quietly breaks things after
every link checker is green:

  - a quoted segment of a moved directory or file next to a path join
    (`root / 'docs' / 'categories'`, `os.path.join(x, "scripts")`)
  - in a moved script, anything that finds the repo root by counting
    directories up (`parents[2]`, `dirname`, `BASH_SOURCE`, `..`): the script
    is now at a different depth

Rerunning is not safe if a NEW path is also some other move's OLD path (a
swap or a chain): the second pass would map it again. Run once, and review
the diff (`dry-run` lists what would change and writes nothing).

Config (`[fix-refs]`): `exclude = ["vendor/**", ...]`, fnmatch globs of
tracked files never rewritten.

Adapted from the move_refs.py helper of the repo factcheck was extracted
from, written for a reorganisation that rewrote about 165 files.
"""
import fnmatch
import os
import pathlib
import posixpath
import re
import subprocess

from ..fixers import fixer

USAGE = "usage: factcheck fix-refs apply|dry-run [OLD=NEW ...]\n"


def git(root, *args):
    # quotepath off: otherwise git prints a non-ASCII path as a quoted
    # octal escape, which then matches nothing and is silently skipped.
    return subprocess.run(["git", "-C", root, "-c", "core.quotepath=off",
                           *args], check=True,
                          capture_output=True, text=True).stdout


def staged_renames(root):
    ren = {}
    for line in git(root, "diff", "--cached", "-M", "--name-status", "HEAD").splitlines():
        parts = line.split("\t")
        if parts[0].startswith("R"):
            ren[parts[1]] = parts[2]
    return ren


def infer_dirs(ren, old_files):
    """Directory moves: old dir -> new dir where EVERY file under the old dir
    at HEAD was renamed to the same relative place under the new dir."""
    cands = set()
    for old, new in ren.items():
        o, n = posixpath.dirname(old), posixpath.dirname(new)
        while o and n:
            cands.add((o, n))
            o, n = posixpath.dirname(o), posixpath.dirname(n)
    dirs = {}
    for o, n in cands:
        under = [f for f in old_files if f.startswith(o + "/")]
        if under and all(ren.get(f) == n + f[len(o):] for f in under):
            dirs[o] = n
    # keep only outermost: a dir inside an already-mapped dir adds nothing
    return {o: n for o, n in dirs.items()
            if not any(o != p and o.startswith(p + "/") for p in dirs)}


class Mapper:
    def __init__(self, ren, dirs):
        self.ren, self.dirs = ren, dirs

    def new(self, path):
        if path in self.ren:
            return self.ren[path]
        for o, n in self.dirs.items():
            if path == o or path.startswith(o + "/"):
                return n + path[len(o):]
        return path


LINK = re.compile(r"(\]\()(<[^>\n]+>|[^)\s]+)(\))")
REFDEF = re.compile(r"^(\[[^\]\n]+\]:\s*)(<[^>\n]+>|\S+)", re.M)
SKIP_TARGET = re.compile(r"^(?:[a-z][a-z0-9+.\-]*:|#|/)", re.I)


def fix_target(raw, old_dir, new_dir, old_exists, mapper):
    angle = raw.startswith("<")
    tgt = raw[1:-1] if angle else raw
    if SKIP_TARGET.match(tgt):
        return raw
    path, sep, frag = tgt.partition("#")
    if not path:
        return raw
    old = posixpath.normpath(posixpath.join(old_dir, path))
    if not old_exists(old):
        return raw
    rel = posixpath.relpath(mapper.new(old), new_dir or ".")
    if path.endswith("/"):
        rel += "/"
    out = rel + sep + frag
    return f"<{out}>" if angle else out


def fix_links(text, old_dir, new_dir, old_exists, mapper):
    """Rewrite link targets; returns (text, {old_target: new_target})."""
    changed = {}

    def one(raw):
        new = fix_target(raw, old_dir, new_dir, old_exists, mapper)
        if new != raw:
            changed[raw.strip("<>").partition("#")[0]] = new.strip("<>").partition("#")[0]
        return new
    text = LINK.sub(lambda m: m.group(1) + one(m.group(2)) + m.group(3), text)
    text = REFDEF.sub(lambda m: m.group(1) + one(m.group(2)), text)
    return text, changed


def fix_visible(text, changed):
    """`[old](new)` -> `[new](new)` where the visible text was the old target."""
    if not changed:
        return text

    def sub(m):
        tick, vis, tgt, frag = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        if changed.get(vis) == tgt.strip("<>"):
            return f"[{tick}{tgt.strip('<>')}{tick}]({m.group(3)}{frag})"
        return m.group(0)
    return re.sub(r"\[(`?)([^\]\s`]+)\1\]\((<?[^)\s#>]+>?)(#[^)\s]*)?\)", sub, text)


def bare_regex(keys):
    alts = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    # Either a recognised prefix (`$root/`, `${root}/`, `../`, `./`) or the
    # start of a path: not preceded by a path character.
    return re.compile(
        r"(?:(?P<pre>\$\{\w+\}/|\$\w+/|(?:\.\./)+|\./)|(?<![\w.\-/]))"
        r"(?P<path>" + alts + r")(?![\w\-]|\.\w)")


def fix_bare(text, rx, mapper):
    if not rx:
        return text
    return rx.sub(lambda m: (m.group("pre") or "") + mapper.new(m.group("path")), text)


def segment_review(text, name, segments):
    """Lines that build a moved path from quoted pieces."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for seg in segments:
            if re.search(rf"""(?:/|join\(|,)\s*['"]{re.escape(seg)}['"]""", line) or \
               re.search(rf"""['"]{re.escape(seg)}['"]\s*(?:/|,)""", line):
                out.append(f"REVIEW {name}:{i}: builds a moved path from '{seg}': {line.strip()[:110]}")
                break
    return out


DEPTH = re.compile(r"parents\[\d+\]|\.parent\.parent|os\.path\.dirname|dirname\b|BASH_SOURCE|\$0\b|__file__|\.\./")


@fixer('fix-refs', usage=USAGE)
def fix_refs(root, cfg, args):
    """Returns 0 on success, 2 on a usage error or when there is nothing to
    map (no staged renames and no OLD=NEW): a silent success there would
    read as "nothing referenced the moved files"."""
    mode, pairs = args[0], args[1:]
    if mode not in ('apply', 'dry-run'):
        print(USAGE, end='')
        return 2
    dry_run = mode == 'dry-run'
    exclude = cfg.section('fix-refs').get('exclude', [])
    try:
        # The repo's top level, not the cwd: from a subdirectory, git
        # would list paths relative to it.
        root = git(str(root), "rev-parse", "--show-toplevel").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"fix-refs: {root} is not inside a git repository")
        return 2
    if subprocess.run(["git", "-C", root, "rev-parse", "--verify", "-q",
                       "HEAD"], capture_output=True).returncode != 0:
        print("fix-refs: needs at least one commit (renames are read "
              "against HEAD)")
        return 2
    try:
        return _fix_refs(root, exclude, pairs, dry_run)
    except subprocess.CalledProcessError as e:
        print(f"fix-refs: git failed: {(e.stderr or '').strip()}")
        return 2


def _fix_refs(root, exclude, pairs, dry_run):
    ren = staged_renames(root)
    for pair in pairs:
        o, _, n = pair.partition("=")
        if not n:
            print(f"fix-refs: OLD=NEW wanted, got {pair!r}")
            return 2
        ren[o] = n
    if not ren:
        print("fix-refs: no staged renames (git mv first) and no OLD=NEW")
        return 2

    old_files = set(git(root, "ls-tree", "-r", "HEAD", "--name-only").splitlines())
    old_dirs = set()
    for f in old_files:
        d = posixpath.dirname(f)
        while d:
            old_dirs.add(d)
            d = posixpath.dirname(d)
    dirs = infer_dirs(ren, old_files)
    mapper = Mapper(ren, dirs)
    rev = {v: k for k, v in ren.items()}
    keys = set(ren) | set(dirs)
    rx = bare_regex(keys) if keys else None

    moved_segments = {posixpath.basename(k) for k in keys if len(posixpath.basename(k)) >= 4
                      and not posixpath.basename(k).endswith((".md", ".py", ".sh", ".nix"))}
    changed_files, review = [], []
    for f in git(root, "ls-files").splitlines():
        if any(fnmatch.fnmatch(f, g) for g in exclude):
            continue
        full = os.path.join(root, f)
        if os.path.islink(full) or not os.path.isfile(full):
            continue
        try:
            text = pathlib.Path(full).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        old_f = rev.get(f, f)
        out, changed = fix_links(text, posixpath.dirname(old_f), posixpath.dirname(f),
                                 lambda p: p in old_files or p in old_dirs, mapper)
        out = fix_visible(out, changed)
        out = fix_bare(out, rx, mapper)
        if out != text:
            changed_files.append(f)
            if not dry_run:
                pathlib.Path(full).write_text(out, encoding="utf-8")
        scan = out
        if f.endswith((".py", ".sh", ".bash", ".just", ".justfile", ".nix")):
            review += segment_review(scan, f, moved_segments)
        if f in rev and f.endswith((".py", ".sh", ".bash")):
            for i, line in enumerate(scan.splitlines(), 1):
                if DEPTH.search(line):
                    review.append(f"REVIEW {f}:{i}: moved script, depth-sensitive? {line.strip()[:110]}")

    verb = "would rewrite" if dry_run else "rewrote"
    print(f"fix-refs: {verb} {len(changed_files)} file(s); "
          f"{len(ren)} renamed path(s), {len(dirs)} whole-directory move(s)")
    if dry_run:
        for f in changed_files:
            print(f"  {f}")
    for line in review:
        print(line)
    if review:
        print(f"fix-refs: {len(review)} line(s) above build paths in code; "
              f"the link check cannot see these, read each.")
    return 0
