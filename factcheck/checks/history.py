"""history: lesson numbers that left the lessons index but are still
cited.

Opt-in (`[history] enable`), REVIEW only, and narrow on purpose. What
today's checks cannot see is the citation that outlived its target: a
wiki page still pointing at §14 after §14 left the index. `lessons-index`
reads the index page and its articles, not who cites them, and nothing
else looks -- exactly the drift that only git history knows about.

The check reuses what a repo already teaches `lessons-index` -- the
`[lessons] page` binding and the index's two number shapes (the
`**§N**` entry marker and the `## N.` section heading) -- and reads the
page's past with one `git log -p --follow`. A number is a ghost when it
was deleted from the page, never re-added, and is absent from today's
page; it becomes a finding only where today's docs still cite it, so a
clean rename never lands here. Needs git; says so by raising
NotAGitCheckout like the other git-reading checks.

Not caught on purpose: bare numbers in a `§§2, 5`-style list (only
§-prefixed citations are read), recipes (a `just <name>` mention is
already a hard UNKNOWN RECIPE today), and shapes with no config to
recognize them -- those want the plugin half the request sketched.
"""
import re
import subprocess

from .. import gitfiles
from ..findings import Finding
from ..registry import check

ENTRY_NUM = re.compile(r'\*\*§(\d+)\*\*')
SECTION_NUM = re.compile(r'^#{1,6}\s+(\d+)\.\s', re.M)
CITED = re.compile(r'§\s*(\d+)')


def page_numbers(text):
    """Every lesson number the page states, in either shape."""
    return ({int(n) for n in ENTRY_NUM.findall(text)}
            | {int(n) for n in SECTION_NUM.findall(text)})


def removed_numbers(root, page_rel):
    """{number: short sha} of numbers whose last history event was a
    removal, from one `git log -p --follow` walk replayed oldest first.
    Per commit the deletions apply before the additions, so a number
    that changes shape (entry to section) in one commit was never
    gone."""
    r = subprocess.run(
        ['git', '-C', str(root), 'log', '--follow', '-p',
         '--format=\x02%H', '--', page_rel],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise gitfiles.NotAGitCheckout(f'{root} is not inside a git checkout')
    commits = []
    sha, removed, added = None, set(), set()
    for line in r.stdout.splitlines():
        if line.startswith('\x02'):
            if sha is not None:
                commits.append((sha, removed, added))
            sha, removed, added = line[1:8], set(), set()
        elif line.startswith('-') and not line.startswith('---'):
            removed |= page_numbers(line)
        elif line.startswith('+') and not line.startswith('+++'):
            added |= page_numbers(line)
    if sha is not None:
        commits.append((sha, removed, added))

    present, ghosts = set(), {}
    for csha, c_removed, c_added in reversed(commits):
        for n in c_removed:
            if n in present:
                ghosts[n] = csha
            present.discard(n)
        present |= c_added
    return {n: s for n, s in ghosts.items() if n not in present}


@check('history', order=180)
def check_history(root, cfg):
    """Where today's docs still cite a lesson number that git history
    shows leaving the lessons index. Opt-in: [history] enable."""
    if not cfg.section('history').get('enable'):
        return []
    page_rel = cfg.section('lessons').get('page')
    if not page_rel:
        return []
    tracked = set(gitfiles.tracked_files(root))
    head = page_numbers((root / page_rel).read_text())
    ghosts = {n: s for n, s in removed_numbers(root, page_rel).items()
              if n not in head}
    findings = []
    for path in cfg.scope('docs'):
        rel = path.relative_to(root).as_posix()
        if rel == page_rel:
            continue  # the index is the source of the numbers, not a cite
        for m in CITED.finditer(path.read_text()):
            n = int(m.group(1))
            if n in ghosts:
                findings.append(Finding(
                    'GHOST LESSON', str(path),
                    f"cites §{n}, which left the lessons index in "
                    f"{ghosts[n]} -- restore the lesson or fix the "
                    f"citation", review=True))
    return findings
