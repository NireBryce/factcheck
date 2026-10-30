"""docrefs: helper lookup, skill paths and plain mentions, moved paths,
the bare-count rule with its opt-outs, and quoted-section lookup."""
from .helpers import Tree

from factcheck.checks import docrefs


class DocRefs(Tree):
    def setUp(self):
        super().setUp()
        self.write('.agents/scripts/agent.just', 'show:\nwhere:\n')
        self.write('.agents/skills/wiki-sync/SKILL.md', 'x\n')
        self.write('docs/guide.md', '')

    def findings(self, data=None):
        return docrefs.check_docrefs(self.root, self.cfg(data))

    def test_unknown_helper(self):
        self.write('docs/guide.md', 'run `just agent show` and `just agent '
                                    'shipx`.\n')
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'UNKNOWN HELPER')

    def test_helper_placeholder_skipped(self):
        self.write('docs/guide.md', 'run `just agent <helper>`.\n')
        self.assertEqual(self.findings(), [])

    def test_skill_path_and_plain_mention(self):
        self.write('docs/guide.md',
                   'see `.agents/skills/nope-x/` and skill nope-y now.\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['UNKNOWN SKILL', 'UNKNOWN SKILL'])

    def test_plain_skill_requires_hyphen(self):
        self.write('docs/guide.md', 'that skill set is large.\n')
        self.assertEqual(self.findings(), [])

    def test_git_log_line_is_how_a_removed_skill_is_found(self):
        self.write('docs/guide.md',
                   'find it with git log -- .agents/skills/nope-x\n')
        self.assertEqual(self.findings(), [])

    def test_moved_dir_table(self):
        self.write('docs/guide.md', 'guards live in `.claude/hooks/x.sh`.\n')
        f = self.findings({'docrefs': {
            'moved-dirs': {'.claude/hooks': '.agents/hooks'}}})
        self.assertEqual([x.tag for x in f], ['MOVED PATH'])

    def test_bare_count_flagged_and_opted_out(self):
        self.write('docs/guide.md',
                   'The repo has six modules like this.\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['BARE COUNT'])
        for text in ('The repo has six modules: `a`, `b`, `c`, `d`, `e`, '
                     '`f`.\n',
                     'As of 2026-10-01 the repo has six modules.\n',
                     'It has <!-- count-ok: dated --> six modules.\n',
                     'The two modules ship together.\n'):
            self.write('docs/guide.md', text)
            self.assertEqual(self.findings(), [], text)

    def test_bare_count_accompanied_by_named_items(self):
        self.write('docs/guide.md',
                   'Three scripts exist: `a.sh`, `b.sh`, `c.sh`.\n')
        self.assertEqual(self.findings(), [])

    def test_bare_count_skips_fences_and_generated_regions(self):
        self.write('docs/guide.md',
                   '```sh\n# six modules live here\n```\n\n'
                   '<!-- generated:x -- from y -->\n\n'
                   '| What | Files |\n|---|---|\n| six modules | 6 |\n\n'
                   '<!-- /generated -->\n')
        self.assertEqual(self.findings(), [])

    def test_quoted_section_lookup(self):
        self.write('docs/target.md', '# T\n\n## The Real Deal\n')
        self.write('docs/guide.md',
                   'Read `docs/target.md` "The Real Deal" section.\n')
        self.assertEqual(self.findings(), [])
        self.write('docs/guide.md',
                   'Read `docs/target.md` "The Fake Deal" section.\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['UNKNOWN SECTION'])

    def test_ambiguous_page_reference_is_skipped(self):
        self.write('docs/x/dup.md', '# A\n\n## One\n')
        self.write('docs/y/dup.md', '# B\n')
        self.write('docs/guide.md', 'Read dup.md "Nothing" section.\n')
        self.assertEqual(self.findings(), [])

    def test_exempt_paths_skip_bare_counts(self):
        self.write('wiki/thing-history.md', 'six modules moved here.\n')
        self.assertEqual(self.findings(), [])


if __name__ == '__main__':
    unittest.main()
