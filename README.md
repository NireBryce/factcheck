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

## Status: experimental -- review findings, and review the checks, before trusting either

This tool is young (extracted 2026-10-30) and its API -- config keys,
the plugin registry, finding formats -- will still move. Three things
follow from that:

- **Read a finding before acting on it.** The checks are heuristics over
  prose; a hard finding is a claim worth checking, not a verified fact,
  and the REVIEW findings are explicitly not assertions at all.
- **Review what a check enforces before gating anything on it.** The
  defaults encode the conventions of the repo it was extracted from
  (page headers, sibling pairs, generated regions); they may not be your
  conventions, and "the run is green" then means less than it looks.
  Its first consumer keeps every repo-specific checker as an in-repo
  plugin, reviewed there -- copy that discipline rather than trusting
  the defaults blind.
- **Pin or vendor if you adopt it.** A moving `main` behind a gate is a
  supply-chain decision to make deliberately, not inherit.

The extraction was parity-verified: on its source repo, factcheck and
the checker it replaced produced identical findings. The warning above
is about the parts no parity run can prove -- fit to your repo, and the
API's stability.

## Quickstart

On a machine without nix, install it like any Python tool (it is
stdlib-only, so the install is the only step):

```sh
pipx install git+https://github.com/NireBryce/factcheck
# or: pip install --user git+https://github.com/NireBryce/factcheck
```

```sh
./bin/factcheck check              # every registered check, against cwd
./bin/factcheck links --root .    # one check
./bin/factcheck checks            # what's registered
./bin/factcheck fix-contents PAGE.md   # a fixer, not a check
./bin/factcheck fix-refs dry-run        # after `git mv`: what references it would rewrite
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
| `fix-refs` | *fixer*: after `git mv`, rewrites references to the moved paths in every tracked text file -- markdown links (re-relativised from the linking file's new location), reference definitions, and bare repo paths in prose, code and scripts; whole-directory moves are inferred. Paths a program builds from pieces, and depth-sensitive code in moved scripts, print as `REVIEW` lines instead. `factcheck fix-refs dry-run` lists what would change | `[fix-refs] exclude`; extra moves as `OLD=NEW` arguments |
| `dates` | the `_Last modified: YYYY-MM-DD_` line exists right after the title, in exactly the configured shape, and isn't in the future | scope `pages`, `[dates] line` |
| `siblings` | the `<page>-for-agents.md` pairing: no orphans, long sources have a sibling (or a folded `## Quick facts` section), the sibling isn't older than its source unless a dated reviewed-line says why, word budget (REVIEW only), back-links both ways | scope `pages`, `[siblings] suffix, required-words, budget, fold-heading, exempt` |
| `recipes` | every backtick `` `just <recipe>` `` mention names a real recipe (handles `just key=value <recipe>` overrides and `mod` module names) | scope `docs`, `[recipes] justfile` |
| `skills` | every "skill X" / "X skill" mention names a real skill directory | scope `docs`, `[skills] dirs` |
| `skill-files` | the skill files themselves: the four lookups re-applied to skill prose (backticked-anywhere, bare-in-fences `just` mentions; skill mentions; relative links; repo-rooted backtick paths), plus SKILL.md-only rules — frontmatter `name` matching its directory, a one-sentence description with no repo paths, `when_to_use` under the harness listing cap, plain-YAML-safe values, unknown frontmatter keys, the `**Needs:**` tag vocabulary, and a ban on ` ```! ` / `!`backtick`` ` injection syntax | `[skills] dirs`, `[recipes] justfile`, `[skill-files]` keys/caps/prefixes/needs |
| `docrefs` | cross-references the narrower checks miss: `just <module> <helper>` naming no recipe in that just module; a `<skills-dir>/<name>` path or an unquoted hyphenated skill mention naming no skill directory; backticked paths under directories that moved (a config data table); a sentence naming one markdown page plus a quoted "…section" the page doesn't have; and BARE COUNT — a number from three up directly before a countable noun, unless the sentence names that many items, ends in a colon, carries a date or "as of", or opts out with `<!-- count-ok: reason -->` | scope `docs` + skills, `[docrefs] agent-module, moved-dirs, count-nouns, exempt` |
| `counts` | prose count claims — "all five hosts", "all three nixos hosts", "two of the three nixos hosts" — against actual counts | scope `docs`, `[counts] noun, classes, source, counters`, counters from plugins |
| `lessons-index` | a numbered lessons index stays whole: one `- **§N**` entry per lesson, linking its own `N-slug.md` article and stating the rule, each carrying the required fields (default `Home:` and `Enforced:`), an article for every number, no gaps from 1 to the top. Opt-in: off until `page` is set | `[lessons] page, dir, exempt` (replaces the default `0-human-README.md`), `fields, marker` |
| `restatement` | prose stated twice: word 8-grams shared between any two docs, merged into spans, a pair reported once they add up to `min-words`. Fences, H1 lines and Contents blocks don't count; `<page>` / `<page>-for-agents` sibling pairs are held back as by-design. REVIEW only, most-overlapping first. Opt-in | scope `docs`, `[siblings] suffix`, `[restatement] enable, min-words, top, siblings, exempt-pairs` |
| `rules` | path-scoped rule files: frontmatter is exactly a non-empty `paths:` list of quoted globs, every glob matches a git-tracked file, and the pointer doc names each rule | `[rules] dir, pointer` |
| `summaries` | every tracked file under a directory carries a marker line (default: `# package summary:` on package modules) | `[summaries] dir, suffix, marker, tag, exclude-*` |
| `generated` | every registered generated region exists on its home page and renders exactly what its source produces today; hand-written columns are carried per row, and a new row's empty hand cell is a finding until filled | regions registered by plugins |

Counters for `counts` come from three places, in precedence order: a
static value in config (`total = 5`), a glob count (`total = { glob =
"units/*.md" }`), or a plugin-registered function — see
`examples/nixos-plugins/roster.py`, which reads a hosts file statically,
no evaluation needed. A repo with no counters at all gets a vacuous
pass; a *partially* configured set is a finding, not a silent gap.

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
NixOS repo it checked. That repo adopted this tool on 2026-10-30, and
every check it had was given a declared home, so none could silently
disappear at the switch:

| check_docs.py check | home |
|---|---|
| links, anchors, contents + gen-contents, dates, siblings, recipes, skills, docrefs, counts, skill-files, rules, summaries, generated | **factcheck core now** |
| lessons (index half) | **factcheck core** as `lessons-index`, since it stopped being repo-specific (an example plugin until then) |
| imports/table (+ the static tree reading), secrets, routes, generated region instances | **plugins in that repo** (its `tools/docchecks/`, wired by its own `factcheck.toml`) since the switch; `examples/nixos-plugins/` keeps the copies they started from, as worked examples, and may lag the live ones |
| lessons (the lessons-map half) | **stays repo-carried, deliberately**: the map's glob semantics is a single shared module three readers there import so they cannot disagree; an example copy here would be exactly the duplicate the contract exists to prevent |

Verified: on a copy of that repo, factcheck and check_docs.py produce
identical finding sets for every check compared -- all fifteen except
the lessons-map half, on an untouched tree and with defects injected,
including the generated regions rendering byte-identically (same marker
lines, same tables). The example plugins carry no fleet facts in code:
names, routes and paths in their output come from the configured
sources at runtime; the example config holds this fleet's values, whose
docs domain is already public on its own site.

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
scripts/check   # the tests, the registry listing, and the self-check
```

CI runs exactly that script on Python 3.11, 3.13 and 3.14, plus a check
that a PR's commits carry the canonical agent trailer. No dependencies;
no install. `git config core.hooksPath .githooks` wires the local hooks
(trailer fix-up at commit, `scripts/check` before push).

Agents working here start at [AGENTS.md](AGENTS.md) (`CLAUDE.md` is a
symlink to it); the procedures for landing a change, reviewing one, and
writing docs that stay true are skills under `.agents/skills/`.

## License

MIT -- see [LICENSE](LICENSE).
