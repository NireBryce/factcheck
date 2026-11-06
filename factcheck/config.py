"""factcheck's config file: scopes, per-check bindings, disabled checks,
plugins.

The file is TOML (stdlib `tomllib`): hand-editable, comments allowed, and
the only config language the stdlib-only rule permits -- YAML or JSON
with comments would need a dependency, and plain JSON has no comments
for the why-lines every non-obvious binding needs. It lives at
`<root>/.agents/factcheck`, beside the skills directory that already
uses that path; the root-level `factcheck.toml` the tool originally used
keeps working, so a checkout pinned to an older revision and its config
migrate independently (#21).

A scope is a named list of root-relative glob patterns resolving to the
markdown files a check scans. Checks read their scope by name, so a repo
composes them once (`docs` for claim checks, `pages` for the page-shape
checks) instead of each check re-deriving its file list.

Patterns match with the one glob translation the repo has
(`globs.glob_regex`, the same one rule files use): `**/` is zero or more
directories, `**` is anything, `*` and `?` stay inside one segment,
`{a,b}` alternates, brackets are literal. `[scopes] exclude` drops paths
from every scope, and a per-scope `<name>-exclude` from one; an exclude
wins over any include.

Two rules the walker enforces, both inherited from hard experience in the
ancestor tool:

- **symlinks are never returned.** Repos keep README-style symlinks for
  platform discoverability; scanned as documents they double word counts
  and invent sibling pairs nobody wrote. Every check goes through here so
  a new one can't reintroduce that by globbing directly.
- **`.git` is never returned.** Plain `rglob` would happily descend into
  it on repos without an ignore-aware walker.

All configuration is optional: with no config file, `docs` and `pages`
default to every non-symlink markdown file under the root.
"""
import tomllib
from pathlib import Path, PurePosixPath

from .globs import glob_regex

CONFIG_FILE = '.agents/factcheck'
LEGACY_CONFIG_FILE = 'factcheck.toml'
DEFAULT_SCOPE = ['**/*.md']


class Config:
    def __init__(self, root, data=None, source=None):
        self.root = root
        self.data = data or {}
        # Where the data was parsed from, when it came from a file.
        self.source = source

    def section(self, name):
        """The `[name]` table, or {} -- checks read their bindings out of
        their own section and every binding is optional."""
        return self.data.get(name) or {}

    def scope(self, name):
        """The files scope `name` resolves to: sorted, deduplicated, no
        symlinks, nothing under .git, nothing an exclude claims."""
        scopes = self.data.get('scopes', {})
        includes = [glob_regex(p)
                    for p in scopes.get(name, DEFAULT_SCOPE)]
        excludes = [glob_regex(p) for p in scopes.get('exclude', [])]
        excludes += [glob_regex(p)
                     for p in scopes.get(f'{name}-exclude', [])]
        out = {}
        for p in self.root.rglob('*'):
            rel = PurePosixPath(p.relative_to(self.root))
            if p.is_symlink() or not p.is_file():
                continue
            if '.git' in rel.parts:
                continue
            rel_posix = rel.as_posix()
            if any(rx.match(rel_posix) for rx in excludes):
                continue
            if any(rx.match(rel_posix) for rx in includes):
                out[rel_posix] = p
        return [out[k] for k in sorted(out)]

    def disabled(self):
        """Check names switched off in `[checks] disabled = [...]`. Used
        where a check's convention isn't this repo's -- a disabled check is
        a decision recorded in the config, not a silent gap. The names are
        validated where checks dispatch: an unknown one is an error."""
        return set(self.section('checks').get('disabled', []))


def load(root, path=None):
    """Config for `root`: `path` if given, else `<root>/.agents/factcheck`,
    else the legacy root-level `factcheck.toml`. A missing file is not an
    error -- everything has a default."""
    candidates = ([Path(path)] if path else
                  [root / CONFIG_FILE, root / LEGACY_CONFIG_FILE])
    for p in candidates:
        if p.is_file():
            return Config(root, tomllib.loads(p.read_text()), source=p)
    return Config(root)
