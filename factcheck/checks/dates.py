"""dates: every page in the pages scope carries its `_Last modified:` line
right after the title, in exactly the configured format, and the date isn't
in the future.

This is the presence-and-shape half of the convention -- extractable and
mechanical. It is NOT a claim that the date is still accurate: telling
whether a page's *content* has moved on since that date needs a human
reading the diff, which is what the siblings staleness guard is for."""
import datetime
import re

from ..findings import Finding
from ..registry import check

DEFAULT_LINE = '_Last modified: {date}_'
DATE = r'(\d{4}-\d{2}-\d{2})'


def line_regex(cfg):
    """The configured line template as a whole-line regex; `{date}` in the
    template is where the YYYY-MM-DD group goes. Anchored to the whole
    line: a stray trailing word or missing underscore is exactly the kind
    of drift the check exists to catch."""
    tpl = cfg.section('dates').get('line', DEFAULT_LINE)
    return re.compile('^' + re.escape(tpl).replace(re.escape('{date}'), DATE)
                      + r'\s*$')


def parse_date(text):
    """A YYYY-MM-DD string as a date, or None when it names no real day
    (`2026-02-30`): the line regex accepts the shape, not the calendar."""
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def last_modified(text, rx):
    """The page's date, or None -- for a page without the line, or one
    whose date isn't a real day. `check_dates` is what reports either;
    this just can't compare without a date."""
    for line in text.splitlines()[:6]:
        m = rx.match(line)
        if m:
            return parse_date(m.group(1))
    return None


@check('dates', order=110)
def check_dates(root, cfg):
    """A page whose only heading is the title itself still needs the line --
    there's no exemption for a short page. A file with no title line is
    skipped: there's nothing to anchor the position against."""
    rx = line_regex(cfg)
    findings = []
    today = datetime.date.today()
    for path in cfg.scope('pages'):
        lines = path.read_text().splitlines()
        if not lines or not lines[0].startswith('# '):
            continue
        i = 1
        while i < len(lines) and lines[i].strip() == '':
            i += 1
        m = rx.match(lines[i]) if i < len(lines) else None
        if not m:
            findings.append(Finding(
                'MISSING LAST-MODIFIED', str(path),
                f"no `{DEFAULT_LINE.format(date='YYYY-MM-DD')}` line right "
                f"after the title"))
            continue
        date = parse_date(m.group(1))
        if date is None:
            findings.append(Finding(
                'INVALID DATE', str(path),
                f"Last modified says {m.group(1)}, which is not a real "
                f"date"))
            continue
        if date > today:
            findings.append(Finding(
                'FUTURE DATE', str(path),
                f"Last modified says {date}, which is after today ({today})"))
    return findings
