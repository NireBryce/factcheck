"""siblings: the staleness guard, the reviewed-line escape hatch, the
budget REVIEW, and the missing/orphan/link halves."""
import datetime
from .helpers import Tree

from factcheck.checks import siblings

TODAY = datetime.date.today()
OLD = TODAY - datetime.timedelta(days=7)
OLDER = TODAY - datetime.timedelta(days=14)

# Over the default 1000-word line where "requires a sibling" bites.
LONG_BODY = 'word ' * 1100
SIB_BODY = 'x ' * 100


def page(date, body, title='# P', extra=''):
    return f'{title}\n\n_Last modified: {date}_\n\n## A\n\n{body}\n{extra}'


def sib_page(date, reviewed=None):
    """A sibling with the reviewed line where it belongs -- directly under
    the last-modified line (the read window is the file's first 8 lines,
    so a reviewed line at the bottom of a long page is decoration, not an
    escape hatch)."""
    line = f'\n_Sibling reviewed: {reviewed} -- check_\n' if reviewed else ''
    return (f'# P\n\n_Last modified: {date}_{line}\n\n## A\n\n{SIB_BODY}\n\n'
            f'[source](guide.md)\n')


class Siblings(Tree):
    def setUp(self):
        super().setUp()
        # A short source below the sibling-required word line, so tests
        # exercise one page at a time.
        self.write('wiki/guide.md', page(OLD, 'short'))

    def write_pair(self, src_date, sib_date, sib_text=None, src_text=None,
                   src_body=LONG_BODY):
        if src_text is None:
            src_text = page(src_date, src_body,
                            extra='\n[condensed](guide-for-agents.md)\n')
        if sib_text is None:
            sib_text = sib_page(sib_date)
        self.write('wiki/guide.md', src_text)
        self.write('wiki/guide-for-agents.md', sib_text)

    def findings(self, data=None):
        return siblings.check_siblings(self.root, self.cfg(data))

    def test_fresh_pair_passes(self):
        self.write_pair(OLD, OLD)
        self.assertEqual(self.findings(), [])

    def test_stale_sibling(self):
        self.write_pair(OLD, OLDER)
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'STALE SIBLING')

    def test_reviewed_line_satisfies_staleness(self):
        self.write_pair(OLD, OLDER,
                        sib_text=sib_page(OLDER, reviewed=OLD))
        self.assertEqual(self.findings(), [])

    def test_reviewed_line_older_than_source_is_stale(self):
        self.write_pair(OLD, OLDER,
                        sib_text=sib_page(OLDER, reviewed=OLDER))
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['STALE SIBLING'])

    def test_future_review_date_does_not_satisfy_the_guard(self):
        future = TODAY + datetime.timedelta(days=2)
        self.write_pair(OLD, OLDER,
                        sib_text=sib_page(OLDER, reviewed=future))
        f = self.findings()
        # The forged date is called out, and it satisfies nothing: the
        # pair is still stale underneath it.
        self.assertEqual(sorted(x.tag for x in f),
                         ['FUTURE REVIEW', 'STALE SIBLING'])

    def test_orphan_sibling(self):
        self.write('wiki/lost-for-agents.md', page(OLD, 'x'))
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['ORPHAN SIBLING'])

    def test_missing_sibling_over_word_line(self):
        self.write('wiki/long.md', page(OLD, LONG_BODY))
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['MISSING SIBLING'])
        self.assertIn('long.md', f[0].path)

    def test_quick_facts_fold_passes(self):
        self.write('wiki/long.md',
                   f'# P\n\n_Last modified: {OLD}_\n\n'
                   f'## Quick facts\n\n{LONG_BODY}\n')
        self.assertEqual(self.findings(), [])

    def test_history_pages_exempt_from_requiring_a_sibling(self):
        self.write('wiki/long-history.md', page(OLD, LONG_BODY))
        self.assertEqual(self.findings(), [])

    def test_budget_overrun_is_review_not_hard(self):
        self.write_pair(OLD, OLD, sib_text=(
            sib_page(OLD).replace(SIB_BODY, 'word ' * 600)))
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertTrue(f[0].review)

    def test_back_links_required_both_ways(self):
        self.write_pair(OLD, OLD, src_text=page(OLD, LONG_BODY),
                        sib_text=page(OLD, SIB_BODY))
        f = self.findings()
        self.assertEqual(sorted(x.tag for x in f),
                         ['NO SIBLING LINK', 'NO SOURCE LINK'])

    def test_thresholds_are_configurable(self):
        self.write('wiki/short.md', page(OLD, 'word ' * 30))
        f = self.findings({'siblings': {'required-words': 10}})
        self.assertEqual([x.tag for x in f], ['MISSING SIBLING'])

    def test_suffix_is_configurable(self):
        self.write_pair(
            OLD, OLD,
            src_text=page(OLD, LONG_BODY,
                          extra='\n[condensed](guide-dense.md)\n'))
        (self.root / 'wiki/guide-for-agents.md').rename(
            self.root / 'wiki/guide-dense.md')
        self.assertEqual(
            self.findings({'siblings': {'suffix': '-dense'}}), [])


if __name__ == '__main__':
    unittest.main()
