"""restatement: shared 8-gram prose between docs as REVIEW findings;
what's excluded from matching, sibling pairs held back, exempt pairs,
the floor, and opt-in."""
from .helpers import Tree

from factcheck.checks import restatement

ON = {'restatement': {'enable': True}, 'scopes': {'docs': ['**/*.md']}}
FACT = ('the session start hook wires the git hooks path when it is unset '
        'and reports a different value without changing it')


class Restatement(Tree):
    def findings(self, data=ON):
        return restatement.check_restatement(self.root, self.cfg(data))

    def test_shared_prose_is_one_review_finding_per_pair(self):
        self.write('AGENTS.md', f'# A\n\nIntro words here. {FACT}.\n')
        self.write('docs/guide.md', f'# G\n\nElsewhere, {FACT}. Also more.\n')
        self.write('docs/other.md', '# O\n\nnothing in common at all here.\n')
        f = self.findings()
        self.assertEqual([(x.path, x.review) for x in f],
                         [('AGENTS.md', True)])
        self.assertIn('docs/guide.md', f[0].message)
        self.assertIn('AGENTS.md:3', f[0].message)

    def test_under_the_floor_is_not_reported(self):
        short = 'one two three four five six seven eight nine'
        self.write('a.md', f'{short}\n')
        self.write('b.md', f'{short}\n')
        self.assertEqual(self.findings(), [])
        data = {**ON, 'restatement': {'enable': True, 'min-words': 9}}
        self.assertEqual(len(self.findings(data)), 1)

    def test_fences_titles_and_contents_do_not_count(self):
        body = (f'# {FACT}\n\n## Contents\n\n- {FACT}\n\n## Body\n\n'
                f'```sh\n{FACT}\n```\n')
        self.write('a.md', body)
        self.write('b.md', body)
        self.assertEqual(self.findings(), [])

    def test_sibling_pairs_held_back_unless_asked(self):
        self.write('docs/page.md', f'{FACT}\n')
        self.write('docs/page-for-agents.md', f'{FACT}\n')
        self.assertEqual(self.findings(), [])
        data = {**ON, 'restatement': {'enable': True, 'siblings': True}}
        self.assertEqual(len(self.findings(data)), 1)

    def test_exempt_pairs_either_order(self):
        self.write('docs/lessons.md', f'{FACT}\n')
        self.write('docs/lessons/1-x.md', f'{FACT}\n')
        data = {**ON, 'restatement': {
            'enable': True,
            'exempt-pairs': [['^docs/lessons/', r'^docs/lessons\.md$']]}}
        self.assertEqual(self.findings(data), [])
        self.assertEqual(len(self.findings()), 1)

    def test_off_unless_enabled(self):
        self.write('a.md', f'{FACT}\n')
        self.write('b.md', f'{FACT}\n')
        self.assertEqual(self.findings({'scopes': ON['scopes']}), [])
