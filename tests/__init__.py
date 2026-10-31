"""Fixture tests. Pattern inherited from the ancestor tool's suite: build a
small tree in a temp directory, break one thing at a time, assert the
finding -- a clean run against a clean tree proves nothing about the check
that would catch it. Pure stdlib; no network, no git required except where
a check reads tracked files."""

from .helpers import strip_inherited_git_env

# Before any test module loads: a test must never reach the repo a git
# hook ran it from (see helpers.REPO_LOCAL_GIT_ENV).
strip_inherited_git_env()
