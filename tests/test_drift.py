"""drift: commits under a doc's cited paths after its date, on a throwaway
repo with pinned commit dates; ranking, the floors, and opt-in."""
import os
import subprocess

from .helpers import Tree

from factcheck.checks import drift

ON = {'drift': {'enable': True}, 'scopes': {'docs': ['docs/*.md']}}


class Drift(Tree):
    def setUp(self):
        super().setUp()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith('GIT_')}
        self.env.update(GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t.invalid',
                        GIT_COMMITTER_NAME='t',
                        GIT_COMMITTER_EMAIL='t@t.invalid',
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        self.git('init', '-q')

    def git(self, *args, date=None):
        env = dict(self.env)
        if date:
            env['GIT_COMMITTER_DATE'] = env['GIT_AUTHOR_DATE'] = \
                f'{date}T12:00:00Z'
        subprocess.run(['git', '-C', str(self.root), *args], env=env,
                       check=True, capture_output=True)

    def commit(self, date, *files):
        for f in files:
            self.write(f, f'{date} {f}\n')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', date, date=date)

    def findings(self, data=ON):
        return drift.check_drift(self.root, self.cfg(data))

    def test_counts_commits_after_the_doc_date_only(self):
        self.commit('2026-01-01', 'src/app/core.py', 'src/app/util.py')
        self.write('docs/a.md', '# A\n\n_Last modified: 2026-02-01_\n\n'
                   'See `src/app/core.py` and [u](../src/app/util.py).\n')
        self.commit('2026-01-15', 'src/app/core.py')   # before: not counted
        self.commit('2026-03-01', 'src/app/core.py')
        self.commit('2026-03-02', 'src/app/util.py', 'docs/notes.md')
        f = self.findings()
        self.assertEqual([x.path for x in f], ['docs/a.md'])
        self.assertTrue(f[0].review)
        self.assertIn('2 commit(s) since 2026-02-01', f[0].message)
        self.assertIn('src/app/core.py (1)', f[0].message)

    def test_ranked_most_first_and_floors(self):
        self.commit('2026-01-01', 'src/x/a.py', 'src/x/b.py')
        self.write('docs/one.md', '# 1\n\n_Last modified: 2026-01-02_\n\n'
                   '`src/x/a.py`\n')
        self.write('docs/two.md', '# 2\n\n_Last modified: 2026-01-02_\n\n'
                   '`src/x/b.py`\n')
        self.commit('2026-01-02')
        self.commit('2026-02-01', 'src/x/b.py')
        self.commit('2026-02-02', 'src/x/b.py')
        self.commit('2026-02-03', 'src/x/a.py')
        self.assertEqual([x.path for x in self.findings()],
                         ['docs/two.md', 'docs/one.md'])
        data = {**ON, 'drift': {'enable': True, 'min-commits': 2}}
        self.assertEqual([x.path for x in self.findings(data)],
                         ['docs/two.md'])
        data = {**ON, 'drift': {'enable': True, 'top': 1}}
        self.assertEqual(len(self.findings(data)), 1)

    def test_shallow_dirs_ambiguous_names_and_md_are_ignored(self):
        self.commit('2026-01-01', 'src/a/x.py', 'lib/a/x.py', 'docs/b.md')
        self.write('docs/c.md', '# C\n\n_Last modified: 2026-01-02_\n\n'
                   '`src/` `x.py` `docs/b.md`\n')
        self.commit('2026-01-02')
        self.commit('2026-02-01', 'src/a/x.py', 'lib/a/x.py', 'docs/b.md')
        self.assertEqual(self.findings(), [])

    def test_no_date_line_falls_back_to_last_commit(self):
        self.commit('2026-01-01', 'src/a/x.py')
        self.write('docs/d.md', '# D\n\n`src/a/x.py`\n')
        self.commit('2026-01-05')
        self.commit('2026-02-01', 'src/a/x.py')
        f = self.findings()
        self.assertIn('since 2026-01-05', f[0].message)

    def test_a_cited_directory_counts_changes_beneath_it(self):
        self.commit('2026-01-01', 'src/app/mod/x.py')
        self.write('docs/e.md', '# E\n\n_Last modified: 2026-01-02_\n\n'
                   'Everything under `src/app/mod/`.\n')
        self.commit('2026-01-02')
        self.commit('2026-02-01', 'src/app/mod/deep/y.py')
        f = self.findings()
        self.assertIn('src/app/mod (1)', f[0].message)

    def test_at_sign_path_does_not_break_the_log_parser(self):
        self.commit('2026-01-01', '@scope/pkg/i.js', 'src/a/x.py')
        self.write('docs/f.md', '# F\n\n_Last modified: 2026-01-02_\n\n'
                   '`src/a/x.py`\n')
        self.commit('2026-01-02')
        self.commit('2026-02-01', 'src/a/x.py', '@scope/pkg/i.js')
        self.assertEqual(len(self.findings()), 1)

    def test_impossible_date_falls_back_to_git(self):
        self.commit('2026-01-01', 'src/a/x.py')
        self.write('docs/g.md', '# G\n\n_Last modified: 2026-02-30_\n\n'
                   '`src/a/x.py`\n')
        self.commit('2026-01-05')
        self.commit('2026-02-01', 'src/a/x.py')
        self.assertIn('since 2026-01-05', self.findings()[0].message)

    def test_shallow_clone_is_reported_not_undercounted(self):
        self.commit('2026-01-01', 'src/a/x.py')
        self.commit('2026-01-02', 'src/a/x.py')
        clone = self.root.parent / (self.root.name + '-shallow')
        subprocess.run(['git', 'clone', '-q', '--depth', '1',
                        f'file://{self.root}', str(clone)], check=True,
                       env=self.env, capture_output=True)
        self.addCleanup(__import__('shutil').rmtree, clone, True)
        f = drift.check_drift(clone, self.cfg(ON).__class__(clone, ON))
        self.assertEqual([x.tag for x in f], ['DRIFT NEEDS HISTORY'])

    def test_off_unless_enabled(self):
        self.commit('2026-01-01', 'src/a/x.py')
        self.write('docs/d.md', '# D\n\n`src/a/x.py`\n')
        self.commit('2026-01-05')
        self.commit('2026-02-01', 'src/a/x.py')
        self.assertEqual(self.findings({'scopes': ON['scopes']}), [])


class NotARepo(Tree):
    def test_reported_once(self):
        self.write('docs/a.md', '`src/a/x.py`\n')
        f = drift.check_drift(self.root, self.cfg(ON))
        self.assertEqual([(x.tag, x.review) for x in f],
                         [('DRIFT NEEDS GIT', True)])
