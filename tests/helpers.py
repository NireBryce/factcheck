"""Shared fixture plumbing: a temp tree with a `write` helper, and a Config
built from a plain dict (the same shape factcheck.toml parses to)."""
import pathlib
import tempfile
import unittest

from factcheck.config import Config


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
