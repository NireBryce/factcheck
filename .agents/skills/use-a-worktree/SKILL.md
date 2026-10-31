---
name: use-a-worktree
description: Sets up an isolated git worktree so work doesn't happen in the shared checkout.
when_to_use: Before any task that will branch, commit, merge or check out, at the first git command that moves a branch or changes what's checked out.
---

# Working in a worktree

## Applies to

The first time in a session that you are about to run a git command
that changes what is checked out or what a branch points at: `checkout
-b`, `commit`, `merge`, `branch -f`/`-d`. Not for read-only work:
reading files, running `scripts/check` on what is checked out, grepping.

Stay in the shared checkout when:

- the user names it or says to work there;
- the task is about the shared checkout's own state;
- you already made a worktree for this branch earlier in the
  conversation (one per task, not one per command).

## Why

Two sessions sharing one checkout see each other's `checkout`, commits
and branch deletions mid-task: files revert, branches change underneath,
and `git branch -f` fails because the branch is checked out in the other
session's directory. A worktree has its own directory and `HEAD` and
shares everything else (branches, objects, `git worktree list`).

## How

**Subagents under Claude Code:** pass `isolation: "worktree"` to the
Agent tool. That needs `.claude/` to be a real directory, which it is
here.

**Create**, based on `origin/main`:

```sh
git -C <repo> fetch origin
git -C <repo> worktree add <scratch>/wt-<branch> -b <branch> origin/main
```

`<scratch>` is the scratch directory your harness names, or `/tmp`.
Verify you are in it (`git -C <path> status -sb`) before anything that
changes state. A shell tool can reset cwd between calls, so use absolute
paths or `git -C`.

**Already edited in the shared checkout?** Move the edits instead of
committing there, and only when every dirty path is yours:

```sh
git -C <repo> status --short     # anything not yours: stop and ask
git -C <repo> diff > <scratch>/x.patch   # `git add -N` new files first
git -C <worktree> apply <scratch>/x.patch
git -C <repo> stash push -m "<what>"     # then drop, once the worktree has them
```

**Check a commit without moving a branch:** `git worktree add --detach
<path> <sha>`.

**Git inside a hook** run from a worktree: use `git -C "$repo_root"`, not
`cd` plus a cleared `GIT_DIR`. An inherited `GIT_DIR` retargets git at
the wrong root (nixos-configs §44).

**Clean up** when the work has shipped or been abandoned:

```sh
git -C <repo> worktree remove --force <path>
git -C <repo> branch -d <branch>     # fails while a worktree holds it
```

Glance at `git worktree list` at session start; the session-start hook
prints it. Don't remove a worktree you don't recognize without checking
`git -C <path> status`. It may belong to a live session.

## See also

- `ship`: step 1 uses throwaway detached worktrees.
- Adapted from nixos-configs' `use-a-worktree` skill.
