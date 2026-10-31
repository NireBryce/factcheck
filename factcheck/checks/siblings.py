"""siblings: the two-audience page split, guarded.

A long page written for a human and its compressed sibling written for
something loading it mid-task are *deliberate* duplication -- which is
exactly why it is the one duplication worth a mechanical staleness guard:
the split is only as good as the check under it.

- **stale** is the guard: both pages carry a last-modified line (checked
  for shape by `dates`), so a sibling dated EARLIER than its source means
  the source was edited and the sibling wasn't -- one fact, two copies,
  one of them now lying. Equal dates pass: that's the same-change edit
  the convention asks for.
- An older sibling is satisfied by a reviewed-line dated at or after the
  source's -- how an edit with genuinely nothing to sync gets landed
  without either lying about the sibling's date or leaving the run red.
  The reason is mandatory and the date can't be in the future: a forged
  future date would silence this pair permanently.
- **missing**: a page over the word line with no sibling and no folded
  first section.
- **budget** is REVIEW only -- the point of a sibling is density, and a
  page that is mostly commands has a floor no editing gets under. Losing
  a fact to hit a number is the worse outcome."""
import datetime
import re

from ..findings import Finding
from ..registry import check

SYNC_SEE = ("the source was edited without its condensed sibling following; "
            "follow the edit or land a dated reviewed-line -- don't bump "
            "the sibling's date to clear it")

# The escape hatch: written on the sibling, under its last-modified line:
#     _Sibling reviewed: 2026-09-11 -- header reorder, no facts moved_
# It means someone read the source as of that date and confirmed nothing
# here needs to change. A reason is mandatory -- "reviewed" with nothing
# after it is the silent bump wearing a badge.
REVIEWED_LINE = re.compile(
    r'^_Sibling reviewed: (\d{4}-\d{2}-\d{2})\s*(?:--|—)\s*(\S.*?)_\s*$')

# Exempt from *requiring* a sibling (each may still have one).
DEFAULT_EXEMPT = (
    r'^wiki/agent-lessons-learned(\.md|/)',
    r'-history\.md$',
)


def _settings(cfg):
    s = cfg.section('siblings')
    return {
        'suffix': s.get('suffix', '-for-agents'),
        'required_words': int(s.get('required-words', 1000)),
        'budget': float(s.get('budget', 0.5)),
        'fold': s.get('fold-heading', 'Quick facts'),
        'exempt': [re.compile(rx) for rx in s.get('exempt', DEFAULT_EXEMPT)],
    }


def sibling_pairs(pages, suffix):
    """(source, sibling) for every `<page><suffix>.md` in `pages`, the
    sibling first-class even when its source doesn't exist yet (the orphan
    case)."""
    pairs = []
    for sib in pages:
        if sib.name.endswith(f'{suffix}.md'):
            source = sib.with_name(
                sib.name[:-len(f'{suffix}.md')] + '.md')
            pairs.append((source, sib))
    return pairs


def _words(text):
    """Word count matching `wc -w`, so a human can check a budget finding
    with one shell command rather than rerunning this tool."""
    return len(text.split())


def _reviewed(text):
    """The sibling's reviewed date and reason, or (None, None). Read from
    the same head-of-file window as `last_modified` so the two lines stay
    visually adjacent. A line whose date isn't a real day gives
    (False, raw-date): present, but no date to honour."""
    from .dates import parse_date
    for line in text.splitlines()[:8]:
        m = REVIEWED_LINE.match(line)
        if m:
            date = parse_date(m.group(1))
            if date is None:
                return False, m.group(1)
            return date, m.group(2).strip()
    return None, None


@check('siblings', order=140)
def check_siblings(root, cfg):
    from .dates import last_modified, line_regex
    from ..mdcore.headings import first_section

    st = _settings(cfg)
    rx = line_regex(cfg)
    pages = cfg.scope('pages')
    findings = []
    have_sibling = set()

    for source, sib in sibling_pairs(pages, st['suffix']):
        rel_sib = sib.relative_to(root).as_posix()
        rel_src = source.relative_to(root).as_posix()
        if not source.exists():
            findings.append(Finding(
                'ORPHAN SIBLING', rel_sib,
                f"no {rel_src} for it to condense", see=SYNC_SEE))
            continue
        have_sibling.add(source)
        src_text, sib_text = source.read_text(), sib.read_text()

        src_date = last_modified(src_text, rx)
        sib_date = last_modified(sib_text, rx)
        rev_date, rev_reason = _reviewed(sib_text)
        if rev_date is False:
            findings.append(Finding(
                'INVALID REVIEW DATE', rel_sib,
                f"Sibling reviewed says {rev_reason}, which is not a real "
                f"date -- it can't excuse a stale pair", see=SYNC_SEE))
            rev_date, rev_reason = None, None
        if rev_date and rev_date > datetime.date.today():
            findings.append(Finding(
                'FUTURE REVIEW', rel_sib,
                f"Sibling reviewed says {rev_date}, which is after today "
                f"({datetime.date.today()}) -- a future date would satisfy "
                f"this pair's staleness guard forever", see=SYNC_SEE))
            rev_date = None
        if src_date and sib_date and sib_date < src_date:
            if rev_date and rev_date >= src_date:
                pass  # declared no-op: read as of rev_date, nothing to sync
            elif rev_date:
                findings.append(Finding(
                    'STALE SIBLING', rel_sib,
                    f"Sibling reviewed {rev_date} ({rev_reason}) predates "
                    f"{rel_src}'s {src_date} -- that page has been edited "
                    f"again since the review; re-read it and either follow "
                    f"the edit here or re-date the review", see=SYNC_SEE))
            else:
                findings.append(Finding(
                    'STALE SIBLING', rel_sib,
                    f"Last modified {sib_date} is older than {rel_src}'s "
                    f"{src_date} -- that page was edited without its "
                    f"condensed sibling following in the same change. If "
                    f"the edit genuinely had nothing to sync, say so with "
                    f"a `_Sibling reviewed: {src_date} -- <reason>_` line "
                    f"here rather than bumping the date above", see=SYNC_SEE))

        src_words, sib_words = _words(src_text), _words(sib_text)
        budget = int(src_words * st['budget'])
        if sib_words > budget:
            findings.append(Finding(
                'REVIEW', rel_sib,
                f"{sib_words} words against a {budget}-word budget "
                f"({int(st['budget'] * 100)}% of {rel_src}'s {src_words}) "
                f"-- cut narration, not facts; if what's left is all "
                f"load-bearing, over is the right answer", review=True))

        if sib.name not in src_text:
            findings.append(Finding(
                'NO SIBLING LINK', rel_src,
                f"doesn't link to {sib.name}", see=SYNC_SEE))
        if source.name not in sib_text:
            findings.append(Finding(
                'NO SOURCE LINK', rel_sib,
                f"doesn't link back to {source.name}", see=SYNC_SEE))

    for path in pages:
        rel = path.relative_to(root).as_posix()
        if path.name.endswith(f"{st['suffix']}.md") or path in have_sibling:
            continue
        if any(rx.search(rel) for rx in st['exempt']):
            continue
        text = path.read_text()
        words = _words(text)
        if words >= st['required_words']:
            if first_section(text) == st['fold']:
                continue  # single page, dense summary folded in at the top
            findings.append(Finding(
                'MISSING SIBLING', rel,
                f"{words} words, over the {st['required_words']}-word line, "
                f"but has neither a {path.stem}{st['suffix']}.md nor `## "
                f"{st['fold']}` as its first section", see=SYNC_SEE))
    return findings
