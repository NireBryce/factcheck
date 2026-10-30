"""dates: line shape and position, and the future-date guard."""
import datetime
from .helpers import Tree

from factcheck.checks import dates


class Dates(Tree):
    def findings(self, data=None):
        return dates.check_dates(self.root, self.cfg(data))

    def test_clean(self):
        self.write('wiki/p.md', '# P\n\n_Last modified: 2026-10-01_\n\n## A\n')
        self.assertEqual(self.findings(), [])

    def test_missing_line(self):
        self.write('wiki/p.md', '# P\n\n## A\n')
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'MISSING LAST-MODIFIED')

    def test_wrong_shape_is_missing(self):
        # A stray trailing word or missing underscore is exactly the drift
        # this check exists to catch, so it is not "close enough".
        for line in ('_Last modified: 2026-10-01_ today\n',
                     'Last modified: 2026-10-01\n'):
            self.write('wiki/p.md', f'# P\n\n{line}\n## A\n')
            f = self.findings()
            self.assertEqual(len(f), 1, line)
            self.assertEqual(f[0].tag, 'MISSING LAST-MODIFIED', line)

    def test_future_date(self):
        future = datetime.date.today() + datetime.timedelta(days=2)
        self.write('wiki/p.md',
                   f'# P\n\n_Last modified: {future}_\n\n## A\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['FUTURE DATE'])

    def test_no_title_line_is_skipped(self):
        self.write('notes.md', 'plain text, no markdown title\n')
        self.assertEqual(self.findings(), [])

    def test_line_format_is_configurable(self):
        cfg = {'dates': {'line': 'Modified: {date}'}}
        self.write('wiki/p.md', '# P\n\nModified: 2026-10-01\n\n## A\n')
        self.assertEqual(self.findings(cfg), [])
        self.write('wiki/p.md', '# P\n\n## A\n')
        f = self.findings(cfg)
        self.assertEqual([x.tag for x in f], ['MISSING LAST-MODIFIED'])


if __name__ == '__main__':
    unittest.main()
