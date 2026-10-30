---
name: investigate-bug
description: Checks whether a reported bug or symptom is already a tracked thread before you investigate it.
when_to_use: Someone reports a false finding, a missed finding, a crash or odd output, before reproducing or diagnosing it.
---

# Checking before investigating

## Applies to

Someone reports a false finding, a missed finding, a traceback or "weird"
output, and you're about to reproduce or diagnose it. Run this **before**
that. Not for deciding whether to write up something you already found
(`propose-issue`), and not when the user already points at the cause.

## Why

In the repo factcheck came from, hours went into re-deriving a bug from a
live session when it had been written up two days earlier, one link
from the docs index (nixos-configs §39, its issue 72). Prose saying "check
first" didn't make the check happen; a triggered skill does.

## Steps

1. **Before reproducing**, search with a couple of guesses from the
   report's wording (the finding's tag, the error text, the check name):

   ```sh
   gh issue list --repo NireBryce/factcheck --state all --search "<keywords>"
   git log --all --oneline -i --grep "<keywords>"
   grep -rn "<keywords>" README.md AGENTS.md tests/ examples/
   ```

   A finding that only shows up in a consumer may be that consumer's
   config or plugin. Look there too, but read only; don't file there
   (`propose-issue`).
2. **Hit:** read it fully and resume from where it left off. If it is
   stale or wrong, fix *that*; don't start a parallel investigation.
3. **No hit:** reproduce for real, with the reporter's input, not a
   fixture you wrote from the description (AGENTS.md, §50). Once it's
   diagnosed, don't leave it only in your reply: propose an issue, and
   add the failing input as a fixture test with the fix.
4. **Say fixed vs verified precisely.** A fix with a passing fixture is
   *tests pass*. It is *parity on a consumer* only once the reporter's
   repo produces the right findings.

## See also

`propose-issue`. Adapted from nixos-configs' `investigate-bug` skill.
