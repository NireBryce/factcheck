"""anchors: the fragment half of a link, against GitHub's real slug
behavior."""
from .helpers import Tree

from factcheck.checks import anchors

PAGE = """# Page

## The two apps

content

## Setup

## Setup
"""


class Anchors(Tree):
    def findings(self):
        return anchors.check_anchors(self.root, self.cfg())

    def test_clean(self):
        self.write('docs/page.md', PAGE)
        self.write('docs/a.md',
                   '# Page\n'
                   '[apps](page.md#the-two-apps)\n'
                   '[here](#page)\n'
                   '[plain](page.md)\n')
        self.assertEqual(self.findings(), [])

    def test_broken_anchor(self):
        self.write('docs/page.md', PAGE)
        self.write('docs/a.md', '[x](page.md#the-two-apps-)\n')
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'BROKEN ANCHOR')

    def test_repeated_heading_counter(self):
        # The second `## Setup` renders as #setup-1 on GitHub.
        self.write('docs/page.md', PAGE)
        self.write('docs/a.md', '[s](page.md#setup-1)\n')
        self.assertEqual(self.findings(), [])

    def test_no_finding_for_a_file_links_already_reports(self):
        self.write('docs/a.md', '[x](no-page.md#section)\n')
        self.assertEqual(self.findings(), [])

    def test_slug_punctuation_case(self):
        self.write('docs/page.md', '# P\n\n## `VMs/_lib/libvirt-vm.nix`\n')
        self.write('docs/a.md', '[x](page.md#vms_liblibvirt-vmnix)\n')
        self.assertEqual(self.findings(), [])


if __name__ == '__main__':
    unittest.main()


class AnchorsOutsideCodeOnly(Tree):
    def test_fragment_in_code_is_not_checked(self):
        self.write('docs/a.md', '# A\n\nSee `[x](#nowhere)` and\n\n'
                   '```\n[y](#nowhere)\n```\n')
        self.assertEqual(anchors.check_anchors(self.root, self.cfg()), [])
