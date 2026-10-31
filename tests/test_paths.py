"""paths: backticked filenames that name no tracked file, as REVIEW
findings; suffix matching, ./ and ../ normalisation, opt-outs, opt-in."""
import subprocess

from .helpers import Tree

from factcheck.checks import paths

ON = {'paths': {'enable': True}}


class Paths(Tree):
    def setUp(self):
        super().setUp()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.write('factcheck/checks/links.py', 'x\n')
        self.write('docs/guide.md', 'x\n')
        self.write('untracked.py', 'x\n')

    def findings(self, doc, data=ON):
        self.write('README.md', doc)
        subprocess.run(['git', '-C', str(self.root), 'add',
                        'factcheck', 'docs', 'README.md'], check=True)
        return paths.check_paths(self.root, self.cfg(data))

    def test_full_short_and_relative_mentions_resolve(self):
        self.assertEqual(self.findings(
            '`factcheck/checks/links.py`, `checks/links.py`, `links.py`, '
            '`../docs/guide.md`, `./docs/guide.md`\n'), [])

    def test_missing_and_untracked_are_review_findings(self):
        f = self.findings('see `checks/gone.py`\nand `untracked.py`\n')
        self.assertEqual([(x.path, x.review) for x in f],
                         [('README.md:1', True), ('README.md:2', True)])
        self.assertIn('`checks/gone.py`', f[0].message)

    def test_partial_segment_does_not_match(self):
        # `inks.py` is a suffix of the string but not of a path segment.
        self.assertEqual(len(self.findings('`inks.py`\n')), 1)

    def test_opt_outs(self):
        doc = ('`old.py` was renamed <!-- path-ok: history -->\n'
               '`nixpkgs/modules/x.nix`\n')
        data = {'paths': {'enable': True, 'ignore': ['^nixpkgs/']}}
        self.assertEqual(self.findings(doc, data), [])

    def test_exts_bind_what_counts_as_a_file(self):
        data = {'paths': {'enable': True, 'exts': ['.rs']}}
        self.assertEqual(len(self.findings('`gone.py` `gone.rs`\n', data)), 1)

    def test_off_unless_enabled(self):
        self.assertEqual(self.findings('`gone.py`\n', {}), [])
