---
name: boyscouting
description: Fixes small, local problems in files you're already editing, in the same commit as the main task.
when_to_use: Noticing a stale comment, dead import, unused variable or similar small flaw in a file you're changing for another reason.
---

# Boyscouting

## Applies to

You're editing a file for a real task and notice something small and
local: a stale comment, a dead import, a misnamed variable, a duplicated
three-liner. Not for:

- a defect worth tracking: `propose-issue`;
- a README claim your change made stale: fix it as part of the change
  (AGENTS.md, "A change that makes the README stale");
- a deliberate broad tidy-up: say so and make it the task.

## The rule

Fix only what the diff touches or sits next to. Put the fix in the same
commit as the main task, and say in the commit body that it's incidental.

## What qualifies

- Small, obviously correct, and reviewable in seconds next to the real
  change.
- In a file, or lines next to ones, you're editing anyway. Having to open
  a file you otherwise wouldn't makes it a separate task.
- Changes no behaviour, no finding a check emits, and no plugin API. If
  you can't tell that it's behaviour-neutral, it needs real verification
  and isn't a quick tidy.

## What doesn't

- **A real bug**, even a tiny one, once it has a failure scenario:
  `propose-issue`, unless the user is present and says to fix it now.
- **A rename or restructure** because you'd have written it differently.
- **A file you weren't going to touch.**

## Steps

1. Spot something small in a file you're already changing.
2. If it needs another file or changes behaviour, stop and use
   `propose-issue`, or mention it.
3. Make the fix, minimal and local.
4. Report it ("also removed an unused import in the same file") and add a
   trailing clause to the commit body.

## See also

`propose-issue` (noticed, not fixed). Adapted from nixos-configs'
`boyscouting` skill.
