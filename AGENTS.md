# AGENTS.md

> **Written by agents, for agents.** These are working notes for something
> with no memory between sessions; a repeated mistake is the failure mode
> this file exists to prevent. `README.md` is the human entry point.
>
> This file is canonical, and `CLAUDE.md` is a symlink to it. Skills are
> plain markdown at `.agents/skills/<name>/SKILL.md`, which any agent can
> read as files. `.claude/` is a real directory whose `skills` and
> `settings.json` are symlinks into `.agents/`: a symlinked `.claude`
> makes Claude Code refuse to create subagent worktrees.
>
> Adapted on 2026-10-30 from
> [nixos-configs](https://github.com/NireBryce/nixos-configs)' agent
> tooling, the repo factcheck was extracted from. A rule here citing
> "§N" points at that repo's
> [lessons index](https://github.com/NireBryce/nixos-configs/blob/experimental/wiki/agent-lessons-learned.md),
> where the account of the mistake behind it lives.

## What this is

A stdlib-only Python 3.11+ CLI that checks a repository's documentation
against the repository. Checks register in `factcheck/registry.py`, and
`factcheck checks` lists them. Repo-specific checks are plugins that live
in the consuming repo, not here; `examples/` holds worked ones.
Consumers pin factcheck by revision, so whatever lands on `main` is what
the next bump picks up.

## Hard rules

Each one is stated in full, with its reason, in the section it belongs
to.

- **Standard library only, Python 3.11 syntax.** (Conventions)
- **A new check lands with a fixture test of the case it exists to
  catch, in the same commit.** (Before calling it done)
- **"push" means skill `ship`: a PR to `main`, merged only on the user's
  yes.** (Working)
- **Do work that will branch or commit in its own worktree.** (Working)
- **File issues and PRs only in `NireBryce/factcheck`**, unless the user
  asks for a specific filing elsewhere. (Working)
- **Public text says what a check enforces, not what got past it.**
  (Working)
- **Say which rung you reached, and never more.** (Before calling it
  done)
- **Trailer `Co-Authored-By: Claude`; prose says "the user".**
  (Conventions)

## Before calling it done

**Say which rung you reached.** In ascending order: *tests pass*
(`scripts/check`, the same command CI runs); *self-check passes* (part of
`scripts/check`: factcheck run on its own docs); *parity on a consumer*
(run on a real consuming repo, with findings compared against what was
there before); *used* (a consumer's CI ran the pinned revision). Each one
finds defects the one before cannot. An undated "verified" means *tests
pass* (§18).

**A clean run proves nothing.** A checker that reports success has not
been tested. Test it against a case it should catch, in the same commit
(§1). Before believing a zero, show that the query can return non-zero:
a regex over prose misses silently when the spelling differs or `\w`
misses `-` (§22). Know what a count counts (§31).

**A stub tests your model of the input** (§50). A fixture written from
what you think consumers' docs look like passes against your own
assumptions. Take fixture inputs from real consumer docs where you can,
and count *parity on a consumer* only against a real repo.

**A check keyed on a signal that never fires prevents nothing** (§28).
Show that the trigger occurs in real input before trusting the check to
catch anything.

**When a check fires on new work, fix its model before reaching for its
escape flag** (§23). "This check is wrong" and "this check is incomplete"
look the same from outside. Don't satisfy a check by editing its input
into silence, such as bumping a date it compares.

**When a tool contradicts you, suspect yourself first** (§3): which
commit, which cwd, which Python.

**Read the output, not the status.** `cmd | tail` exits 0 when `cmd`
failed. Use `set -o pipefail` or don't pipe (§20). Python puts the cause
at the bottom of a traceback; read to the end.

**Tests never touch a repo they didn't create.** A git hook exports
`GIT_DIR` and friends, and the suite runs inside one (pre-push); inherited,
they aim a test's `git -C <tmp>` at the hook's repo. `tests/__init__.py`
strips them before any test loads, and `scripts/check` clears them too, so
a new test that shells out to git needs nothing extra
(nixos-configs §44; on 2026-10-31 this wrote a fake identity into the
shared repo config before it was in place).

**Each commit is green on its own** (§15). Check what is staged before
committing, and never describe in a message what the commit doesn't
contain yet.

**Writing a trap down doesn't stop the next agent walking into it** (§5).
If a mistake can be made mechanically impossible, with a check, a test
or a hook, do that instead of adding a sentence here.

## Working in this repo

**"push" means skill `ship`**: branch, PR to `main`, CI green, then one
combined ask covering both the merge and the branch deletion. Merge only
on a yes. Naming another branch outright means push there; `main` itself
moves only by PR. Check the branch with `git branch --show-current`;
don't assume it.

**Do work that will branch, commit or check out in a dedicated `git
worktree`** (skill `use-a-worktree`). Skip that for read-only work, or
when the user says to work in the shared checkout. If git state doesn't
match your own last action, check `git reflog` before concluding that
anything is broken.

**A change that makes the README stale fixes it in the same change.**
The README's checks table, config keys and examples are claims about the
code. Grep for the names you changed before calling it done.

**Fix small things only in files you're already changing** (skill
`boyscouting`). A defect anywhere else gets proposed, not fixed (skill
`propose-issue`). Before investigating a reported bug, check whether it
is already tracked (skill `investigate-bug`).

**File issues and PRs only in `NireBryce/factcheck`.** A bug in a
consumer is reported to the user, and filed in that repo only if the
user asks for that specific filing in their own message. Approving a
list of tasks doesn't count. A filing here can still ping another project
through GitHub autolinking (`owner/repo#123`), so grep a draft for that
shape before filing.

**Public text says what a check enforces and how it was verified.** That
covers PR bodies, commit messages, code comments, test names and the
README. Never write there which inputs got past an older version, or what
a gap in a consumer's docs would expose. Tests keep the inputs they check
without narrating them.

**Read upstream behaviour rather than guessing at it.** GitHub's anchor
slugs and CommonMark's fence rules were reverse-engineered from the real
renderer (README, "Design notes worth keeping"). A new rendering
assumption gets the same treatment, and a comment saying where it was
read.

**Calibrate severity.** One maintainer and a few consumers. "This is
broken and here is the fix" beats incident framing.

## Conventions

- **Standard library only, Python 3.11+.** factcheck runs in pre-commit
  hooks and degraded environments with no package manager. No
  dependency, not even a dev one, and no syntax newer than 3.11. CI runs
  3.11, 3.13 and 3.14.
- **Defaults are one repo's conventions.** A new default must be
  overridable in config. A default that only makes sense for the repo
  factcheck came from belongs in that repo's config or plugins.
- **REVIEW vs hard findings.** A heuristic that can't be sure emits
  `REVIEW`, which never fails a run. A hard finding is a claim that it
  is right.
- **The plugin API is public.** Consumers' plugins import from
  `factcheck.findings`, `factcheck.registry`, `factcheck.fixers` and
  `factcheck.mdcore`. Changing a signature there is a breaking change:
  say so in the commit body and the PR.
- **Commit messages:** Conventional Commits prefix on the first line
  (`feat:`, `fix:`, `docs:`, `chore:`, `test:`); the body says what, why
  and what was verified.
- **Provenance trailer on every agent-authored commit:
  `Co-Authored-By: <agent>`**, the agent's name only, with no model name
  and no email. An agent cannot verify which model is executing it.
  Claude's form is `Co-Authored-By: Claude`. Three layers hold it:
  `attribution.commit` in `.agents/settings.json`, `.githooks/commit-msg`
  (which rewrites the wrong Claude shape), and `scripts/check_trailers.py`
  in CI over a PR's own commits. Any other agent's trailer passes through
  all three, so form it correctly at write time.
- **Prose that means the person says "the user"**, never a name.

## Commands

```sh
scripts/check                        # tests + registry listing + self-check; what CI runs
python3 -m unittest tests.test_links # one test module
python3 -m factcheck <check> --root <repo>   # one check against another repo
```

`git config core.hooksPath .githooks` wires the git hooks: `commit-msg`
fixes the trailer and `pre-push` runs `scripts/check`. Under Claude Code
the session-start hook sets it when it is unset.

## Skills

The skills under `.agents/skills/` are listed by any harness that reads
that directory. Every one is plain markdown; read the file when its task
comes up. `ship`, `use-a-worktree`, `review`, `fact-hygiene`, `new-skill`,
`boyscouting`, `git-archaeology`, `propose-issue` and `investigate-bug`
are adapted from nixos-configs' skills of the same names.
