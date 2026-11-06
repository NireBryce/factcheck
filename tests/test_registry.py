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
    def setUp(self):
        # Dispatch tests get an empty config by default: this repo's own
        # config (scopes, disabled names, plugins) would otherwise leak
        # into a `check` run that is only testing dispatch -- and strict
        # `disabled` validation fails those runs once the registry is
        # cleared by the test. A test passing --config explicitly wins.
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._empty_cfg = pathlib.Path(self._tmp.name) / 'empty.toml'
        self._empty_cfg.write_text('')

    def run_cli(self, *args):
        out = io.StringIO()
        extra = () if '--config' in args else ('--config', str(self._empty_cfg))
        code = cli.main(['--root', str(REPO_ROOT), *extra, *args], out=out)
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

    def test_a_check_returning_strings_exits_2_and_names_the_check(self):
        # A plugin that cannot import factcheck (a stdlib-only hook module)
        # can hand back plain strings. The runner used to die in
        # `see_lines` with `'str' object has no attribute 'see'`, naming
        # no check.
        saved = dict(registry.CHECKS)
        try:
            registry.CHECKS.clear()

            def strs(root, cfg):
                return ["DEMO  a.md: a plain string, not a Finding"]
            registry.check('zz-strs')(strs)

            code, outtext = self.run_cli('check')
            self.assertEqual(code, 2)
            self.assertIn("'zz-strs'", outtext)
            self.assertIn('str', outtext)
            self.assertIn('Finding', outtext)
            self.assertNotIn('Traceback', outtext)
        finally:
            registry.CHECKS.clear()
            registry.CHECKS.update(saved)

    def test_a_check_returning_none_exits_2_and_names_the_check(self):
        # The other common slip: a check that builds its list and forgets
        # `return`.
        saved = dict(registry.CHECKS)
        try:
            registry.CHECKS.clear()

            def forgot_return(root, cfg):
                pass
            registry.check('zz-none')(forgot_return)

            code, outtext = self.run_cli('check')
            self.assertEqual(code, 2)
            self.assertIn("'zz-none'", outtext)
            self.assertIn('NoneType', outtext)
        finally:
            registry.CHECKS.clear()
            registry.CHECKS.update(saved)

    def test_config_disabled_names_are_strict(self):
        # [checks] disabled validates like --skip now: a name nothing
        # answers to stops the run naming itself, instead of silently
        # doing nothing (#21). The --config file replaces the repo's own,
        # so this runs on this repo without its plugins.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = pathlib.Path(tmp) / 'cfg.toml'
            cfg_file.write_text('[checks]\ndisabled = ["nope-check"]\n')
            code, outtext = self.run_cli('--config', str(cfg_file), 'check')
        self.assertEqual(code, 2)
        self.assertIn('unknown check(s) in [checks] disabled', outtext)
        self.assertIn('nope-check', outtext)

    def test_single_check_of_disabled_check_is_refused(self):
        # The aggregate skips disabled checks silently (the config is the
        # record); naming the check directly must not fall through to a
        # findings-less pass -- that is the wrong-repo green in
        # miniature. Same refusal for --skip naming the command itself.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = pathlib.Path(tmp) / 'cfg.toml'
            cfg_file.write_text('[checks]\ndisabled = ["dates"]\n')
            code, outtext = self.run_cli('--config', str(cfg_file), 'dates')
        self.assertEqual(code, 2)
        self.assertIn('switched off by [checks] disabled', outtext)
        code, outtext = self.run_cli('dates', '--skip=dates')
        self.assertEqual(code, 2)
        self.assertIn('switched off by --skip', outtext)

    def test_positional_repo_root_is_honored_not_dropped(self):
        # The edit hook calls `factcheck siblings <root>`; a silently
        # ignored positional made the check scan the harness's cwd and
        # exit 0 -- the wrong-repo green this test exists to prevent.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'wiki').mkdir()
            (root / 'wiki/page.md').write_text(
                '# P\n\n_Last modified: 2026-01-01_\n\n## A\n\nx\n')
            (root / 'wiki/page-for-agents.md').write_text(
                '# P\n\n_Last modified: 2020-01-01_\n\n## A\n\nx\n')
            out = io.StringIO()
            code = cli.main(['--skip=nope' if False else 'siblings',
                             str(root)], out=out)
        self.assertEqual(code, 1)
        self.assertIn('STALE SIBLING', out.getvalue())

    def test_skip_rejects_an_unknown_check(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), 'check', '--skip=nope'],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_config_disabled_unknown_name_exits_2(self):
        # `disabled` validates like --skip now: a name nothing answers to
        # is a stale decision the run must surface, not silently drop
        # (#21). A known name still skips its check without a word.
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
            self.assertEqual(code, 2)
            self.assertIn('not-registered-here', buf.getvalue())
        finally:
            registry.CHECKS.clear()
            registry.CHECKS.update(saved)

    def test_config_disabled_known_name_skips_silently(self):
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
                cfg = Config(pathlib.Path(tmp),
                             {'checks': {'disabled': ['zz-bad']}})
                buf = io.StringIO()
                code = cli._run_checks('check', pathlib.Path(tmp), cfg,
                                       set(), buf)
            self.assertEqual(code, 0)
            self.assertNotIn('BAD', buf.getvalue())
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
