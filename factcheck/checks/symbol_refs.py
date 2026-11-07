"""symbol-refs: a name given beside a path that the file does not contain.

`paths` confirms a backticked file exists. Docs also point at a place
inside it, a path followed by a parenthesised list of names:

    `tests/test_discover.py` (RedactTest)
    `src/polymorph/discover.py` (`_safe`, `_id_shaped`)

This check reads the named file and requires each name to occur in it as
a whole word (so `_safe` does not match inside `_safely`). A parenthesis
counts only when every item is a bare or backticked identifier, optionally
dotted (`Class.method`, each part checked) or ending `()`; `(see below)`
or `(old, removed in v2)` is prose and is left alone. An item ending in
a file extension (`[paths] exts`) names a file, not a symbol, so a
parenthesis holding one, `` `settings.json` (`reader.py`) ``, is skipped.

  - the file resolves (suffix match, as `paths`) and a name is absent from
    every candidate: a hard finding;
  - the file does not resolve, is untracked or is not text: skipped, since
    `paths` owns a missing file.

Opt-in, because a repo that keeps historical names beside paths gets
steady noise:

    [symbol-refs]
    enable = true

A line carrying `<!-- symbol-ok: reason -->` is skipped, for a name kept
on purpose. Fenced code is skipped. Needs git: only tracked files count.
"""
import re

from ..findings import Finding
from ..gitfiles import NotAGitCheckout, tracked_files
from ..mdcore import fences
from ..registry import check
from .paths import DEFAULT_EXTS, normalize

SYMBOL_OK = re.compile(r'<!--\s*symbol-ok:[^>]*-->')
MENTION = re.compile(
    r'`([\w./-]+\.\w+)(?::\d+(?:-\d+)?)?`\s*\(([^()]*)\)')
NAME = re.compile(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?:\(\))?')
SEE = ("a name beside a path that the file does not contain: a rename or "
       "removal the doc missed, or a deliberate historical name (mark it "
       "<!-- symbol-ok: reason -->)")


def names_in(parenthesised, exts=DEFAULT_EXTS):
    """The identifiers in `a, `b`, C.d()`, or None when any item is not
    one (the parenthesis is prose, not a name list) or is a file name
    (it ends in one of `exts`)."""
    out = []
    for item in parenthesised.split(','):
        item = item.strip().strip('`').strip()
        if not NAME.fullmatch(item) or item.endswith(tuple(exts)):
            return None
        out.extend(p for p in item.removesuffix('()').split('.'))
    return out or None


def candidates(token, tracked):
    name = normalize(token)
    return [t for t in tracked if t == name or t.endswith('/' + name)]


def occurs(name, text):
    return re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text)


@check('symbol-refs', order=96)
def check_symbol_refs(root, cfg):
    if not cfg.section('symbol-refs').get('enable'):
        return []
    try:
        tracked = tracked_files(root)
    except NotAGitCheckout:
        return [Finding('SYMBOL-REFS NEEDS GIT', str(root),
                        "not a git checkout: `symbol-refs` reads "
                        "git-tracked files", review=True)]
    texts = {}

    def read(rel):
        if rel not in texts:
            try:
                texts[rel] = (root / rel).read_text()
            except (OSError, UnicodeDecodeError):
                texts[rel] = None
        return texts[rel]

    exts = cfg.section('paths').get('exts', DEFAULT_EXTS)
    findings = []
    for path in cfg.scope('docs'):
        rel = path.relative_to(root).as_posix()
        for n, line, kind in fences.scan_lines(path.read_text()):
            if kind != fences.TEXT or SYMBOL_OK.search(line):
                continue
            for m in MENTION.finditer(line):
                names = names_in(m.group(2), exts)
                if names is None:
                    continue
                bodies = [t for t in (read(c) for c in
                                      candidates(m.group(1), tracked))
                          if t is not None]
                if not bodies:
                    continue
                for name in names:
                    if not any(occurs(name, b) for b in bodies):
                        findings.append(Finding(
                            'MISSING SYMBOL', f'{rel}:{n}',
                            f"`{name}` does not occur in `{m.group(1)}`",
                            see=SEE))
    return findings
