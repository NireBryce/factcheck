# factcheck

Checks the claims a project's documentation makes against the repository
it documents.

Docs drift silently: nothing about a rename, a deleted file, or a changed
config reads the prose that describes it. factcheck extracts structured,
checkable facts from markdown -- link targets, `just <recipe>` mentions,
page conventions, set-claims like "these hosts are enrolled" -- and
compares them against reality: the filesystem, a justfile, skill
directories, or any source a plugin knows how to read.

It runs on the Python standard library alone (3.11+), from a checkout,
with no install step, so it can live in pre-commit hooks, CI, and
degraded environments that have no package manager. Extracted from a
working doc-vs-repo checker in a large NixOS configuration repo, where
every design choice below was paid for at least once.

## Quickstart

```sh
./bin/factcheck check              # every registered check, against cwd
./bin/factcheck links --root .    # one check
./bin/factcheck checks            # what's registered
./bin/factcheck fix-contents PAGE.md   # a fixer, not a check
```

With no `factcheck.toml`, the `docs` and `pages` scopes are every
non-symlink markdown file under the root (never under `.git`). Most real
repos want explicit scopes:

```toml
# factcheck.toml
[scopes]
docs = ["docs/**/*.md", "README.md", "CONTRIBUTING.md"]
pages = ["docs/**/*.md"]

[recipes]
justfile = "Justfile"

[plugins]
load = ["plugins/my-checks.py"]
```

## The checks

| check | claims it checks | bindings (config) |
|---|---|---|
| `links` | every relative markdown link resolves to a real file (percent-decoded first) | scope `docs` |
| `anchors` | every `#fragment` resolves to a real heading, slugged the way GitHub renders it, including `-1` dedup counters | scope `docs` |
| `contents` | a page's `## Contents` list matches its own headings; a page that should have one has one | scope `pages`, `[contents] exempt` |
| `fix-contents` | *fixer*: rewrites a Contents block in place; replaces only the bullet run, never the surrounding prose | — |
| `dates` | the `_Last modified: YYYY-MM-DD_` line exists right after the title, in exactly the configured shape, and isn't in the future | scope `pages`, `[dates] line` |
| `siblings` | the `<page>-for-agents.md` pairing: no orphans, long sources have a sibling (or a folded `## Quick facts` section), the sibling isn't older than its source unless a dated reviewed-line says why, word budget (REVIEW only), back-links both ways | scope `pages`, `[siblings] suffix, required-words, budget, fold-heading, exempt` |
| `recipes` | every backtick `` `just <recipe>` `` mention names a real recipe (handles `just key=value <recipe>` overrides and `mod` module names) | scope `docs`, `[recipes] justfile` |
| `skills` | every "skill X" / "X skill" mention names a real skill directory | scope `docs`, `[skills] dirs` |

Conventions vary; bindings are config. The defaults are the conventions
factcheck was extracted from -- every one overridable, none load-bearing.

## Findings

A finding prints as one line, `TAG  path: message`. Findings a heuristic
can't be sure about are marked `REVIEW` and never fail a run on their own
(the run says so explicitly rather than passing silently); everything else
is hard and exits 1. Exit 2 means usage error. After the findings, one
`-> TAG: see <advice>` line per kind points at the fix.

`--skip=a,b` leaves named checks out of `check` and says so in the output;
a `--skip` name that matches no check is an error, not a no-op. Checks can
also declare capability needs (`needs=("nix",)`) and are skipped, loudly,
where the capability is missing.

## Plugins

A plugin is any Python module that registers checks at import time. List
it in the config by repo-relative path:

```toml
[plugins]
load = ["plugins/my-checks.py"]
```

```python
# plugins/my-checks.py -- the whole seam
from factcheck.findings import Finding
from factcheck.registry import check

@check('my-roster', needs=())          # needs=("nix",) if it shells out
def check_my_roster(root, cfg):
    ...
    return [Finding('MY TAG', rel_path, "what's wrong")]
```

Registration is the subcommand table: a registered check gets its own
subcommand, a place in `check`'s output order, and `--skip` support, and
nothing else has to know its name. Re-executing a plugin module replaces
its checks instead of duplicating them, so callers can exec the tool afresh
per invocation. See `plugins/example/pending-decisions.py` for the smallest
real one. A fixer registers through `factcheck.fixers` and never joins
`check`'s aggregate -- fixers rewrite files; checks only report.

## Provenance: parity with check_docs.py

factcheck generalizes a checker (`check_docs.py`) that lived inside the
NixOS repo it checked. Since that repo will adopt this tool, every check
there has a declared home here -- none may silently disappear at the
switch:

| check_docs.py check | home |
|---|---|
| links, anchors, contents + gen-contents, dates, siblings, recipes, skills | **factcheck core now** (as `links`, `anchors`, `contents` + `fix-contents`, `dates`, `siblings`, `recipes`, `skills`) |
| docrefs (helper lookup, quoted-section, bare-count rule), counts, skill-files frontmatter rules, rules (`paths:` frontmatter), summaries (marker line), generated-region engine | **factcheck core later** |
| imports/table + static nix tree reading, secrets (sops enrollment), routes (reverse-proxy), lessons (+ the lessons-map contract), generated-region instances | **plugins carried by that repo** -- they encode its fleet facts |

## Design notes worth keeping

- **Symlinks are never scanned.** README-style symlinks double word counts
  and invent sibling pairs nobody wrote; the walker is the one place that
  decides, so a new check can't reintroduce it by globbing directly.
- **Fences have one definition** (`mdcore.fences`, CommonMark line rules).
  The ancestor's scripts once carried six ideas of what a fence is; one
  was defined twice in one file and the later one silently won.
- **Slugs are GitHub's, reverse-engineered**, not assumed: punctuation
  disappears with nothing in its place (`` `VMs/_lib/x.nix` `` slugs to
  `vms_libxnix`-shaped strings), and repeated headings get `-1` counters
  fed by every heading in document order, not just the ones you want.
- **A clean run proves nothing.** Every check lands with a fixture test
  against the case it exists to catch, in the same change.

## Development

```sh
python3 -m unittest discover -s tests -t .
python3 -m factcheck check   # self-check (factcheck.toml scopes it)
```

CI runs both on Python 3.11, 3.13 and 3.14. No dependencies; no install.

## License

MIT -- see [LICENSE](LICENSE).
