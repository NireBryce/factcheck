"""contents: a page's `## Contents` block matches its own headings -- plus
the fixer that makes it true.

Two halves:

- **stale**: a page that has a block whose list no longer matches its
  headings -- a heading renamed, added, or removed without regenerating.
- **missing**: a page that should have one and doesn't. Skipping this half
  outright made a *deleted* block look exactly like a correctly exempt
  page in the ancestor tool -- that failure is why it exists.

A page with no `##` headings at all is skipped either way -- there is
nothing to list, and the fixer declines to write an empty block.

`fix-contents` is the actual fix for every finding here (and for a broken
anchor pointing at the page's own Contents block): it rewrites the block in
place. It replaces ONLY the contiguous run of Contents bullet lines -- never
"everything up to the next heading", which once silently deleted the intro
prose that used to sit after the block, on every page that had any."""
import re

from ..findings import Finding
from ..registry import check
from ..fixers import fixer

CONTENTS_HEADING = re.compile(r'^##\s+Contents\s*$', re.M)
CONTENTS_ITEM = re.compile(r'^-\s+\[(?P<text>.+)\]\(#(?P<slug>[^)]+)\)\s*$',
                           re.M)
CONTENTS_ITEM_LINE = re.compile(r'^-\s+\[.+\]\(#[^)]+\)\s*$')
NEXT_HEADING = re.compile(r'^##\s+', re.M)

SEE = ("regenerate with `factcheck fix-contents <page>`")

# Pages exempt from carrying a Contents block at all. NOT the same set as
# the siblings check's exempt list, and conflating the two is a mistake
# that has already been made: a `-history.md` page is exempt from needing
# a *sibling* but still carries Contents like any other page, and one page
# lost its block on the strength of exactly that confusion. Keep the two
# lists apart and named for what they exempt.
DEFAULT_EXEMPT = (
    r'^wiki/agent-lessons-learned(\.md|/)',
    r'-for-agents\.md$',
)


def expected_contents_items(text):
    """[(heading_text, slug), ...] a fresh Contents block should list, in
    document order -- level-2 headings only, excluding a heading literally
    named `Contents` (itself). Slugs every heading on the page, not just
    the level-2 ones, so GitHub's per-page dedup counter lands on the right
    ones even though only level-2 headings make the list."""
    from ..mdcore.headings import iter_headings
    from ..mdcore.slugs import github_slug
    seen = {}
    items = []
    for level, text_ in iter_headings(text):
        slug = github_slug(text_, seen)
        if level == 2 and text_.strip() != 'Contents':
            items.append((text_, slug))
    return items


def actual_contents_items(text):
    """[(heading_text, slug), ...] the page's existing block actually
    lists, read back from the file rather than assumed -- or `None` if the
    page has no such section at all."""
    m = CONTENTS_HEADING.search(text)
    if not m:
        return None
    rest = text[m.end():]
    end = NEXT_HEADING.search(rest)
    section = rest[:end.start()] if end else rest
    return [(mm.group('text'), mm.group('slug'))
            for mm in CONTENTS_ITEM.finditer(section)]


@check('contents', order=100)
def check_contents(root, cfg):
    findings = []
    exempt = [re.compile(rx) for rx in
              cfg.section('contents').get('exempt', DEFAULT_EXEMPT)]
    for path in cfg.scope('pages'):
        rel = path.relative_to(root).as_posix()
        text = path.read_text()
        actual = actual_contents_items(text)
        expected = expected_contents_items(text)
        if actual is None:
            if expected and not any(rx.search(rel) for rx in exempt):
                findings.append(Finding(
                    'MISSING CONTENTS', str(path),
                    f"has {len(expected)} `##` headings but no '## Contents' "
                    f"block, and isn't exempt -- add one with "
                    f"`factcheck fix-contents {path}`", see=SEE))
            continue
        if actual != expected:
            findings.append(Finding(
                'STALE CONTENTS', str(path),
                f"its '## Contents' list doesn't match its own headings -- "
                f"fix with `factcheck fix-contents {path}`", see=SEE))
    return findings


@fixer('fix-contents')
def fix_contents(root, cfg, files):
    """Rewrites each page's Contents block in place to match its current
    headings exactly -- idempotent, safe any time a heading changed."""
    for f in files:
        _regenerate(root, cfg, f)


def _regenerate(root, cfg, file_arg):
    from pathlib import Path
    path = Path(file_arg)
    if not path.is_absolute():
        path = Path.cwd() / path
    text = path.read_text()
    items = expected_contents_items(text)
    if not items and not CONTENTS_HEADING.search(text):
        # Nothing to list and no block to rewrite: inserting an empty
        # Contents heading is worse than leaving the page alone (the check
        # passes either way -- an empty list against an empty list).
        print(f"SKIP {path}: no `##` headings to list")
        return
    block = '## Contents\n\n' + '\n'.join(
        f'- [{t}](#{s})' for t, s in items) + '\n'
    m = CONTENTS_HEADING.search(text)
    if m:
        rest = text[m.end():]
        lines = rest.splitlines(keepends=True)
        i = 0
        while i < len(lines) and lines[i].strip() == '':
            i += 1
        while i < len(lines) and CONTENTS_ITEM_LINE.match(lines[i]):
            i += 1
        tail = m.end() + sum(len(l) for l in lines[:i])
        new_text = text[:m.start()] + block + text[tail:]
    else:
        lines = text.splitlines(keepends=True)
        if not lines or not lines[0].startswith('# '):
            print(f"SKIP {path}: no '# Title' line to insert Contents after")
            return
        insert_at = 1
        while insert_at < len(lines) and lines[insert_at].strip() == '':
            insert_at += 1
        # A configured last-modified line sits between the title and
        # Contents -- skip past it too, so a fresh block lands after it
        # rather than splitting title from date.
        from .dates import line_regex
        if insert_at < len(lines) and line_regex(cfg).match(lines[insert_at]):
            insert_at += 1
            while insert_at < len(lines) and lines[insert_at].strip() == '':
                insert_at += 1
        # Past the intro prose too, to just above the first real section --
        # the title/date position above is only the floor, used when the
        # page has no `##` heading to sit in front of.
        first_heading = next(
            (i for i, l in enumerate(lines)
             if i >= insert_at and l.startswith('## ')), None)
        if first_heading is not None:
            insert_at = first_heading
        new_text = ''.join(lines[:insert_at]) + block + '\n' + ''.join(
            lines[insert_at:])
    if new_text != text:
        path.write_text(new_text)
        print(f"updated {path}")
    else:
        print(f"unchanged {path}")
