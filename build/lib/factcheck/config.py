"""factcheck.toml: scopes, per-check bindings, disabled checks, plugins.

A scope is a named list of root-relative glob patterns resolving to the
markdown files a check scans. Checks read their scope by name, so a repo
composes them once (`docs` for claim checks, `pages` for the page-shape
checks) instead of each check re-deriving its file list.

Two rules the walker enforces, both inherited from hard experience in the
ancestor tool:

- **symlinks are never returned.** Repos keep README-style symlinks for
  platform discoverability; scanned as documents they double word counts
  and invent sibling pairs nobody wrote. Every check goes through here so
  a new one can't reintroduce that by globbing directly.
- **`.git` is never returned.** Plain `rglob` would happily descend into
  it on repos without an ignore-aware walker.

All configuration is optional: with no factcheck.toml, `docs` and `pages`
default to every non-symlink markdown file under the root.
"""
import tomllib
from pathlib import Path, PurePosixPath

CONFIG_FILE = 'factcheck.toml'
DEFAULT_SCOPE = ['**/*.md']


class Config:
    def __init__(self, root, data=None):
        self.root = root
        self.data = data or {}

    def section(self, name):
        """The `[name]` table, or {} -- checks read their bindings out of
        their own section and every binding is optional."""
        return self.data.get(name) or {}

    def scope(self, name):
        """The files scope `name` resolves to: sorted, deduplicated, no
        symlinks, nothing under .git."""
        patterns = self.data.get('scopes', {}).get(name, DEFAULT_SCOPE)
        out = {}
        for pat in patterns:
            for p in self.root.glob(pat):
                rel = PurePosixPath(p.relative_to(self.root))
                if p.is_symlink() or not p.is_file():
                    continue
                if '.git' in rel.parts:
                    continue
                out[rel.as_posix()] = p
        return [out[k] for k in sorted(out)]

    def disabled(self):
        """Check names switched off in `[checks] disabled = [...]`. Used
        where a check's convention isn't this repo's -- a disabled check is
        a decision recorded in the config, not a silent gap."""
        return set(self.section('checks').get('disabled', []))


def load(root, path=None):
    """Config for `root`; `path` overrides where factcheck.toml is looked
    up (a missing file is not an error -- everything has a default)."""
    p = Path(path) if path else root / CONFIG_FILE
    if p.is_file():
        return Config(root, tomllib.loads(p.read_text()))
    return Config(root)
