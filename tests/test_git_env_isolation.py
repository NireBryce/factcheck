"""The suite run from inside a git hook leaves the hook's repo alone.
A hook exports GIT_DIR and friends; with them set, the fix-refs and rules
fixtures (`git init`, `git config user.*`, `git commit` in a temp dir)
still leave that repo's config, branches and index unchanged."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .helpers import strip_inherited_git_env

ROOT = Path(__file__).resolve().parent.parent


class Strip(unittest.TestCase):
    def test_removes_repo_local_vars_and_numbered_config_pairs(self):
        env = {'GIT_DIR': '/x/.git', 'GIT_INDEX_FILE': '/x/index',
               'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'user.name',
               'GIT_CONFIG_VALUE_0': 'v', 'GIT_AUTHOR_NAME': 'kept',
               'PATH': '/bin'}
        removed = strip_inherited_git_env(env)
        self.assertEqual(set(env), {'GIT_AUTHOR_NAME', 'PATH'})
        self.assertEqual(set(removed), {
            'GIT_DIR', 'GIT_INDEX_FILE', 'GIT_CONFIG_COUNT',
            'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0'})

    def test_this_process_has_none_left(self):
        self.assertNotIn('GIT_DIR', os.environ)
        self.assertNotIn('GIT_INDEX_FILE', os.environ)


class HookShapedRun(unittest.TestCase):
    """Runs the git-writing fixture suites as a hook would, aimed at a
    scratch repo standing in for the real one, and checks it after."""

    def test_scratch_repo_is_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / 'victim'
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith('GIT_')}
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
            subprocess.run(['git', 'init', '-q', str(repo)], env=env,
                           check=True)
            gitdir = repo / '.git'
            before = ((gitdir / 'config').read_text(),
                      sorted(p.name for p in (gitdir / 'refs/heads').iterdir()),
                      (gitdir / 'index').exists())
            hook_env = dict(env, GIT_DIR=str(gitdir),
                            GIT_INDEX_FILE=str(gitdir / 'index'))
            r = subprocess.run(
                [sys.executable, '-m', 'unittest', 'tests.test_fixrefs',
                 'tests.test_rules'], cwd=ROOT, env=hook_env,
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            after = ((gitdir / 'config').read_text(),
                     sorted(p.name for p in (gitdir / 'refs/heads').iterdir()),
                     (gitdir / 'index').exists())
            self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()
