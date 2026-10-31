"""drift: which docs have the most code change under what they cite.

Answers "where should an accuracy audit start", and nothing more: for
each doc in the docs scope, take its date (the `dates` check's
last-modified line, looked for in the first six lines; else, or when it
isn't a real date, the file's last commit date), collect the repo
paths it cites (backticked tokens and markdown-link targets that resolve
to tracked files or directories), and count the commits that touched
those paths strictly after that date. Markdown files are not counted as
changes, because a doc citing a doc is not drift in the code it describes.
A cited directory shallower than `min-dir-depth` components is skipped
as too broad ("everything changed"), and a short name matching more than
one tracked path is skipped as ambiguous.

Every finding is REVIEW: a commit under a cited path doesn't mean the
doc is wrong, only that it is where reading should start. The top `top`
docs with at least `min-commits` are reported, most first. Opt-in:

    [drift]
    enable = true
    top = 10             # how many docs to report
    min-commits = 1      # below this, a doc isn't reported
    min-dir-depth = 3    # cited directories shallower than this are ignored

Needs git with full history: outside a checkout, or in a shallow clone
(CI's default checkout), it reports that once instead of a silent or
truncated count. One `git log --name-only` pass for the whole repo. A
commit on the doc's own date isn't counted, since dates have no time.

Generalized from the doc_drift.py and docscope.py helpers of the repo
factcheck was extracted from, where it ranked the docs for a whole-repo
accuracy audit.
"""
import re
import subprocess
from collections import defaultdict

from ..findings import Finding
from ..registry import check
from . import dates

BACKTICK = re.compile(r"`([^`\n]+)`")
MDLINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")
EXTS = (".nix", ".py", ".sh", ".md", ".yaml", ".yml", ".json", ".toml",
        ".just", ".justfile", ".js", ".ts", ".rs", ".go", ".rb")
SEE = ("commits under the paths a doc cites since its date: read the doc "
       "against them first in an accuracy pass; not a claim it is wrong")


def _git(root, *args):
    # quotepath off: a non-ASCII path would otherwise come back as an
    # octal escape that matches no cited token.
    p = subprocess.run(["git", "-C", str(root), "-c", "core.fsmonitor=false",
                        "-c", "core.quotepath=off", *args],
                       capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def normalize(token):
    return "/".join(p for p in token.split("/") if p not in (".", "..", ""))


class Index:
    """Tracked files and directories, for resolving a cited token."""

    def __init__(self, root):
        self.files = set(_git(root, "ls-files").splitlines())
        self.dirs = {"/".join(f.split("/")[:i]) for f in self.files
                     for i in range(1, f.count("/") + 1)}
        self.all = self.files | self.dirs
        self.by_name = {}
        for p in self.all:
            parts = p.split("/")
            for i in range(len(parts)):
                self.by_name.setdefault("/".join(parts[i:]), []).append(p)

    def resolve(self, token):
        """The repo path a cited token names, or None (unknown, ambiguous,
        or a bare word)."""
        t = normalize(token.strip().rstrip("/"))
        t = re.sub(r":\d+(-\d+)?$", "", t)
        if not t or any(c in t for c in " *<>{}$|()=") \
                or t.startswith(("http", "~")):
            return None
        if "/" not in t and not t.endswith(EXTS):
            return None
        if t in self.all:
            return t
        hits = self.by_name.get(t, [])
        return hits[0] if len(hits) == 1 else None


def cited(text, index):
    out = set()
    for rx in (BACKTICK, MDLINK):
        for m in rx.finditer(text):
            p = index.resolve(m.group(1))
            if p:
                out.add(p)
    return out


def change_log(root):
    """{path: {(date, sha)}} for every non-markdown file ever touched."""
    # A NUL marks a commit line: no path can start with one, unlike the
    # `@` that a tracked `@scope/pkg/` path would be mistaken for.
    out = _git(root, "log", "--format=%x00%H %cs", "--name-only",
               "--no-renames")
    hist = defaultdict(set)
    sha = date = None
    for line in out.splitlines():
        if line.startswith("\0"):
            sha, date = line[1:].split()
        elif line and sha and not line.endswith(".md"):
            hist[line].add((date, sha))
    return hist


def rank(root, cfg):
    s = cfg.section('drift')
    min_depth = s.get('min-dir-depth', 3)
    index = Index(root)
    hist = change_log(root)
    by_dir = defaultdict(list)
    for f in hist:
        parts = f.split("/")
        for i in range(1, len(parts)):
            by_dir["/".join(parts[:i])].append(f)
    date_rx = dates.line_regex(cfg)

    rows = []
    for path in cfg.scope('docs'):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(errors="replace")
        try:
            d = dates.last_modified(text, date_rx)
        except ValueError:   # a date-shaped line that isn't a real date
            d = None
        date = d.isoformat() if d else _git(
            root, "log", "-1", "--format=%cs", "--", rel).strip()
        if not date:
            continue
        paths = {p for p in cited(text, index)
                 if p != rel and not p.endswith(".md")
                 and (p in index.files or p.count("/") + 1 >= min_depth)}
        per = {}
        for p in paths:
            keys = by_dir[p] if p in index.dirs else [p]
            per[p] = {sha for k in keys for dd, sha in hist.get(k, ())
                      if dd > date}
        allc = set().union(*per.values()) if per else set()
        top = sorted(per, key=lambda p: (-len(per[p]), p))[:3]
        rows.append(dict(doc=rel, date=date, cited=len(paths),
                         commits=len(allc),
                         top=[(p, len(per[p])) for p in top if per[p]]))
    rows.sort(key=lambda r: (-r["commits"], -r["cited"], r["doc"]))
    return rows


@check('drift', order=160)
def check_drift(root, cfg):
    s = cfg.section('drift')
    if not s.get('enable'):
        return []
    # Silence here would read as "nothing drifted": say why instead.
    shallow = _git(root, "rev-parse", "--is-shallow-repository").strip()
    if shallow not in ("true", "false"):
        return [Finding('DRIFT NEEDS GIT', str(root),
                        "not a git checkout: `drift` reads commit history",
                        review=True)]
    if shallow == "true":
        return [Finding('DRIFT NEEDS HISTORY', str(root),
                        "shallow clone: commit counts would be truncated "
                        "(fetch full history, e.g. actions/checkout with "
                        "fetch-depth: 0)", review=True)]
    top, floor = s.get('top', 10), s.get('min-commits', 1)
    findings = []
    for r in [r for r in rank(root, cfg) if r["commits"] >= floor][:top]:
        paths = ", ".join(f"{p} ({n})" for p, n in r["top"])
        findings.append(Finding(
            'DRIFT', r["doc"],
            f"{r['commits']} commit(s) since {r['date']} under the paths it "
            f"cites; most: {paths}", review=True, see=SEE))
    return findings
