---
name: review
description: Reviews a change using this repo's own checks and the traps a doc checker falls into.
when_to_use: Reviewing a PR, branch or commit, or before saying your own change is done.
---

# Reviewing a change to factcheck

## Applies to

You're asked to review a PR, branch or commit, yours or someone else's,
or you're about to say "done" on your own change. It adds factcheck's
own failure modes to a generic code-review pass. Not for writing a check
from scratch; AGENTS.md "Before calling it done" covers that.

## Run first: the mechanical checks

Reading a diff is never enough.

1. `scripts/check`: the tests, the registry listing and the self-check.
   It is exactly what CI runs.
2. `git status --short`: an untracked new test or plugin file never ran
   in CI.
3. For a range of several commits, each commit green on its own (skill
   `ship`, step 1).
4. For a change to a check's behaviour, run it on a real consumer repo,
   before and after, and diff the findings:

   ```sh
   python3 -m factcheck check --root <consumer> > /tmp/before.txt   # on origin/main
   python3 -m factcheck check --root <consumer> > /tmp/after.txt    # on the branch
   diff /tmp/before.txt /tmp/after.txt
   ```

   Every added or vanished finding is explained in the PR. That is the
   *parity on a consumer* rung.

## Read for: traps a diff can't show

- **A new check without a failing fixture.** Its test must fail with the
  check removed or broken. Try it: comment out the check's core and run
  the test.
- **A test whose input is only the author's model of a doc** (nixos-configs §50). Prefer
  a fixture lifted from a real consumer's docs.
- **A trigger that never fires** (nixos-configs §28). Does the pattern occur in any real
  input? A check that has never produced a finding outside its own test
  is unproven.
- **Silent misses in a regex over prose** (nixos-configs §22): `\w` misses `-`, a
  backtick or a line wrap splits the token, case differs. Is there a
  fixture for each spelling the docs actually use?
- **Hard vs REVIEW.** A heuristic that can be wrong on a correct doc must
  emit `REVIEW`, never a hard finding that fails someone's CI.
- **A new default that encodes one repo's conventions.** It must be
  overridable in config, and the README's checks table must name the key.
- **Stdlib only, 3.11 syntax.** No new import from outside the standard
  library. No syntax or stdlib API newer than 3.11; CI's 3.11 job is the
  backstop.
- **The plugin API.** A changed signature in `factcheck.findings`,
  `factcheck.registry`, `factcheck.fixers` or `factcheck.mdcore` breaks
  consumers' plugins. Is it called out?
- **Symlinks and fences.** Docs are walked in one place, which skips
  symlinks; fences have one definition (`mdcore.fences`). A check that
  globs or detects fences on its own reintroduces the bugs those exist to
  prevent.
- **The README.** Did the change make its checks table, config keys or
  examples stale (AGENTS.md, "A change that makes the README stale")?

## Conventions worth flagging

- Trailer `Co-Authored-By: <agent>`, name only. CI's trailers job fails
  the PR otherwise.
- Public text about a check says what it enforces, not what got past it.
- A dated "as of" claim is when someone last looked, not proof (skill
  `fact-hygiene`).

## Saying the outcome

Name the rung reached: *tests pass*, *self-check passes*, *parity on a
consumer*, *used*. An undated "verified" means *tests pass*.

## See also

- `ship`: the pre-PR gate, from the author's side.
- Adapted from nixos-configs' `review` skill.
