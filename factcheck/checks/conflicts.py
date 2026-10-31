"""conflicts: a merge left its conflict markers in a doc.

A resolution that kept both halves of a hunk, or forgot one, leaves
`<<<<<<< ours`, `=======` and `>>>>>>> theirs` lines behind (and, with
`merge.conflictStyle = diff3` or `zdiff3`, a `||||||| base` line), and a
page with them still renders; nothing else here notices, since a marker is
just text to every other check. A `<<<<<<<` or `>>>>>>>` line (seven
markers, then a space or the line's end) is a finding; a bare `=======` or
`|||||||` counts only between the two, because on its own `=======` is a
heading underline.

In prose a marker is a hard finding. Inside fenced code it is a REVIEW:
a merge conflicts in a code sample as easily as in prose, but a doc may
also show a conflict as an example. An example fence is marked with
`<!-- conflict-ok: reason -->` on the line just before its opening fence,
and its markers are skipped.
"""
import re

from ..findings import Finding
from ..mdcore import fences
from ..registry import check

OPEN = re.compile(r'^<{7}(?: |$)')
BASE = re.compile(r'^\|{7}(?: |$)')
MID = re.compile(r'^={7}\s*$')
CLOSE = re.compile(r'^>{7}(?: |$)')
CONFLICT_OK = re.compile(r'<!--\s*conflict-ok:[^>]*-->')
SEE = ("a merge's conflict markers are still in the file: resolve the hunk "
       "(keep the right side, or both), then delete the marker lines; a "
       "fence that shows a conflict on purpose gets "
       "<!-- conflict-ok: reason --> on the line before it")


@check('conflicts', order=10)
def check_conflicts(root, cfg):
    findings = []
    for path in cfg.scope('docs'):
        rel = path.relative_to(root).as_posix()
        inside = False      # between a <<<<<<< and its >>>>>>>
        example = False     # in a fence marked conflict-ok
        previous = ''
        for n, line, kind in fences.scan_lines(path.read_text()):
            if kind == fences.OPENER:
                example = bool(CONFLICT_OK.search(previous))
            previous = line
            if kind in (fences.OPENER, fences.CLOSER):
                continue
            if kind == fences.BODY and example:
                continue
            if OPEN.match(line):
                inside = True
            elif CLOSE.match(line):
                inside = False
            elif not (inside and (MID.match(line) or BASE.match(line))):
                continue
            fenced = kind == fences.BODY
            findings.append(Finding(
                'CONFLICT MARKER', f'{rel}:{n}',
                line.strip()[:60] + (' (in fenced code)' if fenced else ''),
                review=fenced, see=SEE))
    return findings
