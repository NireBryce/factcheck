#!/usr/bin/env python3
"""Fail when a commit in a range carries a Claude Co-Authored-By trailer
that is not exactly `Co-Authored-By: Claude`.

AGENTS.md's convention: the trailer names the agent, with no model name
and no email, because an agent cannot verify which model is executing
it. `.githooks/commit-msg` rewrites the wrong shape at commit time, but
only in a clone that wired core.hooksPath. This is the layer that does
not depend on the clone: CI runs it over a PR's own commits.

The match mirrors commit-msg's pattern (`Claude`, then optionally a model
name and/or an `<email>`), with the key matched case-insensitively, as
git treats trailer keys. Only trailers naming Claude are judged; any
other agent's name-only trailer passes, since no check can know which
agent wrote a commit.

Range, not history: existing commits keep their labels, so this is only
pointed at the commits under review. In CI that is `HEAD^1..HEAD^2` of
the PR merge ref.

Usage: check_trailers.py <rev-range>. Exit 0 clean, 1 on a finding, 2 on
a git error. Stdlib plus git; tested by tests/test_check_trailers.py.

Adapted from nixos-configs' flake/scripts/check_trailers.py.
"""
import re
import subprocess
import sys

CANONICAL = "Co-Authored-By: Claude"
# commit-msg's ERE, translated:
# ^Co-Authored-By:[[:space:]]+Claude([[:space:]]+[^<]*)?([[:space:]]*<[^>]*>)?[[:space:]]*$
PATTERN = re.compile(
    r"^(?i:co-authored-by):\s+Claude(\s+[^<]*)?(\s*<[^>]*>)?\s*$")


def bad_trailers(message):
    """Lines of `message` that are a Claude co-author trailer in any form
    other than the canonical one."""
    return [line for line in message.splitlines()
            if PATTERN.match(line) and line != CANONICAL]


def commits(rev_range):
    """(sha, subject, full message) for every commit in the range, merges
    included -- a merge commit on a PR branch is that PR's own too."""
    out = subprocess.run(
        ["git", "log", "--format=%H%x00%s%x00%B%x1e", rev_range],
        capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write(out.stderr)
        sys.exit(2)
    for record in out.stdout.split("\x1e"):
        record = record.lstrip("\n")
        if record:
            sha, subject, body = record.split("\x00", 2)
            yield sha, subject, body


def main(argv):
    if len(argv) != 2:
        sys.exit("usage: check_trailers.py <rev-range>")
    found, count = [], 0
    for sha, subject, body in commits(argv[1]):
        count += 1
        for line in bad_trailers(body):
            found.append((sha, subject, line))
    if found:
        print("Co-Authored-By trailer not in the canonical form "
              f"`{CANONICAL}` (no model name, no email):", file=sys.stderr)
        for sha, subject, line in found:
            print(f"  {sha[:12]} {subject}\n      {line}", file=sys.stderr)
        print("Reword those commits (amend the tip, or rebuild the branch) "
              "and force-push the PR branch. `git config core.hooksPath "
              ".githooks` makes .githooks/commit-msg fix this at commit "
              "time.",
              file=sys.stderr)
        return 1
    print(f"trailers ok: {count} commit(s) in {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
