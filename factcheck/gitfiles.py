"""Git-tracked file listing.

Checks that distinguish "on disk" from "in the repo" (a glob that matches
only untracked files means a rule never loads; a clone never sees the
untracked file) go through here. Needs git; a check calling it should say
so in its docstring."""
import subprocess


class NotAGitCheckout(Exception):
    """`root` is not inside a git checkout, or git isn't installed. The
    runner reports it once per check that needed git, never as a
    traceback."""


def tracked_files(root):
    """Repo-relative paths of every git-tracked file under `root`, sorted
    as `git ls-files` yields them. Raises NotAGitCheckout when there is
    no repository to ask."""
    try:
        r = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'],
                           capture_output=True, text=True)
    except FileNotFoundError:
        raise NotAGitCheckout('git is not installed') from None
    if r.returncode != 0:
        raise NotAGitCheckout(f'{root} is not inside a git checkout')
    return [f for f in r.stdout.split('\0') if f]
