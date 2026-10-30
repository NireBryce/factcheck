"""Example factcheck plugin: flags occurrences of a configured marker
pattern in the docs scope -- the smallest real shape of a repo-specific
check: "this project's docs make a claim shape my repo cares about; here
is the lookup and here is the tag."

Register it by listing the file in the target repo's factcheck.toml:

    [plugins]
    load = ["plugins/example/pending-decisions.py"]

    [pending-decisions]
    pattern = 'DECISION-PENDING'

Everything here is data and one function: the `@check` decorator does the
rest (subcommand, place in `check`, capability declaration if you ever
need one).
"""
import re

from factcheck.findings import Finding
from factcheck.registry import check


@check('pending-decisions')
def check_pending_decisions(root, cfg):
    pattern = cfg.section('pending-decisions').get('pattern')
    if not pattern:
        return []  # not configured: the check is a no-op, not a finding
    rx = re.compile(pattern)
    findings = []
    for path in cfg.scope('docs'):
        for m in rx.finditer(path.read_text()):
            findings.append(Finding(
                'PENDING DECISION', str(path),
                f"'{m.group(0)}' marks an undecided claim -- resolve it or "
                f"drop the marker"))
    return findings
