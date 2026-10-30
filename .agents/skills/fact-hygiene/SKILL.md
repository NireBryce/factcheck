---
name: fact-hygiene
description: Keeps facts, dated status, cross-references and copied counts, versions or config values from going stale when you write them.
when_to_use: Writing a claim about a consumer repo or an external system, a status as of a date, a comment stating something about other code as current fact, or a count, version or config value copied from another file.
---

# Writing facts that don't rot

## Applies to

Four kinds of claim, in the README, a docstring, a comment, a commit
message or a PR body:

1. **A specific fact about something not in front of you**, such as a
   consumer repo's layout or GitHub's renderer behaviour, stated with more
   confidence than you checked it with.
2. **A "status as of `<date>`" snapshot** asserting current, mutable state
   ("nixos-configs pins revision X", "every consumer has flipped").
3. **A cross-reference stated as currently true** ("`docrefs` and
   `counts` both read this table"). A later rename can't know the
   sentence exists.
4. **A derived fact that a command or the cited file already answers**:
   how many checks, how many tests, a line count, a version copied from
   `pyproject.toml`, a config default copied from the code.

Write freely: design rationale, event dates ("on 2026-10-30 X
happened", which can't go stale), plans and open questions labeled as
such, and comments that describe the code right next to them.

## The rule

- **1:** state only what you observed this session, by a named method
  (command output, a file read). Anything else gets a qualifier in the
  same sentence: `unverified`, "assumed from ...".
- **2:** a date says when someone last checked, not that the claim is
  fresh. If it can be re-checked now, check it. If not, write "last
  checked `<date>`, unconfirmed since".
- **3:** a name in prose is a pointer that can dangle. Before renaming or
  removing a check, a config key or a module, grep the exact name across
  the whole repo, docs and examples included.
- **4:** don't record it. Point at the file or command (`factcheck
  checks` lists the checks), or name the items and drop the number. Keep a
  number only when it is the rule itself, a dated record, a PR or issue
  reference, or something a user types. factcheck's own `docrefs` check
  flags the bare-count shape; don't silence it with the opt-out comment
  when a pointer would do.

## When a claim turns out wrong

1. Grep for every copy of it; dated-sounding claims get copied most.
2. Fix every copy in the same change, and correct the confidence as well
   as the content.

## See also

- `git-archaeology`: find the commit behind a date you are about to cite.
- Adapted from nixos-configs' `fact-hygiene` skill, whose four categories
  came from one cleanup sweep in that repo.
