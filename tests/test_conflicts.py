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

    def test_markers_inside_a_fence_are_an_example(self):
        self.assertEqual(self.findings('```\n' + CONFLICT + '```\n'), [])

    def test_lookalikes_are_not_markers(self):
        self.assertEqual(self.findings(
            '<<<<<<<< eight\n>>>>>>>x\nsee <<<<<<< mid-line\n'), [])
