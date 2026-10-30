"""Git-tracked file listing.

Checks that distinguish "on disk" from "in the repo" (a glob that matches
only untracked files means a rule never loads; a clone never sees the
untracked file) go through here. Needs git; a check calling it should say
so in its docstring."""
import subprocess


def tracked_files(root):
    """Repo-relative paths of every git-tracked file under `root`, sorted
    as `git ls-files` yields them."""
    r = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'],
                       capture_output=True, text=True, check=True)
    return [f for f in r.stdout.split('\0') if f]
