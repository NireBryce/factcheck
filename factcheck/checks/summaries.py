"""summaries: every tracked file under a configured directory carries a
configured marker line.

The general shape: "a file in this family states in one comment what it
is, where a browser can see it without opening anything else". The
defaults are the convention factcheck was extracted from -- one-line
`# package summary:` comments on package modules -- and every part is
config."""
import re

from ..findings import Finding
from ..gitfiles import tracked_files
from ..registry import check

DEFAULT_MARKER = r'(?m)^\s*# package summary:'
SEE = "add the marker line the convention requires"


@check('summaries', order=165)
def check_summaries(root, cfg):
    s = cfg.section('summaries')
    directory = s.get('dir', 'flake/modules/packages-config/')
    suffix = s.get('suffix', '.nix')
    marker = re.compile(s.get('marker', DEFAULT_MARKER))
    tag = s.get('tag', 'NO PACKAGE SUMMARY')
    message = s.get(
        'message',
        "no marker line -- the summary convention requires one")
    exclude_files = set(s.get('exclude-files', ['defaults.nix']))
    exclude_underscore = bool(s.get('exclude-underscore', True))

    findings = []
    for rel in sorted(tracked_files(root)):
        if not (rel.startswith(directory) and rel.endswith(suffix)):
            continue
        parts = rel.split('/')
        if parts[-1] in exclude_files:
            continue
        if exclude_underscore and any(p.startswith('_') for p in parts):
            continue
        if not marker.search((root / rel).read_text()):
            findings.append(Finding(tag, rel, message, see=SEE))
    return findings
