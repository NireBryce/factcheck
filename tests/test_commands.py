"""commands: backticked CLI mentions and command-table cells resolved
against a static command tree; moved commands are REVIEW, absent ones hard."""
from .helpers import Tree

from factcheck.checks import commands

USAGE = ('# Usage\n\n'
         '## `polymorph manage validate <dir>`\n\n'
         '## `polymorph manage conformance`\n\n'
         '## `polymorph discover --json`\n\n'
         '## `polymorph`\n')
TREE = {'file': 'docs/usage.md', 'pattern': r'^## `polymorph (.+)`'}
CFG = {'commands': {'prog': 'polymorph', 'tree': TREE}}


class Commands(Tree):
    def setUp(self):
        super().setUp()
        self.write('docs/usage.md', USAGE)

    def run_doc(self, doc, data=CFG):
        self.write('README.md', doc)
        return commands.check_commands(self.root, self.cfg(data))

    def kinds(self, doc, data=CFG):
        return [(f.tag, f.review) for f in self.run_doc(doc, data)]

    def test_resolving_mentions_are_clean(self):
        self.assertEqual(self.run_doc(
            'Run `polymorph manage validate ./data`, then '
            '`polymorph discover`, `polymorph manage` or `polymorph`.\n'
            '`polymorph manage conformance --strict`\n'), [])

    def test_a_word_after_a_leaf_is_an_argument(self):
        self.assertEqual(self.run_doc('`polymorph discover somefile`\n'), [])

    def test_unknown_command_is_a_hard_finding(self):
        f = self.run_doc('`polymorph frobnicate`\n'
                         '`polymorph manage frobnicate`\n')
        self.assertEqual([(x.path, x.review) for x in f],
                         [('README.md:1', False), ('README.md:2', False)])
        self.assertIn("'frobnicate' is not a subcommand of `polymorph`",
                      f[0].message)
        self.assertIn('`polymorph manage`', f[1].message)

    def test_a_moved_command_is_a_review_naming_where(self):
        f = self.run_doc('`polymorph validate ./data`\n')
        self.assertEqual([(x.tag, x.review) for x in f],
                         [('UNKNOWN COMMAND', True)])
        self.assertIn('`polymorph manage validate`', f[0].message)

    def test_table_cells_under_a_configured_heading(self):
        data = {'commands': {**CFG['commands'],
                             'table-headings': ['Commands']}}
        doc = ('## Commands\n\n| command | does |\n|---|---|\n'
               '| `validate` | checks |\n'
               '| `manage validate` | checks |\n'
               '| `polymorph discover` | finds |\n'
               '| `frobnicate` | nothing |\n\n'
               '## Elsewhere\n\n| `validate` | not judged |\n')
        f = self.run_doc(doc, data)
        self.assertEqual([(x.path, x.review) for x in f],
                         [('README.md:5', True), ('README.md:8', False)])

    def test_table_cells_are_not_read_without_the_heading(self):
        self.assertEqual(self.run_doc('| `validate` | x |\n'), [])

    def test_a_deeper_heading_stays_in_the_section(self):
        data = {'commands': {**CFG['commands'],
                             'table-headings': ['Commands']}}
        doc = '## Commands\n\n### Group\n\n| `validate` | x |\n'
        self.assertEqual(len(self.run_doc(doc, data)), 1)

    def test_empty_tree_is_a_finding_not_a_pass(self):
        self.write('docs/usage.md', '# nothing here\n')
        self.assertEqual(self.kinds('`polymorph validate`\n'),
                         [('COMMANDS TREE', False)])

    def test_unconfigured_is_vacuous(self):
        self.assertEqual(self.run_doc('`polymorph nope`\n', {}), [])

    def test_fences_and_opt_out(self):
        self.assertEqual(self.run_doc(
            '```\n`polymorph nope`\n```\n'
            '`polymorph old` was removed <!-- command-ok: history -->\n'), [])

    def test_plugin_tree_source(self):
        @commands.register_tree('fixture')
        def tree(root, cfg):
            return ['manage validate', 'manage conformance', ('discover',)]
        self.addCleanup(commands.TREES.pop, 'fixture')
        data = {'commands': {'prog': 'polymorph',
                             'tree': {'plugin': 'fixture'}}}
        self.assertEqual(self.kinds('`polymorph manage validate` '
                                    '`polymorph discover` '
                                    '`polymorph validate`\n', data),
                         [('UNKNOWN COMMAND', True)])

    def test_prog_prefix_must_be_whole(self):
        self.assertEqual(self.run_doc('`polymorphic nope`\n'), [])
