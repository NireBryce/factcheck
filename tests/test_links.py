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
