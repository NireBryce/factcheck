"""secrets: a prose enrollment claim (".sops.yaml ... enrolls `host`,
`host`, ...") against the enrollment file's actual key anchors.

Unlike membership prose, there is no legitimate named-as-an-exclusion
case for enrollment -- a set mismatch either way is a hard finding.

Config (`[secrets]`):

    [secrets]
    file = "flake/modules/general-config/system/secrets/.sops.yaml"
    name-prefix = "nire-"        # both the anchors (&<name>) and the
                                 # backticked tokens counted as claims
    claim = 'enrolls\\s+(.*?)—'  # em-dash terminator; re.S crosses the
                                 # markdown line-wrap inside the claim
"""
import re

from factcheck.checks.recipes import COMMENT
from factcheck.findings import Finding
from factcheck.registry import check

DEFAULT_CLAIM = r'enrolls\s+(.*?)—'


@check('secrets', order=60)
def check_secrets(root, cfg):
    s = cfg.section('secrets')
    rel = s.get('file', 'flake/modules/general-config/system/secrets/.sops.yaml')
    prefix = s.get('name-prefix', 'nire-')
    claim_rx = re.compile(s.get('claim', DEFAULT_CLAIM), re.S)
    token_rx = re.compile(r'`(' + re.escape(prefix) + r'[\w-]+)`')

    p = root / rel
    actual = set(re.findall(r'&(' + re.escape(prefix) + r'[\w-]+)',
                            COMMENT.sub('', p.read_text())))
    findings = []
    for path in cfg.scope('docs'):
        for m in claim_rx.finditer(path.read_text()):
            claimed = set(token_rx.findall(m.group(1)))
            if not claimed:
                continue  # some other "enrolls ... --" sentence, not this one
            for host in sorted(actual - claimed):
                findings.append(Finding(
                    'MISSING', str(path),
                    f"{p.name} enrolls '{host}' but the enrolls claim "
                    f"doesn't name it"))
            for host in sorted(claimed - actual):
                findings.append(Finding(
                    'EXTRA', str(path),
                    f"the enrolls claim names '{host}' but {p.name} doesn't "
                    f"enroll it"))
    return findings
