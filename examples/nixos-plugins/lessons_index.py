"""lessons: the lessons index is exactly that -- one `- **§N** [title](...)
-- rule.` entry per lesson, each linking its own `<N>-<slug>.md` article
and carrying `Home:` and `Enforced:` fields, with an article for every §
from 1 to the top.

This plugin checks the index's own integrity -- the half that is
self-contained. The OTHER half of the original check validates the
lessons-map TOML, and deliberately does not move here: the map's glob
semantics is a single shared module that three readers in the source
repo (the reminder hook, a CLI helper, and this check) import so they
cannot disagree. An example copy here would be exactly the duplicate the
contract exists to prevent, so at flip time the repo's own plugin imports
its hooks module for the map half.

Config (`[lessons]`):

    [lessons]
    page = "wiki/agent-lessons-learned.md"
    dir = "wiki/agent-lessons-learned"
    human-readme = "0-human-README.md"   # explains the folder, not a lesson
"""
import re

from factcheck.findings import Finding
from factcheck.registry import check

ENTRY = re.compile(
    r'^- \*\*§(\d+)\*\* \[[^\]]+\]\(([\w-]+/[^)]+)\) — .+$')
ARTICLE = re.compile(r'^(\d+)-[a-z0-9-]+\.md$')


@check('lessons', order=150)
def check_lessons(root, cfg):
    s = cfg.section('lessons')
    page_rel = s.get('page', 'wiki/agent-lessons-learned.md')
    dir_rel = s.get('dir', 'wiki/agent-lessons-learned')
    readme = s.get('human-readme', '0-human-README.md')
    page = root / page_rel
    art_dir = root / dir_rel
    prefix = page_rel.rpartition('/')[2][:-3] + '/'

    findings = []
    entries = {}
    for line in page.read_text().splitlines():
        if not line.startswith('- **§'):
            continue
        m = ENTRY.match(line)
        if not m:
            findings.append(Finding(
                'MALFORMED LESSON', page_rel, line[:70]))
            continue
        n, link = int(m.group(1)), m.group(2)
        if n in entries:
            findings.append(Finding(
                'DUPLICATE LESSON', page_rel, f"§{n} has two entries"))
        entries[n] = link
        if not link.startswith(f'{prefix}{n}-'):
            findings.append(Finding(
                'LESSON LINK', page_rel,
                f"§{n} links {link}, not its own article"))
        for field in ('Home: ', 'Enforced: '):
            if f'. {field}' not in line:
                findings.append(Finding(
                    'LESSON FIELD', page_rel,
                    f"§{n} has no `{field.strip()}`"))

    articles = {}
    for p in sorted(art_dir.glob('*.md')):
        if p.name == readme:
            continue
        m = ARTICLE.match(p.name)
        if not m:
            findings.append(Finding(
                'LESSON ARTICLE NAME', str(p), "not `<N>-<slug>.md`"))
            continue
        n = int(m.group(1))
        if n in articles:
            findings.append(Finding(
                'DUPLICATE ARTICLE', str(p),
                f"§{n} already has {articles[n].name}"))
        articles[n] = p
        if not p.read_text().startswith(f'# {n}. '):
            findings.append(Finding(
                'LESSON ARTICLE TITLE', str(p),
                "title isn't `# {n}. ...`".format(n=n)))

    top = max([*entries, *articles], default=0)
    for n in range(1, top + 1):
        if n not in entries:
            findings.append(Finding(
                'MISSING LESSON', page_rel, f"no entry for §{n}"))
        if n not in articles:
            findings.append(Finding(
                'MISSING ARTICLE', dir_rel, f"no {n}-*.md for §{n}"))
    return findings
