---
name: propose-issue
description: Proposes a GitHub issue for a real bug in this repo's code or docs that you found while doing something else.
when_to_use: Noticing a defect while working on something unrelated, such as a check that misfires, a README example that fails, or a doc claim the code contradicts.
---

# Proposing bugs for the issue tracker

## Applies to

You're doing something else (writing a check, running factcheck on a
consumer, reading a module) and notice an actual defect: a false or
missed finding, a README example that doesn't run, a config key the code
no longer reads, dead code. Not something you were asked to look into
(fix that directly and say so), and not a style opinion (no failure
scenario, no issue).

## Never another repo

Every `gh issue create` here names `--repo NireBryce/factcheck`, even
when the cause is in a consumer's docs or plugins. Filing on another
project is a separate action that needs the user to ask for that
specific filing in their own message (AGENTS.md, "File issues and PRs
only in"). For a consumer's bug, tell the user; if factcheck should have
handled the case better, that part is an issue here.

## Steps

1. **Verify, don't recall.** Re-run the command or re-read the file.
2. **Check it isn't already tracked** (skill `investigate-bug`, step 1).
   Stop if it is.
3. **Ask with real content**: a title, a short drafted body and a label
   (`bug`, `documentation`, `enhancement`), not "should I file something?".
   Grep the draft for `owner/repo#123` shapes, which would ping another
   project.
4. **On yes:**

   ```sh
   gh issue create --repo NireBryce/factcheck \
     --title "..." --label bug --body-file <file>
   ```

   The body says what's wrong, where (`file:line`), how it was noticed,
   and a fix sketch if one is obvious. A finding's exact output line and
   the input that produced it make the best repro. End with `🤖 Generated
   by an LLM agent`, which names no model, for the same reason as the
   commit trailer. Report the issue URL.
5. **On no:** don't file, and say so.

## Calibrate

Propose what would bite the next consumer bump or the next session;
mention minor warts in your reply.

## See also

`investigate-bug`, `boyscouting`. Adapted from nixos-configs'
`propose-issue` skill.
