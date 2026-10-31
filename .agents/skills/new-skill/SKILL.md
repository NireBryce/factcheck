---
name: new-skill
description: Writes a new SKILL.md, or fixes the frontmatter of an existing skill.
when_to_use: Creating a SKILL.md, or editing any skill's description or when_to_use.
---

# Writing a new skill

## Applies to

Creating `.agents/skills/<name>/SKILL.md`, or editing an existing
skill's `description` or `when_to_use`. Not for editing a skill's body
alone.

## The rule

| Where | Holds | Who sees it |
|---|---|---|
| `description` | One sentence saying what the skill does, starting with a verb. No file paths, no parenthetical scope lists, no trigger conditions. | Every harness's skill listing |
| `when_to_use` (optional) | Short trigger phrases, one line. | Claude Code only, appended to the description |
| `## Applies to` (first section) | The full trigger list: triggers, non-triggers, exceptions. | Anyone who loaded the skill |

The listing shows only frontmatter, and that is all a session has when
it decides whether to load a skill. Other harnesses ignore `when_to_use`,
so nothing may live only there. Both values must be plain YAML scalars:
never open with a quote, and no `: ` or ` #` inside.

Only `name`, `description` and `when_to_use` are allowed. No
`allowed-tools`, and no syntax that runs a command when the skill loads
(an exclamation mark directly before a backtick, or a fence opened with
three backticks and an exclamation mark). In prose, never put an
exclamation mark directly before a backtick.

`factcheck skill-files`, part of the self-check in `scripts/check`,
enforces the mechanical half: description shape, `when_to_use` on one
line, the key list, injection syntax, links and mentions inside the
skill. This repo runs factcheck on its own skills, so a skill that breaks
the rule fails CI.

## Steps

1. Pick a kebab-case name matching the directory. Discovery is
   automatic; there is no registry to update.
2. Draft the description first, alone. If it needs a second clause, that
   clause belongs in `## Applies to`.
3. Write `## Applies to` right after the title: triggers, explicit
   non-triggers, exceptions. Lift any short trigger phrases the
   description doesn't carry into `when_to_use`.
4. Write the body in whatever shape the task needs: why, steps, gotchas,
   see also. Cite real files and commands.
5. Re-read the description against the finished body and fix it if the
   body grew.
6. Run `scripts/check`.

## See also

- The other skills in `.agents/skills/` are the worked examples.
- Adapted from nixos-configs' `new-skill` skill. That repo's `**Needs:**`
  tag for hook-dependent skills isn't used here, because factcheck has no
  guard hooks.
