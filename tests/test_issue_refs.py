"""issue-refs: closed issues cited in pending-sounding sentences, with the
`gh` lookup replaced so no test touches the network."""
from unittest import mock

from .helpers import Tree

from factcheck import capabilities, registry
from factcheck.checks import issue_refs

ON = {'issue-refs': {'enable': True, 'repo': 'o/r'}}
STATES = {24: ('closed', 'completed'), 25: ('open', None),
          26: ('closed', 'not_planned')}


def fake_lookup(calls):
    def lookup(root, repo, number):
        calls.append((repo, number))
        return STATES.get(number)
    return lookup


class IssueRefs(Tree):
    def run_doc(self, doc, data=ON):
        self.write('README.md', doc)
        self.calls = []
        with mock.patch.object(issue_refs, 'lookup',
                               fake_lookup(self.calls)):
            return issue_refs.check_issue_refs(self.root, self.cfg(data))

    def test_closed_issue_in_a_pending_sentence_is_a_review(self):
        f = self.run_doc('Reshaping this repo (the adopt work, issue 24) '
                         'is next.\n')
        self.assertEqual([(x.tag, x.path, x.review) for x in f],
                         [('CLOSED ISSUE', 'README.md:1', True)])
        self.assertIn('#24 is closed (completed)', f[0].message)

    def test_each_pending_phrase(self):
        for phrase in ('Tracked in #24.', 'See issue 24.', 'Until #24 lands.',
                       'Planned: #24.', 'TODO #24', 'The sync work is #24.'):
            with self.subTest(phrase=phrase):
                self.assertEqual(len(self.run_doc(phrase + '\n')), 1)

    def test_closed_issue_in_a_settled_sentence_is_left_alone(self):
        self.assertEqual(self.run_doc('Fixed by #24 in the last release.\n'),
                         [])

    def test_all_reports_every_closed_reference(self):
        data = {'issue-refs': {**ON['issue-refs'], 'all': True}}
        f = self.run_doc('Fixed by #24 and #26.\n', data)
        self.assertEqual(len(f), 2)
        self.assertIn('not planned', f[1].message)

    def test_open_and_unknown_issues_are_not_closed_findings(self):
        self.assertEqual(self.run_doc('Tracked in #25.\n'), [])

    def test_a_failed_lookup_is_reported_once(self):
        f = self.run_doc('Tracked in #99 and again until #99.\n')
        self.assertEqual([(x.tag, x.review) for x in f],
                         [('ISSUE LOOKUP', True)])
        self.assertIn('#99', f[0].message)

    def test_lookups_are_cached_per_run(self):
        self.run_doc('Tracked in #24. See issue 24. Until #24 lands.\n')
        self.assertEqual(self.calls, [('o/r', 24)])

    def test_reference_shapes(self):
        # URL into the repo: read. Another repo's URL, owner/repo#N, an
        # HTML entity and a longer token: not references.
        doc = ('Tracked in https://github.com/o/r/issues/24.\n'
               'Tracked in https://github.com/x/y/issues/24.\n'
               'Tracked in x/y#24.\n'
               'Tracked in &#24; and v#24 and #24x.\n')
        f = self.run_doc(doc)
        self.assertEqual([x.path for x in f], ['README.md:1'])

    def test_fences_and_opt_out(self):
        self.assertEqual(self.run_doc(
            '```\nTracked in #24.\n```\n'
            'Tracked in #24. <!-- issue-ok: history -->\n'), [])

    def test_opt_in(self):
        self.assertEqual(self.run_doc('Tracked in #24.\n', {}), [])

    def test_repo_defaults_to_the_checkouts_own(self):
        data = {'issue-refs': {'enable': True}}
        with mock.patch.object(issue_refs, 'own_repo', lambda r: 'a/b'):
            self.write('README.md', 'Tracked in #24.\n')
            calls = []
            with mock.patch.object(issue_refs, 'lookup', fake_lookup(calls)):
                issue_refs.check_issue_refs(self.root, self.cfg(data))
        self.assertEqual(calls, [('a/b', 24)])

    def test_no_repo_is_a_review_not_a_pass(self):
        data = {'issue-refs': {'enable': True}}
        with mock.patch.object(issue_refs, 'own_repo', lambda r: None):
            f = issue_refs.check_issue_refs(self.root, self.cfg(data))
        self.assertEqual([(x.tag, x.review) for x in f],
                         [('ISSUE-REFS NEEDS REPO', True)])


class GhCapability(Tree):
    def test_the_check_needs_gh_and_is_skipped_without_it(self):
        self.assertEqual(registry.CHECKS['issue-refs'].needs, ('gh',))
        with mock.patch('shutil.which', lambda name: None):
            self.assertFalse(capabilities.available('gh'))
        with mock.patch('shutil.which', lambda name: '/usr/bin/' + name):
            self.assertTrue(capabilities.available('gh'))
