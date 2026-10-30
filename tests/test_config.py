"""Scope resolution: globs, dedupe, and the two walker rules (no symlinks,
nothing under .git) that exist because scanning the wrong files produced
real false findings in the ancestor tool."""
import unittest

from factcheck.config import Config

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


class Disabled(unittest.TestCase):
    def test_disabled_list(self):
        cfg = Config(None, {'checks': {'disabled': ['dates', 'siblings']}})
        self.assertEqual(cfg.disabled(), {'dates', 'siblings'})


if __name__ == '__main__':
    unittest.main()
