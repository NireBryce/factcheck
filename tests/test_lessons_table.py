"""lessons-index, table shape: a `| Lesson | Rule | Home |` page checked for
empty Homes, Homes naming no skill or file, and a REVIEW for a Home that
carries none of the rule's terms."""
import subprocess

from .helpers import Tree

from factcheck.checks import lessons

CFG = {'lessons': {'page': 'docs/lessons.md', 'shape': 'table'}}
HEAD = '| Lesson | Rule | Home |\n|---|---|---|\n'


class LessonsTable(Tree):
    def setUp(self):
        super().setUp()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.write('.agents/skills/ship/SKILL.md',
                   '# Landing work\nNever merge without a green pipeline; '
                   'confirm the branch deletion with the user.\n')
        self.write('.agents/skills/other/SKILL.md',
                   '# Something else entirely\nFormatting conventions.\n')
        self.write('src/discover.py', 'def redact_secrets(): pass\n')

    def run_table(self, rows, data=CFG, head=HEAD):
        self.write('docs/lessons.md', f'# Lessons\n\n{head}{rows}')
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'],
                       check=True)
        return lessons.check_lessons_index(self.root, self.cfg(data))

    def tags(self, rows, **kw):
        return sorted(f.tag for f in self.run_table(rows, **kw))

    def test_clean_table(self):
        self.assertEqual(self.run_table(
            '| Landing | confirm branch deletion and pipeline status before merging | '
            'skill `ship` |\n'
            '| Secrets | redact secrets before logging | '
            '`src/discover.py` (`redact_secrets`) |\n'), [])

    def test_empty_home_is_a_hard_finding(self):
        f = self.run_table('| Landing | a rule about pipelines and deployments | |\n')
        self.assertEqual([(x.tag, x.review) for x in f],
                         [('EMPTY HOME', False)])
        self.assertEqual(f[0].path, 'docs/lessons.md:5')

    def test_unknown_skill_and_missing_file_are_hard_findings(self):
        self.assertEqual(self.tags(
            '| A | rule about pipelines and deployments | skill `gone` |\n'
            '| B | rule about pipelines and deployments | `src/gone.py` |\n'),
            ['UNKNOWN HOME', 'UNKNOWN HOME'])

    def test_home_that_never_states_the_rule_is_a_review(self):
        # The Home exists and resolves; it shares nothing with the rule.
        f = self.run_table(
            '| Landing | confirm branch deletion and pipeline status before merging | '
            'skill `other` |\n')
        self.assertEqual([(x.tag, x.review) for x in f],
                         [('THIN HOME', True)])
        self.assertIn('shares 0 of the rule', f[0].message)

    def test_min_overlap_is_configurable(self):
        rows = ('| Landing | confirm branch deletion and pipeline status before merging'
                ' | skill `ship` |\n')
        self.assertEqual(self.tags(rows), [])
        data = {'lessons': {**CFG['lessons'], 'min-overlap': 9}}
        self.assertEqual(self.tags(rows, data=data), ['THIN HOME'])

    def test_inflections_match_on_the_first_six_letters(self):
        self.assertEqual(self.tags(
            '| S | redaction of secrets before logging | '
            '`src/discover.py` |\n'), [])

    def test_a_rule_with_too_few_terms_is_not_judged(self):
        self.assertEqual(self.tags('| A | be kind | skill `other` |\n'), [])

    def test_escaped_pipe_stays_in_its_cell(self):
        self.assertEqual(self.tags(
            '| A | confirm branch deletion and pipeline status before merging \\| ever | '
            'skill `ship` |\n'), [])

    def test_cell_count_mismatch_is_malformed(self):
        self.assertEqual(self.tags('| A | only two cells |\n'),
                         ['MALFORMED LESSON'])

    def test_no_matching_table(self):
        self.assertEqual(self.tags('', head='| Name | Why |\n|---|---|\n'),
                         ['LESSON TABLE'])

    def test_a_table_inside_a_fence_is_not_the_table(self):
        self.write('docs/lessons.md', f'```\n{HEAD}| A | r | |\n```\n')
        self.assertEqual(
            [f.tag for f in lessons.check_lessons_index(
                self.root, self.cfg())], [])  # unconfigured: vacuous
        self.assertEqual(
            [f.tag for f in lessons.check_lessons_index(
                self.root, self.cfg(CFG))], ['LESSON TABLE'])

    def test_custom_columns(self):
        data = {'lessons': {**CFG['lessons'], 'columns': ['Why', 'Where'],
                            'rule-column': 'Why', 'home-column': 'Where'}}
        self.assertEqual(self.tags(
            '| confirm branch deletion and pipeline status before merging | skill `ship` |\n',
            data=data, head='| Why | Where |\n|---|---|\n'), [])

    def test_unknown_shape(self):
        data = {'lessons': {'page': 'docs/lessons.md', 'shape': 'grid'}}
        self.assertEqual(self.tags('', data=data), ['LESSONS SHAPE'])
