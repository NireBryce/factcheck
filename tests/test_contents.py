"""contents + the fix-contents fixer: staleness, the missing-block half
(the one whose absence once hid a deletion), exemptions, and the fixer's
bullet-only replacement guarantee."""
from .helpers import Tree

from factcheck.checks.contents import (
    check_contents, expected_contents_items, fix_contents)

PAGE = """# Page

_Last modified: 2026-10-01_

## Contents

- [Alpha](#alpha)
- [Beta](#beta)

## Alpha

text

## Beta

text
"""


class Contents(Tree):
    def write_page(self, text):
        return self.write('wiki/page.md', text)

    def findings(self, data=None):
        return check_contents(self.root, self.cfg(data))

    def fix(self, *files):
        fix_contents(self.root, self.cfg(), list(files))

    def test_clean(self):
        self.write_page(PAGE)
        self.assertEqual(self.findings(), [])

    def test_stale_contents(self):
        self.write_page(PAGE.replace('- [Beta](#beta)\n', ''))
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'STALE CONTENTS')

    def test_missing_contents(self):
        self.write_page(PAGE.split('## Contents')[0] + '## Alpha\n\ntext\n')
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'MISSING CONTENTS')

    def test_exempt_page_needs_no_block(self):
        self.write('wiki/other-for-agents.md', '# T\n\n## A\n\n## B\n')
        self.assertEqual(self.findings(), [])

    def test_exempt_list_is_configurable(self):
        self.write_page(PAGE.split('## Contents')[0] + '## Alpha\n')
        f = self.findings({'contents': {'exempt': [r'wiki/page\.md']}})
        self.assertEqual(f, [])

    def test_page_without_h2_is_skipped(self):
        self.write_page('# Title\n\njust prose\n')
        self.assertEqual(self.findings(), [])

    def test_expected_items_are_h2_only_and_skip_contents_itself(self):
        text = '# T\n\n## Contents\n\n## One\n\n### Sub\n\n## Two\n'
        self.assertEqual([t for t, _ in expected_contents_items(text)],
                         ['One', 'Two'])


class FixContents(Tree):
    def fix(self, page):
        from factcheck.checks.contents import fix_contents
        fix_contents(self.root, self.cfg(), [str(self.root / page)])

    def test_inserts_block_after_title_and_date(self):
        self.write('wiki/p.md',
                   '# P\n\n_Last modified: 2026-10-01_\n\n'
                   'intro\n\n## One\n\n## Two\n')
        self.fix('wiki/p.md')
        text = (self.root / 'wiki/p.md').read_text()
        self.assertEqual(text,
                         '# P\n\n_Last modified: 2026-10-01_\n\n'
                         'intro\n\n'
                         '## Contents\n\n- [One](#one)\n- [Two](#two)\n\n'
                         '## One\n\n## Two\n')

    def test_replaces_only_the_bullet_run(self):
        # The NEXT_HEADING-span version of this fixer once deleted the
        # prose under the block; bullet-only replacement must keep it.
        self.write('wiki/p.md',
                   '# P\n\n## Contents\n\n- [Stale](#stale)\n\n'
                   'kept prose\n\n## Real\n')
        self.fix('wiki/p.md')
        text = (self.root / 'wiki/p.md').read_text()
        self.assertIn('kept prose', text)
        self.assertIn('- [Real](#real)', text)
        self.assertNotIn('Stale', text)

    def test_idempotent(self):
        self.write('wiki/p.md', '# P\n\n## One\n')
        self.fix('wiki/p.md')
        once = (self.root / 'wiki/p.md').read_text()
        self.fix('wiki/p.md')
        self.assertEqual((self.root / 'wiki/p.md').read_text(), once)
        self.assertIn('## Contents', once)

    def test_declines_a_page_with_no_h2(self):
        self.write('wiki/p.md', '# P\n\nprose only\n')
        self.fix('wiki/p.md')
        self.assertEqual((self.root / 'wiki/p.md').read_text(),
                         '# P\n\nprose only\n')


if __name__ == '__main__':
    unittest.main()
