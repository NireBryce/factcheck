"""Fixture tests. Pattern inherited from the ancestor tool's suite: build a
small tree in a temp directory, break one thing at a time, assert the
finding -- a clean run against a clean tree proves nothing about the check
that would catch it. Pure stdlib; no network, no git required except where
a check reads tracked files."""
