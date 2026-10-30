"""Fixers: commands that rewrite files, as opposed to checks that report.

A fixer is deliberately not part of `check`'s aggregate and never gates a
run -- the ancestor tool split `gen-contents` out of its checks for
exactly this reason, and several real findings (`STALE CONTENTS`) name
their fixer in the message. Registration is a separate table from the
check registry on purpose: the two kinds share nothing but the CLI.
"""
FIXERS = {}


def fixer(name):
    """Registers `fn(root, cfg, args) -> None` as the `name` subcommand."""
    def register(fn):
        assert name not in FIXERS, f"fixer {name!r} registered twice"
        FIXERS[name] = fn
        return fn
    return register
