"""conflicts: leftover merge markers in docs, and what is not one."""
from .helpers import Tree

from factcheck.checks import conflicts

CONFLICT = ('intro\n'
            '<<<<<<< HEAD\n'
            '| `a` | ours |\n'
            '=======\n'
            '| `a` | theirs |\n'
            '>>>>>>> origin/main\n'
            'outro\n')


class Conflicts(Tree):
    def findings(self, text):
        self.write('README.md', text)
        return conflicts.check_conflicts(self.root, self.cfg())

    def test_a_left_over_hunk_is_three_findings(self):
        f = self.findings(CONFLICT)
        self.assertEqual([x.path for x in f],
                         ['README.md:2', 'README.md:4', 'README.md:6'])
        self.assertEqual({x.tag for x in f}, {'CONFLICT MARKER'})
        self.assertFalse(any(x.review for x in f))

    def test_a_half_resolved_hunk_still_shows(self):
        # Kept one side, deleted the closing marker only.
        text = 'a\n<<<<<<< HEAD\nours\n=======\ntheirs\n'
        self.assertEqual(len(self.findings(text)), 2)

    def test_a_setext_underline_is_not_a_marker(self):
        self.assertEqual(self.findings('Title\n=======\n\ntext\n'), [])

    def test_markers_inside_a_fence_are_review(self):
        f = self.findings('```toml\n' + CONFLICT + '```\n')
        self.assertEqual([(x.path, x.review) for x in f],
                         [('README.md:3', True), ('README.md:5', True),
                          ('README.md:7', True)])
        self.assertIn('in fenced code', f[0].message)

    def test_a_conflict_ok_fence_is_skipped(self):
        text = ('<!-- conflict-ok: shows a conflict -->\n```\n' + CONFLICT
                + '```\n\n```\n<<<<<<< HEAD\n```\n')
        f = self.findings(text)
        # Only the unmarked second fence reports.
        self.assertEqual([(x.path, x.review) for x in f],
                         [('README.md:13', True)])

    def test_a_diff3_base_marker_is_reported(self):
        text = ('<<<<<<< HEAD\nours\n||||||| base\nold\n=======\n'
                'theirs\n>>>>>>> main\n')
        self.assertEqual([x.path for x in self.findings(text)],
                         ['README.md:1', 'README.md:3', 'README.md:5',
                          'README.md:7'])

    def test_a_bare_base_marker_outside_a_hunk_is_not_reported(self):
        self.assertEqual(self.findings('a\n||||||| base\nb\n'), [])

    def test_lookalikes_are_not_markers(self):
        self.assertEqual(self.findings(
            '<<<<<<<< eight\n>>>>>>>x\nsee <<<<<<< mid-line\n'), [])
