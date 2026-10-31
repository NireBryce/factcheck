"""paths: backticked file mentions in the docs that name no tracked file.

`links` covers the reliable half of "a doc names a file that isn't
there": a markdown link target either resolves or it doesn't. This check
covers the other half, a filename written in backticks with no link
(`hosts.nix`, `scripts/check`), which is common in prose and genuinely
ambiguous to judge mechanically:

  - historical names are often kept on purpose, to explain a rename or a
    removal, and will never resolve;
  - docs shorten paths, so a mention matches any tracked path that *ends*
    with it (`checks/links.py` matches `factcheck/checks/links.py`);
    leading `./` and `../` segments are dropped first;
  - some spans aren't this repo's files at all (another project's tree, an
    `owner/repo.sh`-shaped name), and examples name files never meant to
    exist.

So every finding is REVIEW: a candidate for a human, never a failure.
Opt-in, because a repo whose docs keep historical names gets steady noise:

    [paths]
    enable = true
    exts = [".py", ".md", ...]        # which backticked names count as files
    ignore = ["^nixpkgs/", "example"] # regexes; a matching mention is skipped

Fenced code is skipped (sample output and tree listings name files
freely). A line carrying `<!-- path-ok: reason -->` is skipped. Matching
is case-sensitive, as git's paths are. Needs git: only tracked files
count, since a clone never sees an untracked one; outside a git checkout
the check reports that once instead of running.

Generalized from the wiki_stale_refs.py script of the repo factcheck was
extracted from.
"""
import re
import subprocess

from ..findings import Finding
from ..gitfiles import NotAGitCheckout, tracked_files
from ..mdcore import fences
from ..registry import check

DEFAULT_EXTS = ['.nix', '.py', '.sh', '.md', '.yaml', '.yml', '.json',
                '.toml']
PATH_OK = re.compile(r'<!--\s*path-ok:[^>]*-->')
SEE = ("a backticked name that resolves to no tracked file: a stale "
       "reference after a rename, or a deliberate historical name "
       "(mark it <!-- path-ok: reason -->)")


def mention_rx(exts):
    return re.compile(
        r'`([\w./-]+(?:' + '|'.join(re.escape(e) for e in exts) + r'))`')


def normalize(token):
    """`../flake/doc/foo.md` -> `flake/doc/foo.md`: a path written relative
    to a nested page still suffix-matches the repo-relative tracked one.
    Only *leading* `.`/`..` segments go (and a leading `/`, read as
    repo-rooted); one in the middle is kept, so it can't resolve."""
    parts = token.split('/')
    while parts and parts[0] in ('.', '..', ''):
        parts.pop(0)
    return '/'.join(parts)


def resolves(token, tracked, suffixes):
    name = normalize(token)
    return name in tracked or ('/' + name) in suffixes


def all_suffixes(tracked):
    """Every `/tail` of every tracked path, so a lookup is a set probe
    rather than a scan of the whole tree per mention."""
    out = set()
    for t in tracked:
        parts = t.split('/')
        for i in range(1, len(parts)):
            out.add('/' + '/'.join(parts[i:]))
    return out


@check('paths', order=95)
def check_paths(root, cfg):
    s = cfg.section('paths')
    if not s.get('enable'):
        return []
    rx = mention_rx(s.get('exts', DEFAULT_EXTS))
    ignore = [re.compile(p) for p in s.get('ignore', [])]
    try:
        tracked = set(tracked_files(root))
    except NotAGitCheckout:
        return [Finding('PATHS NEEDS GIT', str(root),
                        "not a git checkout: `paths` reads git-tracked files",
                        review=True)]
    suffixes = all_suffixes(tracked)
    findings = []
    for path in cfg.scope('docs'):
        rel = path.relative_to(root).as_posix()
        for n, line, kind in fences.scan_lines(path.read_text()):
            if kind != fences.TEXT or PATH_OK.search(line):
                continue
            for m in rx.finditer(line):
                tok = m.group(1)
                if any(r.search(tok) for r in ignore):
                    continue
                if not resolves(tok, tracked, suffixes):
                    findings.append(Finding(
                        'STALE PATH', f'{rel}:{n}',
                        f"`{tok}` names no tracked file", review=True,
                        see=SEE))
    return findings
