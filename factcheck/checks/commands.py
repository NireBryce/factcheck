"""commands: a doc's mention of a program's own subcommand names a real
path in its command tree -- `recipes`, for a CLI.

Moving `validate` under `manage` leaves every prose mention of `PROG
validate` naming words that exist, just not where the prose put them. This
check resolves each mention against a tree read from a static source; it
never runs the program.

    [commands]
    prog = "polymorph"                      # required to enable
    tree = { file = "docs/usage.md", pattern = '^## `polymorph (.+)`' }
    # or: tree = { plugin = "polymorph" }   # see register_tree below
    table-headings = ["Commands"]           # optional, see below

The tree is every command path the source yields: for `file`, group 1 of
`pattern` on each line, reduced to its leading lowercase words (a `<arg>`
or `--flag` ends the path); for `plugin`, the paths a function registered
with `register_tree(name)` returns for `(root, cfg)`, each a string
(`"manage validate"`) or a tuple of words. Every prefix of a path is a
command too, so `manage` needs no line of its own. A source that yields
no commands is a finding: a tree that cannot answer would pass everything.

Two mention shapes are read, outside fenced code:

  - a backtick span starting with the program name, `` `polymorph manage
    validate ./dir` ``: the words after it, up to the first token that is
    not a lowercase word, are walked down the tree. At a command that has
    subcommands the next word must be one of them; at a command with none
    the rest are arguments and are not judged.
  - under a heading listed in `table-headings`, the first backtick span of
    each table row's first cell, with or without the program name in
    front, resolved the same way. The section runs to the next heading of
    the same or a higher level.

A word that is no subcommand where it stands is a hard finding; when that
word is a subcommand somewhere else in the tree it is a REVIEW naming
where, since a moved command is the likely cause and a human decides. A
line carrying `<!-- command-ok: reason -->` is skipped.
"""
import re

from ..findings import Finding
from ..mdcore import fences
from ..mdcore.headings import HEADING
from ..registry import check

WORD = re.compile(r'[a-z][\w-]*')
COMMAND_OK = re.compile(r'<!--\s*command-ok:[^>]*-->')
SEE = ("a command that moved or was renamed: fix the doc, or the tree "
       "source if the command is real (mark a deliberate mention "
       "<!-- command-ok: reason -->)")

# name -> fn(root, cfg) -> iterable of command paths, from plugins.
TREES = {}


def register_tree(name):
    """Decorator registering `fn(root, cfg)` as command-tree source `name`;
    it returns paths as `"a b"` strings or tuples of words."""
    def register(fn):
        TREES[name] = fn
        return fn
    return register


def leading_words(text):
    """The leading run of lowercase subcommand-shaped tokens of `text`."""
    out = []
    for tok in text.split():
        if not WORD.fullmatch(tok):
            break
        out.append(tok)
    return tuple(out)


def tree_paths(root, cfg):
    """The set of command paths the configured source yields (empty set
    when there is no source)."""
    src = cfg.section('commands').get('tree')
    raw = []
    if isinstance(src, dict) and 'file' in src:
        rx = re.compile(src['pattern'])
        path = root / src['file']
        if path.is_file():
            for line in path.read_text().splitlines():
                m = rx.search(line)
                if m:
                    raw.append(m.group(1))
    elif isinstance(src, dict) and src.get('plugin') in TREES:
        raw = TREES[src['plugin']](root, cfg)
    paths = set()
    for p in raw:
        words = leading_words(p) if isinstance(p, str) else tuple(p)
        if words:
            paths.add(words)
    return paths


def children(paths):
    """{command prefix: the subcommands directly under it}."""
    kids = {}
    for p in paths:
        for i, word in enumerate(p):
            kids.setdefault(p[:i], set()).add(word)
    return kids


def walk(words, kids):
    """None when `words` resolve; else (the command reached, the word that
    is no subcommand of it)."""
    node = ()
    for w in words:
        under = kids.get(node)
        if not under:
            return None            # a command with no subcommands: args
        if w not in under:
            return node, w
        node += (w,)
    return None


def elsewhere(word, paths):
    """Command paths that carry `word` as a segment, those ending in it
    first."""
    hits = sorted(p for p in paths if word in p)
    return sorted(hits, key=lambda p: p[-1] != word)


def judge(words, prog, paths, kids, where):
    bad = walk(words, kids)
    if bad is None:
        return None
    node, w = bad
    here = ' '.join((prog, *node))
    moved = elsewhere(w, paths)
    if moved:
        shown = ', '.join(f'`{prog} {" ".join(p)}`' for p in moved[:3])
        return Finding('UNKNOWN COMMAND', where,
                       f"'{w}' is not a subcommand of `{here}`, but "
                       f"exists as {shown}", review=True, see=SEE)
    return Finding('UNKNOWN COMMAND', where,
                   f"'{w}' is not a subcommand of `{here}`", see=SEE)


@check('commands', order=35)
def check_commands(root, cfg):
    s = cfg.section('commands')
    prog = s.get('prog')
    if not prog:
        return []
    paths = tree_paths(root, cfg)
    if not paths:
        return [Finding('COMMANDS TREE', 'factcheck config',
                        "[commands] tree yields no commands, so nothing "
                        "can be checked")]
    kids = children(paths)
    headings = set(s.get('table-headings', []))
    mention = re.compile(r'`' + re.escape(prog) + r'((?: [^`]*)?)`')
    findings = []
    for path in cfg.scope('docs'):
        rel = path.relative_to(root).as_posix()
        section_level = None            # level of the open table heading
        for n, line, kind in fences.scan_lines(path.read_text()):
            if kind != fences.TEXT:
                continue
            h = HEADING.match(line)
            if h:
                level = len(h.group(1))
                if section_level is not None and level <= section_level:
                    section_level = None
                if h.group(2).strip('` ') in headings:
                    section_level = level
            if COMMAND_OK.search(line):
                continue
            where = f'{rel}:{n}'
            for m in mention.finditer(line):
                f = judge(leading_words(m.group(1)), prog, paths, kids,
                          where)
                if f:
                    findings.append(f)
            if section_level is not None and line.lstrip().startswith('|'):
                cell = line.strip().strip('|').split('|')[0]
                span = re.search(r'`([^`]+)`', cell)
                if span:
                    text = span.group(1)
                    if text == prog or text.startswith(prog + ' '):
                        continue    # an inline mention, judged above
                    f = judge(leading_words(text), prog, paths, kids, where)
                    if f:
                        findings.append(f)
    return findings
