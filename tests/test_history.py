"""history: the ghost-lesson check -- a number planted in a fixture's
git history, removed from the index, still cited, and the shapes that
must not read as ghosts (re-added, migrated entry-to-section, uncited,
self-cited)."""
import subprocess
import unittest

from .helpers import Tree

from factcheck import gitfiles
from factcheck.checks import history

PAGE_V1 = """# Lessons

- **§1** [First](l/1-first.md) — first rule.
- **§2** [Second](l/2-second.md) — second rule.
"""

CITE = 'The two-host rule is §2, and §1 grounds it.\n'


def git(root, *args):
    subprocess.run(('git', '-C', str(root), *args), check=True,
                   capture_output=True)


def commit(root, msg):
    git(root, 'add', '-A')
    git(root, '-c', 'user.email=t@t', '-c', 'user.name=t',
        'commit', '-qm', msg)


class History(Tree):
    def plant(self):
        """Two lessons, a doc citing both, then a commit that removes
        §2 from the index. Returns the removal's short sha."""
        git(self.root, 'init', '-q')
        self.write('wiki/lessons.md', PAGE_V1)
        self.write('docs/cite.md', CITE)
        commit(self.root, 'two lessons')
        self.write('wiki/lessons.md',
                   PAGE_V1.replace('- **§2** [Second](l/2-second.md) — second rule.\n', ''))
        commit(self.root, 'drop the second lesson')
        log = subprocess.run(
            ('git', '-C', str(self.root), 'log', '--format=%h', '-2'),
            capture_output=True, text=True, check=True)
        return log.stdout.splitlines()[0]

    def run_check(self, data):
        return history.check_history(self.root, self.cfg(data))

    def cfg_data(self, **extra):
        data = {'scopes': {'docs': ['docs/*.md', 'wiki/lessons.md']},
                'lessons': {'page': 'wiki/lessons.md'},
                'history': {'enable': True}}
        data.update(extra)
        return data

    def test_cited_removed_number_is_a_review_finding(self):
        sha = self.plant()
        f = self.run_check(self.cfg_data())
        self.assertEqual([x.tag for x in f], ['GHOST LESSON'])
        self.assertTrue(f[0].review)
        self.assertIn('cites §2', f[0].message)
        self.assertIn(sha, f[0].message)
        # §1 still stands; only the §2 citation is a ghost
        self.assertIn('docs/cite.md', f[0].path)

    def test_readded_number_is_not_a_ghost(self):
        self.plant()
        self.write('wiki/lessons.md', PAGE_V1)
        commit(self.root, 'restore the second lesson')
        self.assertEqual(self.run_check(self.cfg_data()), [])

    def test_entry_to_section_migration_is_not_a_ghost(self):
        # The consumer's restructure: the **§N** entry shape leaves and
        # the same number arrives as a `## N.` section, in one commit.
        self.plant()
        self.write('wiki/lessons.md',
                   '# Lessons\n\n## 1. First\n\n## 2. Second\n')
        commit(self.root, 'inline the lessons')
        self.assertEqual(self.run_check(self.cfg_data()), [])

    def test_uncited_removal_is_silent(self):
        git(self.root, 'init', '-q')
        self.write('wiki/lessons.md', PAGE_V1)
        self.write('docs/cite.md', 'No lessons cited here.\n')
        commit(self.root, 'two lessons')
        self.write('wiki/lessons.md',
                   PAGE_V1.replace('- **§2** [Second](l/2-second.md) — second rule.\n', ''))
        commit(self.root, 'drop the second lesson')
        self.assertEqual(self.run_check(self.cfg_data()), [])

    def test_the_index_is_not_a_citation_of_itself(self):
        self.plant()
        self.write('docs/cite.md', 'Nothing here.\n')
        commit(self.root, 'uncite')
        self.assertEqual(self.run_check(self.cfg_data()), [])

    def test_vacuous_without_enable(self):
        self.plant()
        data = self.cfg_data()
        data['history'] = {}
        self.assertEqual(self.run_check(data), [])

    def test_vacuous_without_lessons_page(self):
        self.plant()
        data = self.cfg_data()
        data['lessons'] = {}
        self.assertEqual(self.run_check(data), [])

    def test_needs_git_like_the_other_history_readers(self):
        self.plant()
        import os
        import shutil
        shutil.rmtree(self.root / '.git')
        with self.assertRaises(gitfiles.NotAGitCheckout):
            self.run_check(self.cfg_data())


if __name__ == '__main__':
    unittest.main()
