"""Scope resolution: globs, excludes, dedupe, and the two walker rules
(no symlinks, nothing under .git) that exist because scanning the wrong
files produced real false findings in the ancestor tool; plus where the
config file is looked for."""
import unittest

from factcheck.config import Config, load

from .helpers import Tree


class Scopes(Tree):
    def test_glob_and_literal_patterns(self):
        self.write('docs/a.md')
        self.write('docs/b.md')
        self.write('AGENTS.md')
        cfg = Config(self.root, {'scopes': {'docs': ['docs/*.md', 'AGENTS.md']}})
        rels = [p.name for p in cfg.scope('docs')]
        self.assertEqual(rels, ['AGENTS.md', 'a.md', 'b.md'])

    def test_doublestar_includes_top_level_files(self):
        self.write('wiki/top.md')
        self.write('wiki/sub/nested.md')
        cfg = Config(self.root, {'scopes': {'pages': ['wiki/**/*.md']}})
        rels = [p.relative_to(self.root).as_posix() for p in cfg.scope('pages')]
        self.assertEqual(rels, ['wiki/sub/nested.md', 'wiki/top.md'])

    def test_symlinks_are_never_returned(self):
        self.write('real.md')
        (self.root / 'link.md').symlink_to(self.root / 'real.md')
        cfg = Config(self.root)
        self.assertEqual([p.name for p in cfg.scope('docs')], ['real.md'])

    def test_git_is_never_descended_into(self):
        self.write('.git/objects/xx.md')
        self.write('docs/a.md')
        cfg = Config(self.root, {'scopes': {'docs': ['**/*.md']}})
        self.assertEqual([p.name for p in cfg.scope('docs')], ['a.md'])

    def test_dedupe_and_sort(self):
        self.write('a.md')
        cfg = Config(self.root, {'scopes': {'docs': ['a.md', '**/*.md']}})
        self.assertEqual([p.name for p in cfg.scope('docs')], ['a.md'])

    def test_unknown_scope_is_empty(self):
        cfg = Config(self.root)
        self.assertEqual(cfg.scope('pages'), [])


class Excludes(Tree):
    def write_docs(self):
        self.write('docs/keep.md')
        self.write('docs/generated/skip.md')
        self.write('README.md')

    def test_per_scope_exclude(self):
        self.write_docs()
        cfg = Config(self.root, {'scopes': {
            'docs': ['**/*.md'],
            'docs-exclude': ['docs/generated/**']}})
        rels = [p.relative_to(self.root).as_posix()
                for p in cfg.scope('docs')]
        self.assertEqual(rels, ['README.md', 'docs/keep.md'])

    def test_global_exclude_hits_every_scope(self):
        self.write_docs()
        self.write('other.md')
        cfg = Config(self.root, {'scopes': {
            'exclude': ['docs/generated/**'],
            'docs': ['**/*.md'],
            'pages': ['docs/**/*.md']}})
        self.assertEqual([p.name for p in cfg.scope('docs')],
                         ['README.md', 'keep.md', 'other.md'])
        self.assertEqual([p.name for p in cfg.scope('pages')], ['keep.md'])

    def test_exclude_wins_over_include(self):
        self.write('a.md')
        cfg = Config(self.root, {'scopes': {
            'docs': ['a.md'], 'exclude': ['a.md']}})
        self.assertEqual(cfg.scope('docs'), [])

    def test_exclude_leaves_the_walker_rules_alone(self):
        # An exclude is a claim about paths, not a licence to rescan
        # symlinks or .git.
        self.write('real.md')
        self.write('.git/objects/xx.md')
        (self.root / 'link.md').symlink_to(self.root / 'real.md')
        cfg = Config(self.root, {'scopes': {'docs': ['**/*.md']}})
        self.assertEqual([p.name for p in cfg.scope('docs')], ['real.md'])

    def test_brace_alternation_and_literal_brackets(self):
        self.write('docs/a.md')
        self.write('docs/b.md')
        self.write('docs/c[1].md')
        cfg = Config(self.root, {'scopes': {
            'docs': ['docs/{a,b}.md']}})
        self.assertEqual(sorted(p.name for p in cfg.scope('docs')),
                         ['a.md', 'b.md'])


class Discovery(Tree):
    def test_new_location_is_read(self):
        self.write('.agents/factcheck', '[probe]\nseen = true\n')
        self.assertEqual(load(self.root).section('probe'), {'seen': True})

    def test_legacy_factcheck_toml_still_read(self):
        self.write('factcheck.toml', '[probe]\nseen = true\n')
        self.assertEqual(load(self.root).section('probe'), {'seen': True})

    def test_new_location_wins_over_legacy(self):
        self.write('.agents/factcheck', '[probe]\nseen = "new"\n')
        self.write('factcheck.toml', '[probe]\nseen = "legacy"\n')
        self.assertEqual(load(self.root).section('probe'), {'seen': 'new'})

    def test_explicit_path_wins_over_both(self):
        self.write('.agents/factcheck', '[probe]\nseen = "new"\n')
        self.write('elsewhere.toml', '[probe]\nseen = "explicit"\n')
        cfg = load(self.root, str(self.root / 'elsewhere.toml'))
        self.assertEqual(cfg.section('probe'), {'seen': 'explicit'})

    def test_source_names_the_file_it_parsed(self):
        self.write('.agents/factcheck', '[probe]\nseen = true\n')
        self.assertTrue(load(self.root).source.name.endswith('factcheck'))
        self.assertIsNone(Config(self.root).source)

    def test_missing_file_is_defaults(self):
        cfg = load(self.root)
        self.assertEqual(cfg.data, {})


class Disabled(unittest.TestCase):
    def test_disabled_list(self):
        cfg = Config(None, {'checks': {'disabled': ['dates', 'siblings']}})
        self.assertEqual(cfg.disabled(), {'dates', 'siblings'})


if __name__ == '__main__':
    unittest.main()
