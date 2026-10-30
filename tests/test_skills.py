"""skills: mention-vs-directory, both word orders, and the deliberate
narrowness of what counts as a mention."""
from .helpers import Tree

from factcheck.checks import skills


class Skills(Tree):
    def setUp(self):
        super().setUp()
        self.write('.agents/skills/wiki-sync/SKILL.md', 'x\n')
        self.write('docs/guide.md', '')

    def findings(self, data=None):
        return skills.check_skills(self.root, self.cfg(data))

    def test_both_word_orders_pass_for_a_real_skill(self):
        self.write('docs/guide.md',
                   'use skill `wiki-sync` first; it is the `wiki-sync` '
                   'skill.\n')
        self.assertEqual(self.findings(), [])

    def test_unknown_skill(self):
        self.write('docs/guide.md', 'use skill `wiki-sync` or `ship-lint` '
                                    'skill.\n')
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertIn("'ship-lint'", f[0].message)

    def test_plain_backtick_name_is_not_a_mention(self):
        # "the `name`" without the word skill is deliberately not matched.
        self.write('docs/guide.md', 'run `wiki-sync`.\n')
        self.assertEqual(self.findings(), [])

    def test_no_skills_dir_means_mentions_are_findings(self):
        import shutil
        shutil.rmtree(self.root / '.agents')
        self.write('docs/guide.md', 'skill `wiki-sync`\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['UNKNOWN SKILL'])

    def test_dirs_are_configurable(self):
        self.write('skills/other/SKILL.md', 'x\n')
        self.write('docs/guide.md', 'skill `other`\n')
        self.assertEqual(
            self.findings({'skills': {'dirs': ['skills']}}), [])


if __name__ == '__main__':
    unittest.main()
