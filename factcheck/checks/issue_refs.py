"""issue-refs: a closed issue cited in a sentence that reads as pending.

"Reshaping this repo is tracked in issue 24" goes on describing future
work after issue 24 ships and closes. This check looks up the state of the
issues the docs cite and reports a closed one where the sentence still
speaks of it as not done.

    [issue-refs]
    enable = true
    repo = "owner/name"      # default: the checkout's own, from `gh`
    all = false              # true: every closed reference, pending or not

References read, outside fenced code: `issue N`, `#N` (not part of
`owner/repo#N`, an HTML entity or a longer token) and an issue or pull URL
into the same repo. A sentence reads as pending when it carries `tracked
in`, `see issue`, `until`, `planned`, `TODO`, `pending`, `not yet`,
`future` or `the <words> work`. Every finding is REVIEW: whether a closed
issue's sentence is stale is a human's call, and a citation kept as
history is fine. A line with `<!-- issue-ok: reason -->` is skipped.

Needs `gh` (capability `gh`): without it the run prints a skip line,
never a silent pass. A lookup `gh` fails is reported once, as REVIEW, and
the references it covered are left unjudged. Lookups are cached per run.
"""
import json
import re
import subprocess

from ..findings import Finding
from ..mdcore import fences
from ..registry import check

ISSUE_OK = re.compile(r'<!--\s*issue-ok:[^>]*-->')
REF = re.compile(
    r'(?<![\w/&#-])(?:[Ii]ssues?\s+#?(\d+)|#(\d+))(?![\w-])'
    r'|https://github\.com/([\w.-]+/[\w.-]+)/(?:issues|pull)/(\d+)')
PENDING = re.compile(
    r'\b(?:tracked in|see issue|until|planned|pending|not yet|future)\b'
    r'|\bTODO\b|\bthe [^.]{1,40}? work\b', re.I)
SENTENCE_END = re.compile(r'(?<=[.!?])\s+')
SEE = ("a closed issue cited as pending: update the sentence to say what "
       "shipped, or mark a citation kept as history <!-- issue-ok: reason -->")


def lookup(root, repo, number):
    """(state, reason) of issue or PR `number`, or None when `gh` cannot
    say. The one call out to GitHub; tests replace it."""
    r = subprocess.run(
        ['gh', 'api', f'repos/{repo}/issues/{number}'],
        cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
    except ValueError:
        return None
    return data.get('state'), data.get('state_reason')


def own_repo(root):
    r = subprocess.run(
        ['gh', 'repo', 'view', '--json', 'nameWithOwner', '-q',
         '.nameWithOwner'], cwd=root, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def sentence_around(line, start):
    """The sentence of `line` that holds offset `start`."""
    lo = 0
    for m in SENTENCE_END.finditer(line):
        if m.end() > start:
            return line[lo:m.start()]
        lo = m.end()
    return line[lo:]


@check('issue-refs', order=170, needs=('gh',))
def check_issue_refs(root, cfg):
    s = cfg.section('issue-refs')
    if not s.get('enable'):
        return []
    repo = s.get('repo') or own_repo(root)
    if not repo:
        return [Finding('ISSUE-REFS NEEDS REPO', 'factcheck config',
                        "no [issue-refs] repo and `gh repo view` found none",
                        review=True)]
    every = bool(s.get('all'))
    cache = {}
    failed = set()
    findings = []
    for path in cfg.scope('docs'):
        rel = path.relative_to(root).as_posix()
        for n, line, kind in fences.scan_lines(path.read_text()):
            if kind != fences.TEXT or ISSUE_OK.search(line):
                continue
            for m in REF.finditer(line):
                if m.group(3) and m.group(3) != repo:
                    continue            # another repo's issue
                num = int(m.group(1) or m.group(2) or m.group(4))
                if num not in cache:
                    cache[num] = lookup(root, repo, num)
                got = cache[num]
                if got is None:
                    failed.add(num)
                    continue
                state, reason = got
                if state != 'closed':
                    continue
                sentence = sentence_around(line, m.start())
                if not (every or PENDING.search(sentence)):
                    continue
                why = f" ({reason.replace('_', ' ')})" if reason else ''
                msg = f"#{num} is closed{why}"
                if not every:
                    msg += "; the sentence reads as pending"
                findings.append(Finding('CLOSED ISSUE', f'{rel}:{n}', msg,
                                        review=True, see=SEE))
    if failed:
        nums = ', '.join(f'#{x}' for x in sorted(failed))
        findings.append(Finding(
            'ISSUE LOOKUP', 'gh',
            f"could not look up {nums} in {repo}; left unjudged",
            review=True))
    return findings
