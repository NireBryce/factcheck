"""The registry is the subcommand table, and the re-registration rules are
what make reloads safe. Ported from the ancestor suite, which grew these
tests from real breakage (a double-registration assert, a reload that
duplicated every check)."""
import contextlib
import importlib.util
import io
import pathlib
import subprocess
import sys
import unittest

from factcheck import checks as builtin_checks  # noqa: F401  (registers)
from factcheck import cli, registry

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / 'bin' / 'factcheck'


class EveryBuiltinIsRegistered(unittest.TestCase):
    def test_every_check_function_is_registered(self):
        import types
        registered = {c.fn.__name__ for _, c in registry.registered()}
        defined = set()
        for mod in vars(builtin_checks).values():
            if not isinstance(mod, types.ModuleType):
                continue
            defined |= {n for n, fn in vars(mod).items()
                        if n.startswith('check_') and callable(fn)}
        self.assertTrue(defined)
        self.assertEqual(defined - registered, set())


class Ordering(unittest.TestCase):
    def test_unordered_checks_run_last_in_registration_order(self):
        saved = dict(registry.CHECKS)
        try:
            def late(root, cfg):
                return []

            def later(root, cfg):
                return []

            def first(root, cfg):
                return []

            def other(root, cfg):
                return []
            registry.check('zz-late')(late)
            registry.check('zz-later')(later)
            registry.check('aa-first', order=-1)(first)
            names = registry.names()
            self.assertEqual(names[0], 'aa-first')
            self.assertEqual(names[-2:], ['zz-late', 'zz-later'])
            with self.assertRaises(AssertionError):
                registry.check('zz-late')(other)
        finally:
            registry.CHECKS.clear()
            registry.CHECKS.update(saved)

    def test_same_module_and_qualname_replaces_its_entry(self):
        # A plugin exec'd afresh arrives as a new object: that replaces, and
        # keeps the original registration sequence instead of appending.
        saved = dict(registry.CHECKS)
        try:
            def fn(root, cfg):
                return []

            def same_name(root, cfg):
                return []
            same_name.__qualname__ = fn.__qualname__
            same_name.__module__ = fn.__module__
            registry.check('zz-reload')(fn)
            first_seq = registry.CHECKS['zz-reload'].seq
            registry.check('zz-reload')(same_name)
            self.assertEqual(registry.CHECKS['zz-reload'].seq, first_seq)
            self.assertEqual(registry.names().count('zz-reload'), 1)
        finally:
            registry.CHECKS.clear()
            registry.CHECKS.update(saved)


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        # Root pinned to this repo: cwd may be any project, whose
        # factcheck.toml (plugins, scopes) would otherwise leak into a
        # `check` run that is only testing dispatch.
        code = cli.main(['--root', str(REPO_ROOT), *args], out=out)
        return code, out.getvalue()

    def test_unknown_subcommand_exits_2(self):
        r = subprocess.run([sys.executable, str(SCRIPT), 'nope'],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_unknown_flag_exits_2(self):
        code, outtext = self.run_cli('--bogus')
        self.assertEqual(code, 2)
        self.assertIn('--bogus', outtext)

    def test_checks_lists_fixers(self):
        code, outtext = self.run_cli('checks')
        self.assertEqual(code, 0)
        self.assertIn('fixers: fix-contents', outtext)

    def test_skip_leaves_a_check_out_and_says_so(self):
        saved = dict(registry.CHECKS)
        try:
            registry.CHECKS.clear()

            def ok(root, cfg):
                return []

            def bad(root, cfg):
                from factcheck.findings import Finding
                return [Finding('BAD', 'x', 'always')]
            registry.check('zz-ok', order=1)(ok)
            registry.check('zz-bad', order=2)(bad)

            code, outtext = self.run_cli('check')
            self.assertEqual(code, 1)
            self.assertIn('BAD  x: always', outtext)
            code, outtext = self.run_cli('check', '--skip=zz-bad')
            self.assertEqual(code, 0)
            self.assertNotIn('BAD', outtext)
            self.assertIn('skipped zz-bad', outtext)
        finally:
            registry.CHECKS.clear()
            registry.CHECKS.update(saved)

    def test_skip_rejects_an_unknown_check(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), 'check', '--skip=nope'],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_config_disabled_check_does_not_run_and_is_not_an_error(self):
        # Unlike --skip (validated strictly -- a typo should stop the run),
        # config `disabled` may name a check that isn't registered in this
        # run at all, and says nothing when it fires.
        import contextlib
        import tempfile
        from factcheck.config import Config
        saved = dict(registry.CHECKS)
        try:
            registry.CHECKS.clear()

            def bad(root, cfg):
                from factcheck.findings import Finding
                return [Finding('BAD', 'x', 'always')]
            registry.check('zz-bad')(bad)
            with tempfile.TemporaryDirectory() as tmp:
                cfg = Config(pathlib.Path(tmp), {'checks': {'disabled': [
                    'zz-bad', 'not-registered-here']}})
                buf = io.StringIO()
                code = cli._run_checks('check', pathlib.Path(tmp), cfg,
                                       set(), buf)
            self.assertEqual(code, 0)
            self.assertNotIn('BAD', buf.getvalue())
            self.assertNotIn('skipped', buf.getvalue())
        finally:
            registry.CHECKS.clear()
            registry.CHECKS.update(saved)

    def test_capability_skip_says_so(self):
        saved = dict(registry.CHECKS)
        try:
            registry.CHECKS.clear()
            registry.check('zz-needs', needs=('no-such-capability',))(
                lambda root, cfg: [])
            code, outtext = self.run_cli('zz-needs')
            self.assertEqual(code, 0)
            self.assertIn('zz-needs: skipped (needs no-such-capability',
                          outtext)
            code, outtext = self.run_cli('zz-needs')
            self.assertEqual(code, 0)
            self.assertIn('skipped', outtext)
        finally:
            registry.CHECKS.clear()
            registry.CHECKS.update(saved)


class PluginReloading(unittest.TestCase):
    TMP_PLUGIN = '''
from factcheck.findings import Finding
from factcheck.registry import check

@check('zz-plugin')
def check_zz(root, cfg):
    return []
'''

    def test_reloading_a_plugin_replaces_its_checks(self):
        from factcheck import plugins, config
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'plugins').mkdir()
            (root / 'plugins' / 'zz.py').write_text(self.TMP_PLUGIN)
            cfg = config.Config(
                root, {'plugins': {'load': ['plugins/zz.py']}})
            plugins.load(cfg)
            plugins.load(cfg)  # a fresh exec per call must not duplicate
            self.assertEqual(registry.names().count('zz-plugin'), 1)
            registry.CHECKS.pop('zz-plugin')


if __name__ == '__main__':
    unittest.main()
