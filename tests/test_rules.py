"""rules: frontmatter shape, dead globs (tracked, not just on disk), and
the pointer-file requirement."""
import subprocess
from .helpers import Tree

from factcheck.checks import rules

GOOD = '''---
paths:
  - "src/**/*.nix"
  - "**/*.{sh,py}"
---

# A rule
'''


class Rules(Tree):
    def setUp(self):
        super().setUp()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.write('src/a/b.nix', '{ }\n')
        self.write('tools/run.sh', 'true\n')
        self.write('AGENTS.md', 'Rules: `.agents/rules/good.md`.\n')
        self.write('.agents/rules/good.md', GOOD)
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)

    def findings(self, data=None):
        return rules.check_rules(self.root, self.cfg(data))

    def test_clean(self):
        self.assertEqual(self.findings(), [])

    def test_dead_glob(self):
        self.write('.agents/rules/good.md',
                   GOOD.replace('src/**/*.nix', 'nope/**'))
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'DEAD RULE GLOB')
        self.assertIn("'nope/**'", f[0].message)

    def test_untracked_match_is_dead(self):
        # On disk but not in git: clones never see it, so the rule would
        # never load where it matters.
        self.write('src/other.nix', '{ }\n')
        self.write('.agents/rules/good.md',
                   GOOD.replace('src/**/*.nix', 'src/other.nix'))
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['DEAD RULE GLOB'])

    def test_unlisted_rule(self):
        self.write('AGENTS.md', 'nothing here\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['UNLISTED RULE'])

    def test_no_frontmatter(self):
        self.write('.agents/rules/good.md', '# just prose\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['RULE FRONTMATTER'])

    def test_empty_paths(self):
        self.write('.agents/rules/good.md', '---\npaths:\n---\n\n# r\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['RULE FRONTMATTER'])

    def test_unknown_field(self):
        self.write('.agents/rules/good.md',
                   '---\npaths:\n  - "src/**/*.nix"\ndescription: d\n---\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['RULE FRONTMATTER'])

    def test_dir_and_pointer_are_configurable(self):
        self.write('docs/rules/x.md',
                   GOOD.replace('src/**/*.nix', 'src/**/*.nix'))
        self.write('GUIDE.md', 'see `docs/rules/x.md`\n')
        self.write('.agents/rules/good.md', GOOD)
        f = self.findings({'rules': {'dir': 'docs/rules',
                                     'pointer': 'GUIDE.md'}})
        self.assertEqual(f, [])


if __name__ == '__main__':
    unittest.main()
