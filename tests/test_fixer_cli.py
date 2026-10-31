"""The CLI's fixer dispatch: a fixer's arguments are its files, never the
repo root, so config loads from the root a check would use."""
import io
import os
import tempfile
import unittest
from pathlib import Path

from factcheck import cli, fixers


class FixerRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'factcheck.toml').write_text('[probe]\nseen = true\n')
        (self.root / 'page.md').write_text('# p\n')
        self.seen = {}

        def probe(root, cfg, files):
            self.seen.update(root=root, cfg=cfg.section('probe'), files=files)
            return 3
        fixers.FIXERS['probe-fixer'] = probe
        self.addCleanup(fixers.FIXERS.pop, 'probe-fixer')
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)

    def test_first_file_is_not_taken_as_the_root(self):
        rc = cli.main(['probe-fixer', 'page.md'], out=io.StringIO())
        self.assertEqual(self.seen['root'], self.root)
        self.assertEqual(self.seen['cfg'], {'seen': True})
        self.assertEqual(self.seen['files'], ['page.md'])
        self.assertEqual(rc, 3)

    def test_root_flag_still_wins(self):
        other = self.root / 'sub'
        other.mkdir()
        cli.main(['--root', str(other), 'probe-fixer', 'page.md'],
                 out=io.StringIO())
        self.assertEqual(self.seen['root'], other)


if __name__ == '__main__':
    unittest.main()
