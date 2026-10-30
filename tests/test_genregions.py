"""The generated-region engine: region syntax, staleness, hand-column
preservation keyed by row, broken/duplicate/missing regions, and the
fence-masking rule."""
from .helpers import Tree

from factcheck import genregions
from factcheck.checks import generated

REGION_DEF = genregions.Region(
    'test-table', 'wiki/table.md', 'the units/ directory',
    ['Unit', 'Note', 'Role'], 'Unit', ['Role'],
    lambda root: [(f'unit-{n}', {'Unit': f'`unit-{n}`', 'Note': 'x'})
                  for n in 'ab'])

MARKER = REGION_DEF.marker()  # the test's pages must carry the real note


def region_text(table):
    return f'{MARKER}\n\n{table.rstrip()}\n\n<!-- /generated -->'


class GenRegions(Tree):
    def setUp(self):
        super().setUp()
        genregions.REGIONS['test-table'] = REGION_DEF
        self.addCleanup(genregions.REGIONS.pop, 'test-table')
        self.write('units/a', '')

    def findings(self, data=None):
        return generated.check_generated(self.root, self.cfg(data))

    def region_page(self, table, page='wiki/table.md'):
        self.write(page, f'# T\n\n{region_text(table)}\n\n## After\n')

    TABLE = ('| Unit | Note | Role |\n|---|---|---|\n'
             '| `unit-a` | x | does a |\n| `unit-b` | x | does b |\n')

    def test_current_region_passes(self):
        self.region_page(self.TABLE)
        self.assertEqual(self.findings(), [])

    def test_stale_region(self):
        self.region_page(self.TABLE.replace('x | does a', 'OLD | does a'))
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['STALE GENERATED'])

    def test_hand_column_carried_per_row(self):
        self.region_page(self.TABLE.replace('| does a |', '|  |'))
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['EMPTY HAND CELL'])
        self.assertIn("'unit-a'", f[0].message)

    def test_unknown_region(self):
        # Written directly: nesting a foreign region inside region_text's
        # wrapper would just make the outer region malformed.
        self.write('wiki/table.md',
                   '# T\n\n<!-- generated:nope -- from nothing -->\n\n'
                   '| A |\n|---|\n| b |\n\n<!-- /generated -->\n')
        # The unregistered name is flagged, and the real region is nowhere
        # on its home page.
        self.assertEqual(sorted(x.tag for x in self.findings()),
                         ['MISSING REGION', 'UNKNOWN REGION'])

    def test_broken_region_markers(self):
        # A start marker with no end: written directly, since region_text
        # would add the well-formed wrapper this test is about to break.
        self.write('wiki/table.md',
                   '# T\n\n<!-- generated:test-table -- from x -->\n\ntext\n')
        self.assertEqual(sorted(x.tag for x in self.findings()),
                         ['BROKEN REGION', 'MISSING REGION'])

    def test_missing_region_on_its_home_page(self):
        self.write('wiki/other.md', '# O\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['MISSING REGION'])
        self.assertIn('wiki/table.md', f[0].path)

    def test_marker_in_fence_is_not_a_region(self):
        self.write('wiki/table.md',
                   '# T\n\n````md\n'
                   '<!-- generated:test-table -- from x -->\n'
                   '````\n')
        self.assertEqual([x.tag for x in self.findings()], ['MISSING REGION'])

    def test_write_rewrites_and_reports_dropped_rows(self):
        self.region_page(
            self.TABLE
            + '| `unit-gone` | x | precious |\n')
        page = self.root / 'wiki/table.md'
        findings, notes = genregions.run(self.root, [page], write=True)
        self.assertEqual(findings, [])
        self.assertTrue(any('precious' in n for n in notes))
        text = page.read_text()
        self.assertIn('does a', text)       # carried to the matching row
        self.assertIn('precious', str(notes))
        self.assertNotIn('unit-gone', text)


if __name__ == '__main__':
    unittest.main()
