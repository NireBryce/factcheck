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

Config (`[lessons]`):

    [lessons]
    page = "docs/lessons-learned.md"           # required to enable
    dir = "docs/lessons-learned"               # default: page minus .md
    exempt = ["0-human-README.md"]             # files in dir that aren't lessons;
                                               # setting it replaces this default
    fields = ["Home", "Enforced"]              # each entry must carry `<f>: `
    marker = "§"                               # the number's prefix

Generalized from the index half of the lessons check in the repo
factcheck was extracted from; that repo keeps the other half (its
lessons-map file) as its own plugin, registered as `lessons`.
"""
import posixpath
import re

from ..findings import Finding
from ..registry import check

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
    exempt = set(s.get('exempt', ['0-human-README.md']))
    fields = s.get('fields', ['Home', 'Enforced'])
    marker = s.get('marker', '§')
    page = root / page_rel
    art_dir = root / dir_rel
    if not page.is_file():
        return [Finding('MISSING LESSONS PAGE', page_rel,
                        '[lessons] page names no file')]
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
