"""Shared fixture plumbing: a temp tree with a `write` helper, and a Config
built from a plain dict (the same shape factcheck.toml parses to)."""
import os
import pathlib
import re
import tempfile
import unittest

from factcheck.config import Config

# What `git rev-parse --local-env-vars` prints (git 2.43): the variables
# that tie a git process to one repository. A git hook exports them, so a
# test run inside one (pre-push runs the suite) would point every `git -C
# <tmp>` at the hook's repo instead of the test's: its `git config` lands
# in that repo's shared config and its `git commit` on its branch.
REPO_LOCAL_GIT_ENV = (
    'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_CONFIG', 'GIT_CONFIG_PARAMETERS',
    'GIT_CONFIG_COUNT', 'GIT_OBJECT_DIRECTORY', 'GIT_DIR', 'GIT_WORK_TREE',
    'GIT_IMPLICIT_WORK_TREE', 'GIT_GRAFT_FILE', 'GIT_INDEX_FILE',
    'GIT_NO_REPLACE_OBJECTS', 'GIT_REPLACE_REF_BASE', 'GIT_PREFIX',
    'GIT_SHALLOW_FILE', 'GIT_COMMON_DIR')
CONFIG_PAIR = re.compile(r'^GIT_CONFIG_(KEY|VALUE)_\d+$')


def strip_inherited_git_env(environ=os.environ):
    """Removes the repo-local git variables (and GIT_CONFIG_COUNT's
    numbered KEY/VALUE pairs) from `environ`; returns what it removed.
    Called once when the test package is imported, so no test -- present
    or future -- runs git against a repo it didn't create."""
    removed = {}
    for name in list(environ):
        if name in REPO_LOCAL_GIT_ENV or CONFIG_PAIR.match(name):
            removed[name] = environ.pop(name)
    return removed


class Tree(unittest.TestCase):
    """A temp directory dressed up as a small repo, plus dict-configs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def write(self, rel, text='x\n'):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def cfg(self, data=None):
        return Config(self.root, data or {})
