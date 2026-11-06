"""lessons-index: a numbered lessons-learned index stays whole.

The shape it checks is an index page with one entry per lesson,

    - **§N** [title](<dir>/N-slug.md) — the rule. Home: ... Enforced: ...

where each entry links its own article in a directory of `<N>-<slug>.md`
files, and carries the fields that say where the rule lives and what
enforces it. Numbers are stable and cited from elsewhere, so a gap is a
finding: every number from 1 to the highest one used has both an entry
and an article. A field's *contents* are left to the checks that already
read links and skill or recipe names; this one only guarantees that each
field exists, so an entry can't land without saying where its rule lives.

Opt-in: a repo without `[lessons] page` gets a vacuous pass, because the
shape is a convention, not a default every repo follows.

A repo may instead keep its lessons as one table (`shape = "table"`), one
row per lesson:

    | Lesson | Rule | Home |
    |---|---|---|
    | ... | test a checker against a case it should catch | AGENTS.md; skill `ship` |

Every row must have a non-empty Home, and every skill (`skill `x``) and
repo path (`` `src/x.py` ``) the Home names must resolve, by the same
lookups as `skills` and `paths`. Those are hard findings, because a Home
is where the rule is supposed to live. On top of that, a REVIEW when the
Home's files share none of the rule's distinctive terms (words of six or
more letters, compared on their first six letters, minus a stopword
list): the Home exists but may never have been given the rule. A lead for
a human, not a claim; a rule with fewer than two distinctive terms is not
judged. A name given beside a path in a Home is left to `symbol-refs`.

Config (`[lessons]`):

    [lessons]
    page = "docs/lessons-learned.md"           # required to enable
    dir = "docs/lessons-learned"               # default: page minus .md
    exempt = ["NOTES.md"]                      # files in dir that aren't lessons;
                                               # default: none -- the source repo's
                                               # 0-human-README.md went back to its
                                               # own config (#20)
    fields = ["Home", "Enforced"]              # each entry must carry `<f>: `
    marker = "§"                               # the number's prefix
    shape = "index"                            # or "table" (see above)
    columns = ["Lesson", "Rule", "Home"]       # table shape: the header cells
    rule-column = "Rule"                       # table shape: which columns
    home-column = "Home"                       #   hold the rule and its Home
    min-overlap = 1                            # table shape: REVIEW below this
                                               #   many shared terms

Generalized from the index half of the lessons check in the repo
factcheck was extracted from; that repo keeps the other half (its
lessons-map file) as its own plugin, registered as `lessons`.
"""
import posixpath
import re

from ..findings import Finding
from ..gitfiles import NotAGitCheckout, tracked_files
from ..mdcore import fences
from ..registry import check
from .paths import DEFAULT_EXTS, all_suffixes, mention_rx, resolves
from .skills import SKILL_MENTION, skill_dirs

ARTICLE = re.compile(r'^(\d+)-[a-z0-9-]+\.md$')
# The entry separator: an em dash, or `--` where the page avoids one.
SEPARATOR = r'(?:—|--)'


def entry_rx(marker):
    return re.compile(
        r'^- \*\*' + re.escape(marker) + r'(\d+)\*\* \[[^\]]+\]\(([^)\s]+)\) '
        + SEPARATOR + r' .+$')


@check('lessons-index', order=150)
def check_lessons_index(root, cfg):
    s = cfg.section('lessons')
    page_rel = s.get('page')
    if not page_rel:
        return []
    dir_rel = s.get('dir', page_rel[:-3] if page_rel.endswith('.md')
                    else page_rel).rstrip('/')
    exempt = set(s.get('exempt', ()))
    fields = s.get('fields', ['Home', 'Enforced'])
    marker = s.get('marker', '§')
    page = root / page_rel
    art_dir = root / dir_rel
    shape = s.get('shape', 'index')
    if shape not in ('index', 'table'):
        return [Finding('LESSONS SHAPE', page_rel,
                        f'[lessons] shape is "{shape}", not "index" or '
                        '"table"')]
    if not page.is_file():
        return [Finding('MISSING LESSONS PAGE', page_rel,
                        '[lessons] page names no file')]
    if shape == 'table':
        return table_findings(root, cfg, page_rel)
    # Links on the page are relative to it, so an entry's link starts with
    # the article directory as seen from the page (`../wiki/arts/` from
    # `docs/`); a leading `./` on the link is ignored.
    page_parent = page_rel.rpartition('/')[0]
    prefix = posixpath.relpath(dir_rel, page_parent or '.') + '/'
    prefix = '' if prefix == './' else prefix
    start = f'- **{marker}'
    rx = entry_rx(marker)

    findings = []
    entries = {}
    for line in page.read_text().splitlines():
        if not line.startswith(start):
            continue
        m = rx.match(line)
        if not m:
            findings.append(Finding('MALFORMED LESSON', page_rel, line[:70]))
            continue
        n, link = int(m.group(1)), m.group(2)
        link = link[2:] if link.startswith('./') else link
        if n in entries:
            findings.append(Finding(
                'DUPLICATE LESSON', page_rel,
                f"{marker}{n} has two entries"))
        entries[n] = link
        if not link.startswith(f'{prefix}{n}-'):
            findings.append(Finding(
                'LESSON LINK', page_rel,
                f"{marker}{n} links {link}, not its own article"))
        for field in fields:
            if not re.search(rf'(?<![\w-]){re.escape(field)}: ', line):
                findings.append(Finding(
                    'LESSON FIELD', page_rel,
                    f"{marker}{n} has no `{field}:`"))

    articles = {}
    for p in sorted(art_dir.glob('*.md')) if art_dir.is_dir() else []:
        rel = p.relative_to(root).as_posix()
        if p.name in exempt or p == page:
            continue
        m = ARTICLE.match(p.name)
        if not m:
            findings.append(Finding(
                'LESSON ARTICLE NAME', rel, "not `<N>-<slug>.md`"))
            continue
        n = int(m.group(1))
        if n in articles:
            findings.append(Finding(
                'DUPLICATE ARTICLE', rel,
                f"{marker}{n} already has {articles[n].name}"))
        articles[n] = p
        if not p.read_text().startswith(f'# {n}. '):
            findings.append(Finding(
                'LESSON ARTICLE TITLE', rel, f"title isn't `# {n}. ...`"))

    top = max([*entries, *articles], default=0)
    for n in range(1, top + 1):
        if n not in entries:
            findings.append(Finding(
                'MISSING LESSON', page_rel, f"no entry for {marker}{n}"))
        if n not in articles:
            findings.append(Finding(
                'MISSING ARTICLE', dir_rel, f"no {n}-*.md for {marker}{n}"))
    return findings


# --- table shape ---------------------------------------------------------

STOPWORDS = frozenset("""
    about after against always another because before between cannot could
    during either every except further having itself maybe never other
    rather should simply since still their there these thing things those
    through under until using where whether which while without would
    """.split())
TERM = re.compile(r'[A-Za-z]{6,}')
STEM = 6
SEP_ROW = re.compile(r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$')
TABLE_SEE = ("a lessons-table Home that holds no trace of the rule: add the "
             "rule to the Home, or point the row at where it lives")


def split_row(line):
    """The cells of a GFM table row: split on pipes not escaped with a
    backslash, outer pipes dropped, `\\|` read as a literal pipe."""
    body = line.strip()
    body = body[1:] if body.startswith('|') else body
    if body.endswith('|') and not body.endswith('\\|'):
        body = body[:-1]
    return [c.strip().replace('\\|', '|')
            for c in re.split(r'(?<!\\)\|', body)]


def terms(text):
    """A text's distinctive terms: words of six or more letters, lowered,
    stopwords out, cut to their first six letters so an inflection
    (`redact`, `redaction`) still matches."""
    return {w.lower()[:STEM] for w in TERM.findall(text)
            if w.lower() not in STOPWORDS}


def find_table(text, columns):
    """[(lineno, cells)] for the data rows of the first table outside a
    fence whose header cells equal `columns`; None when there is none."""
    lines = [(n, line) for n, line, kind in fences.scan_lines(text)
             if kind == fences.TEXT]
    for i, (_, line) in enumerate(lines):
        if '|' not in line or split_row(line) != columns:
            continue
        if i + 1 >= len(lines) or not SEP_ROW.match(lines[i + 1][1]):
            continue
        rows = []
        for m, row in lines[i + 2:]:
            if '|' not in row:
                break
            rows.append((m, split_row(row)))
        return rows
    return None


def table_findings(root, cfg, page_rel):
    s = cfg.section('lessons')
    columns = s.get('columns', ['Lesson', 'Rule', 'Home'])
    rule_col = s.get('rule-column', 'Rule')
    home_col = s.get('home-column', 'Home')
    min_overlap = s.get('min-overlap', 1)
    if rule_col not in columns or home_col not in columns:
        return [Finding('LESSONS SHAPE', page_rel,
                        f'[lessons] columns lacks "{rule_col}" or '
                        f'"{home_col}"')]
    ri, hi = columns.index(rule_col), columns.index(home_col)
    rows = find_table((root / page_rel).read_text(), columns)
    if rows is None:
        return [Finding('LESSON TABLE', page_rel,
                        f'no table with the header | {" | ".join(columns)} |')]
    skills, _ = skill_dirs(root, cfg)
    findings = []
    try:
        tracked = set(tracked_files(root))
    except NotAGitCheckout:
        tracked = None
        findings.append(Finding(
            'LESSONS NEEDS GIT', page_rel,
            "not a git checkout: Home paths are not resolved", review=True))
    suffixes = all_suffixes(tracked) if tracked is not None else set()
    path_rx = mention_rx(DEFAULT_EXTS)

    for n, cells in rows:
        where = f'{page_rel}:{n}'
        if len(cells) != len(columns):
            findings.append(Finding(
                'MALFORMED LESSON', where,
                f'{len(cells)} cells, header has {len(columns)}'))
            continue
        home, rule = cells[hi], cells[ri]
        if not home:
            findings.append(Finding(
                'EMPTY HOME', where, f'no {home_col} for "{cells[0][:50]}"'))
            continue
        bodies = []
        for m in SKILL_MENTION.finditer(home):
            name = m.group(1) or m.group(2)
            if name not in skills:
                findings.append(Finding(
                    'UNKNOWN HOME', where, f'skill `{name}` has no directory'))
                continue
            bodies += [p.read_text(errors='replace')
                       for p in sorted(skills[name].rglob('*.md'))]
        if tracked is not None:
            for m in path_rx.finditer(home):
                tok = m.group(1)
                if not resolves(tok, tracked, suffixes):
                    findings.append(Finding(
                        'UNKNOWN HOME', where,
                        f'`{tok}` names no tracked file'))
                    continue
                name = tok.lstrip('./')
                for rel in (t for t in tracked
                            if t == name or t.endswith('/' + name)):
                    try:
                        bodies.append((root / rel).read_text())
                    except (OSError, UnicodeDecodeError):
                        pass
        rule_terms = terms(rule)
        if bodies and len(rule_terms) >= 2:
            shared = rule_terms & terms('\n'.join(bodies))
            if len(shared) < min_overlap:
                findings.append(Finding(
                    'THIN HOME', where,
                    f"the {home_col} shares {len(shared)} of the rule's "
                    f"{len(rule_terms)} distinctive terms",
                    review=True, see=TABLE_SEE))
    return findings
