"""Fence handling and slug computation, against the cases that broke the
ancestor tool: its scripts once disagreed with each other (and with
CommonMark) on every one of these."""
import unittest

from factcheck.mdcore import fences
from factcheck.mdcore.headings import iter_headings
from factcheck.mdcore.slugs import github_slug


def fenced_lines(text):
    return [line for _, line, in_fence in fences.iter_lines(text) if in_fence]


class FenceHandling(unittest.TestCase):
    def test_indented_fence_in_list_item(self):
        self.assertIn('   just indented-recipe', fenced_lines(
            '1. step\n\n   ```sh\n   just indented-recipe\n   ```\n'))

    def test_tilde_fence(self):
        self.assertIn('just tilde-recipe', fenced_lines(
            '~~~\njust tilde-recipe\n~~~\n'))

    def test_longer_fence_is_not_closed_by_a_shorter_one(self):
        self.assertIn('just inner-recipe', fenced_lines(
            '````md\n```\njust inner-recipe\n```\n````\n'))

    def test_other_fence_character_does_not_close(self):
        self.assertIn('just mixed-recipe', fenced_lines(
            '```\n~~~\njust mixed-recipe\n```\n'))

    def test_four_space_indent_is_not_a_fence(self):
        self.assertEqual(fenced_lines('    ```\njust prose-recipe\n'), [])

    def test_prose_after_closing_fence_is_not_read(self):
        self.assertEqual(fenced_lines('```\nx\n```\njust after-recipe\n'),
                         ['```', 'x', '```'])

    def test_backtick_in_info_string_is_inline_code_not_a_fence(self):
        self.assertEqual(fenced_lines('```foo``` bar\njust x\n'), [])

    def test_unclosed_fence_runs_to_the_end(self):
        self.assertIn('just never-closed', fenced_lines('```\njust never-closed\n'))

    def test_blank_fences_preserves_offsets(self):
        text = 'before\n```sh\nsecret\n```\nafter\n'
        blanked = fences.blank_fences(text)
        self.assertEqual(len(blanked), len(text))
        self.assertEqual(blanked.splitlines()[-1], 'after')
        self.assertNotIn('secret', blanked)


class HeadingIteration(unittest.TestCase):
    def test_shell_comment_in_fence_is_not_a_heading(self):
        text = '# Title\n\n```sh\n# or, one-off:\n```\n\n## Real\n'
        self.assertEqual(list(iter_headings(text)),
                         [(1, 'Title'), (2, 'Real')])


class GitHubSlugs(unittest.TestCase):
    def test_plain(self):
        seen = {}
        self.assertEqual(github_slug('The two apps', seen), 'the-two-apps')

    def test_punctuation_disappears_without_replacement(self):
        seen = {}
        self.assertEqual(github_slug('`VMs/_lib/libvirt-vm.nix`', seen),
                         'vms_liblibvirt-vmnix')

    def test_repeated_headings_get_counters_in_document_order(self):
        seen = {}
        self.assertEqual(github_slug('Setup', seen), 'setup')
        self.assertEqual(github_slug('Other', seen), 'other')
        self.assertEqual(github_slug('Setup', seen), 'setup-1')

    def test_removed_char_between_spaces_leaves_double_hyphen(self):
        # The colon disappears with nothing in its place, so the two spaces
        # it sat between become adjacent -- and each becomes a hyphen.
        seen = {}
        self.assertEqual(github_slug('a : b', seen), 'a--b')
        # Kept characters pass through: literal hyphens plus the spaces
        # around them.
        self.assertEqual(github_slug('a -- b', seen), 'a----b')


if __name__ == '__main__':
    unittest.main()
