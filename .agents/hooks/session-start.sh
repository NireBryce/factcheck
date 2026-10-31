#!/usr/bin/env bash
# SessionStart hook (Claude Code). Puts the repo state AGENTS.md asks an
# agent to check -- branch, whether this is a linked worktree, dirty-path
# count, `git worktree list` -- into context before the first tool call,
# and wires .githooks/ when core.hooksPath is unset (same command as in
# AGENTS.md "Commands"; repo-local, idempotent). A different existing
# value is reported and left alone.
#
# Never fails: no `set -e`, every git call guarded, exit 0 always. Plain
# stdout, which SessionStart adds to the agent's context.
#
# Adapted from nixos-configs' .agents/hooks/session-start.sh.
set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE

root="${CLAUDE_PROJECT_DIR:-$PWD}"
root=$(git -C "$root" rev-parse --show-toplevel 2>/dev/null) || exit 0

branch=$(git -C "$root" branch --show-current 2>/dev/null)
echo "branch: ${branch:-(detached)}"

gitdir=$(git -C "$root" rev-parse --git-dir 2>/dev/null)
common=$(git -C "$root" rev-parse --git-common-dir 2>/dev/null)
if [ -n "$gitdir" ] && [ "$gitdir" != "$common" ]; then
    echo "checkout: linked worktree ($root)"
else
    echo "checkout: shared checkout ($root) -- work that branches or commits goes in a worktree (skill use-a-worktree)"
fi

dirty=$(git -C "$root" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
echo "dirty paths: $dirty"

hooks=$(git -C "$root" config --get core.hooksPath 2>/dev/null)
if [ -z "$hooks" ]; then
    if git -C "$root" config core.hooksPath .githooks 2>/dev/null; then
        echo "core.hooksPath: was unset, now .githooks (commit-msg, pre-push)"
    else
        echo "core.hooksPath: unset, and setting it failed -- run: git config core.hooksPath .githooks"
    fi
elif [ "$hooks" != ".githooks" ]; then
    echo "core.hooksPath: $hooks (not .githooks; left alone, so this repo's hooks don't run)"
fi

echo "worktrees:"
git -C "$root" worktree list 2>/dev/null | sed 's/^/  /'
exit 0
