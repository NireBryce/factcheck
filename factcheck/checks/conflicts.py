"""conflicts: a merge left its conflict markers in a doc.

A resolution that kept both halves of a hunk, or forgot one, leaves
`<<<<<<< ours`, `=======` and `>>>>>>> theirs` lines behind, and a page
with them still renders; nothing else here notices, since a marker is
just text to every other check. A `<<<<<<<` or `>>>>>>>` line (seven
markers, then a space or the line's end) is a finding; a bare `=======`
counts only between the two, because on its own it is a heading
underline. Lines inside fenced code are skipped, so a doc may show a
conflict as an example.
"""
import re

from ..findings import Finding
from ..mdcore import fences
from ..registry import check

OPEN = re.compile(r'^<{7}(?: |$)')
MID = re.compile(r'^={7}\s*$')
CLOSE = re.compile(r'^>{7}(?: |$)')
SEE = ("a merge's conflict markers are still in the file: resolve the hunk "
       "(keep the right side, or both), then delete the marker lines")


@check('conflicts', order=10)
def check_conflicts(root, cfg):
    findings = []
    for path in cfg.scope('docs'):
        rel = path.relative_to(root).as_posix()
        inside = False
        for n, line, kind in fences.scan_lines(path.read_text()):
            if kind != fences.TEXT:
                continue
            if OPEN.match(line):
                inside = True
            elif CLOSE.match(line):
                inside = False
            elif not (inside and MID.match(line)):
                continue
            findings.append(Finding(
                'CONFLICT MARKER', f'{rel}:{n}', line.strip()[:60], see=SEE))
    return findings
