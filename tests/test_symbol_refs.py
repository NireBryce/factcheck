"""symbol-refs: a name beside a path must occur in that file as a whole
word; prose parentheses, missing files, opt-out and opt-in."""
import subprocess

from .helpers import Tree

from factcheck.checks import symbol_refs

ON = {'symbol-refs': {'enable': True}}


class SymbolRefs(Tree):
    def setUp(self):
        super().setUp()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.write('src/pkg/discover.py',
                   'def _safe(x):\n    return x\n\n'
                   'def _id_shaped(x):\n    return x\n\n'
                   'class Finder:\n    def run(self):\n        pass\n')
        self.write('tests/test_discover.py', 'class RedactTest:\n    pass\n')

    def findings(self, doc, data=ON):
        self.write('README.md', doc)
        subprocess.run(['git', '-C', str(self.root), 'add',
                        'src', 'tests', 'README.md'], check=True)
        return symbol_refs.check_symbol_refs(self.root, self.cfg(data))

    def test_names_present_in_the_file_pass(self):
        self.assertEqual(self.findings(
            '`src/pkg/discover.py` (`_safe`, `_id_shaped`)\n'
            '`tests/test_discover.py` (RedactTest)\n'
            '`discover.py` (Finder.run, `_safe()`)\n'), [])

    def test_absent_name_is_a_hard_finding(self):
        f = self.findings('`src/pkg/discover.py` (`_safe`, `_gone`)\n')
        self.assertEqual([(x.path, x.review) for x in f],
                         [('README.md:1', False)])
        self.assertIn('`_gone`', f[0].message)

    def test_whole_word_only(self):
        # `_saf` is a prefix of `_safe`; `Find` a prefix of `Finder`.
        self.assertEqual(
            len(self.findings('`discover.py` (`_saf`, Find)\n')), 2)

    def test_dotted_name_checks_each_part(self):
        self.assertEqual(len(self.findings('`discover.py` (Finder.gone)\n')),
                         1)

    def test_missing_file_is_left_to_paths(self):
        self.assertEqual(self.findings('`src/pkg/gone.py` (`_safe`)\n'), [])

    def test_prose_parentheses_are_not_name_lists(self):
        self.assertEqual(self.findings(
            '`discover.py` (see below)\n'
            '`discover.py` (removed in v2)\n'
            '`discover.py` (`_safe`, 12 lines)\n'), [])

    def test_opt_out_and_fences(self):
        self.assertEqual(self.findings(
            '`discover.py` (`_old`) <!-- symbol-ok: renamed in v2 -->\n'
            '```\n`discover.py` (`_old`)\n```\n'), [])

    def test_a_line_number_after_the_path_is_dropped(self):
        self.assertEqual(len(self.findings(
            '`discover.py:3` (`_safe`, `_gone`)\n')), 1)

    def test_a_parenthesis_naming_a_file_is_not_a_symbol_list(self):
        # A line from a real consumer doc: the parenthesis is a second
        # file, so it is neither split at the dot nor read against the
        # first file.
        self.write('.agents/settings.json', '{}\n')
        self.assertEqual(self.findings(
            "The only reader is for Claude Code's `.agents/settings.json` "
            "(`reader_claude.py`).\n"), [])

    def test_file_extensions_follow_the_paths_exts_config(self):
        data = {'symbol-refs': {'enable': True}, 'paths': {'exts': ['.rs']}}
        self.assertEqual(len(self.findings('`discover.py` (`gone.py`)\n',
                                           data)), 2)
        self.assertEqual(self.findings('`discover.py` (`gone.rs`)\n',
                                       data), [])

    def test_opt_in(self):
        self.assertEqual(self.findings('`discover.py` (`_gone`)\n', {}), [])

    def test_untracked_file_is_not_read(self):
        self.write('untracked.py', 'x = 1\n')
        self.assertEqual(self.findings('`untracked.py` (`_gone`)\n'), [])
