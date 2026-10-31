"""plugins/readme_checks_table.py and the fix-generated fixer: the README
checks table follows the registry. A new check gets a row whose
hand-written cells start empty and fail until filled; a removed check's
row goes, and the write run reports the hand text it carried."""
import importlib.util
import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout

from factcheck import fixers, genregions, registry
from factcheck.checks import generated
from factcheck.config import Config

PLUGIN = (pathlib.Path(__file__).resolve().parent.parent / 'plugins'
          / 'readme_checks_table.py')
TABLE = ('<!-- generated:checks-table -->\n'
         '| check | claims it checks | bindings (config) |\n|---|---|---|\n'
         '| `alpha` | alpha prose | `[alpha]` |\n'
         '| `gone` | gone prose | `[gone]` |\n'
         '<!-- /generated -->\n')


class ReadmeRegion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        for reg in (registry.CHECKS, genregions.REGIONS, fixers.FIXERS):
            saved = dict(reg)
            self.addCleanup(reg.update, saved)
            self.addCleanup(reg.clear)
            reg.clear()
        registry.check('alpha')(lambda root, cfg: [])
        registry.check('beta')(lambda root, cfg: [])
        spec = importlib.util.spec_from_file_location('readme_plugin', PLUGIN)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
        self.readme = self.root / 'README.md'
        self.readme.write_text('# R\n\n' + TABLE)
        self.cfg = Config(self.root, {'scopes': {'pages': ['README.md']}})

    def fix(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = generated.fix_generated(self.root, self.cfg, [str(self.readme)])
        return rc, out.getvalue()

    def test_stale_until_regenerated(self):
        tags = [f.tag for f in generated.check_generated(self.root, self.cfg)]
        self.assertIn('STALE GENERATED', tags)

    def test_new_check_row_is_empty_and_fails_removed_row_reported(self):
        rc, out = self.fix()
        self.assertEqual(rc, 1)
        self.assertIn("row 'beta' has no claims it checks", out)
        self.assertIn("dropped  README.md: region 'checks-table' row "
                      "'`gone`'", out)
        text = self.readme.read_text()
        self.assertIn('| `alpha` | alpha prose | `[alpha]` |', text)
        self.assertIn('| `beta` |  |  |', text)
        self.assertNotIn('gone', text)

    def test_filled_in_is_clean_and_idempotent(self):
        self.fix()
        self.readme.write_text(self.readme.read_text().replace(
            '| `beta` |  |  |', '| `beta` | beta prose | none |'))
        self.assertEqual(self.fix(), (0, ''))
        self.assertEqual(generated.check_generated(self.root, self.cfg), [])


if __name__ == '__main__':
    unittest.main()
