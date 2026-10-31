"""The repository root `check` is given (issue 8): a file or a missing
path is a usage error, and a directory outside git is reported per check
that needs git -- never a traceback, never a silent pass."""
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from factcheck import cli


def run(*argv):
    out = io.StringIO()
    return cli.main(list(argv), out=out), out.getvalue()


class CheckRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'page.md').write_text('# p\n')
        # Keep git from finding an enclosing repo or a hook's GIT_DIR.
        env = {k: os.environ.pop(k) for k in list(os.environ)
               if k.startswith('GIT_')}
        self.addCleanup(os.environ.update, env)
        os.environ['GIT_CEILING_DIRECTORIES'] = str(self.root.parent)
        self.addCleanup(os.environ.pop, 'GIT_CEILING_DIRECTORIES', None)

    def test_a_page_as_the_root_is_a_usage_error(self):
        rc, out = run('check', str(self.root / 'page.md'))
        self.assertEqual(rc, 2)
        self.assertIn('not a directory', out)
        self.assertIn('--root', out)

    def test_a_missing_root_is_a_usage_error(self):
        rc, out = run('--root', str(self.root / 'nope'), 'check')
        self.assertEqual(rc, 2)
        self.assertIn('not a directory', out)

    def test_outside_git_each_git_check_says_so_and_the_run_fails(self):
        rc, out = run('check', str(self.root))
        self.assertEqual(rc, 2)
        self.assertRegex(out, r'(?m)^[a-z-]+: skipped -- .* is not inside a git checkout')
        self.assertIn('not inside a git checkout', out)
        self.assertIn('could not run without a git checkout', out)
        self.assertNotIn('no findings', out)
        self.assertNotIn('only REVIEW', out)

    def test_inside_git_the_same_tree_runs(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        rc, out = run('rules', str(self.root))
        self.assertEqual(rc, 0, out)
        self.assertNotIn('skipped', out)


if __name__ == '__main__':
    unittest.main()
