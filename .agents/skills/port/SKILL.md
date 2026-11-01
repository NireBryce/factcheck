---
name: port
description: Ports conventions and scaffolding from other repos into this one, adapted to this repo's own vocabulary rather than copied.
when_to_use: A request to adopt, port, extract or sync templates, CI, branch protection, hooks or skills from other repos into this one.
---

# Porting from other repos

## Applies to

The deliverable is this repo's own files or settings, derived from one
or more named source repos: "port/adopt/extract X from <repos>", "make
this repo's scaffolding match the siblings", "bring the issue templates
over". The sources are arguments -- any repos, named in the ask.

Not for: fixing a defect noticed along the way (skill `propose-issue`),
small cleanups inside files already being changed (skill
`boyscouting`), landing changes on `main` (skill `ship` runs the
landing), or copying code under the public plugin API -- that is an
ordinary code change, not a convention port. Reading other repos for
comparison, changing nothing here, is research: no worktree until
something branches.

## Why

A port copied verbatim imports the source's domain: an issue form whose
dropdown lists another project's hosts lies in a repo that has none.
What transfers between repos is the *shape* -- the discipline a
template, hook or ruleset encodes. The *content* -- enumerations,
required fields, contact links, check names -- must come from this
repo's own reality. Classifying every artifact before writing anything
keeps the verbatim copies verbatim, keeps the adaptations honest, and
forces an explicit answer for everything skipped.

## Inventory both sides first

Source repos, on disk or through the API: `.github/` (templates,
workflows, dependabot), branch protection (`gh api` on the rulesets
endpoints -- invisible to a clone), `.agents/` skills and hooks, git
hooks, README structure. This repo: the same surfaces, read *before*
writing. An adapted equivalent may already exist here, in which case
the port is a diff against it -- or nothing at all.

## Classify before writing

Every artifact is verbatim, adapted, or skipped, and the decision is
explicit per artifact:

- **verbatim** -- encodes no source domain: a dependabot config, a
  gitignore, an editor setting. Copy it, and fix any comment that would
  lie about this repo (a workflow count, a justification naming the
  source's shape).
- **adapt** -- the shape is the source's contribution, the content is
  this repo's: issue forms (dropdown options come from this repo's own
  enumeration -- ask the tool, never transcribe the source's), PR
  templates (section structure stays; the domain guidance comments
  rewrite), branch-protection rulesets (mirror an existing ruleset as a
  JSON template and swap the name, branch condition and required
  checks).
- **skip** -- an equivalent already exists here, or the artifact is
  pure source domain. The PR body says why, under "Deliberately left
  alone"; an unexplained gap invites the next session to redo the
  decision with worse information.

## Adaptation rules

- Every enumeration comes from this repo's ground truth -- the tool's
  own listing, a real CI run's job names -- never from the source repo.
- Verify external constraints against their real documentation rather
  than memory, and record where a number was read (issue-form field
  caps, template validation rules).
- Required status checks must name contexts that actually exist; pull
  them from a real run before creating a ruleset. A ruleset requiring
  a context that never reports wedges every future PR against it.
- Leave provenance in the adapted file -- a header comment naming the
  source and the date, the way `AGENTS.md`'s own header does.

## Land it

File changes go through a worktree (skill `use-a-worktree`) and one
logical unit per PR (skill `ship`). API-only state -- rulesets, repo
settings -- never shows in a diff: record exactly what was created (id,
name, rules, required checks) in the PR body, because the PR text is
the only place that state is visible. The PR's own CI run is often the
first real exercise of ported workflow changes; a green run there
belongs in the body's "Verified" section, named as exactly that.

## See also

- `ship` and `use-a-worktree` -- landing the port, and where its
  branch lives.
- `new-skill` -- the conventions this skill file itself follows.
- Written 2026-10-31 from porting the GitHub scaffolding of the two
  repos this repo's agent tooling was extracted from.
