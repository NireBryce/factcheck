"""links: a clean tree proves nothing -- each test breaks one link."""
from .helpers import Tree

from factcheck.checks import links


class Links(Tree):
    def findings(self):
        return links.check_links(self.root, self.cfg())

    def test_clean(self):
        self.write('docs/a.md', '[b](b.md)\n')
        self.write('docs/b.md', 'x\n')
        self.assertEqual(self.findings(), [])

    def test_broken_link(self):
        self.write('docs/a.md', '[gone](gone.md)\n')
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'BROKEN LINK')
        self.assertIn('gone.md', f[0].message)

    def test_external_and_anchor_targets_skipped(self):
        self.write('docs/a.md',
                   '[site](https://x.y/z)\n'
                   '[mail](mailto:a@b.c)\n'
                   '[here](#see-also)\n'
                   '[bare](#)\n')
        self.assertEqual(self.findings(), [])

    def test_percent_encoded_target_decoded(self):
        self.write('dir name/file.md', 'x\n')
        self.write('docs/a.md', '[f](../dir%20name/file.md)\n')
        self.assertEqual(self.findings(), [])

    def test_anchor_on_broken_file_is_links_not_anchors(self):
        self.write('docs/a.md', '[x](no-page.md#section)\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['BROKEN LINK'])


if __name__ == '__main__':
    unittest.main()


class LinksOutsideCodeOnly(Tree):
    """A link-shaped string in code is literal text on GitHub, not a link:
    it isn't checked, and a real link next to it still is."""

    def findings(self, text):
        self.write('docs/a.md', text)
        return [f.message for f in links.check_links(self.root, self.cfg())]

    def test_code_span_is_not_a_link(self):
        self.assertEqual(self.findings('the shape `[t](dir/N-x.md)` here\n'),
                         [])

    def test_double_backtick_span_with_a_backtick_inside(self):
        self.assertEqual(self.findings('``[a`b](gone.md)``\n'), [])

    def test_fenced_block_is_not_a_link(self):
        self.assertEqual(self.findings('```md\n[t](gone.md)\n```\n'
                                       '~~~\n[t](gone.md)\n~~~\n'), [])

    def test_real_link_next_to_code_is_still_checked(self):
        f = self.findings('`code` then [t](gone.md) and `more`\n')
        self.assertEqual(len(f), 1)
        self.assertIn('gone.md', f[0])

    def test_unclosed_or_escaped_backtick_does_not_hide_a_link(self):
        self.assertEqual(len(self.findings('a ` stray tick [t](gone.md)\n')),
                         1)
        self.assertEqual(len(self.findings('\\`[t](gone.md)\\`\n')), 1)

    def test_a_span_does_not_cross_a_blank_line(self):
        # The backticks are in different paragraphs, so neither opens a
        # span and the link between them is real.
        self.assertEqual(len(self.findings('a `\n\n[t](gone.md)\n\nb `\n')),
                         1)
