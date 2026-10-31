"""Fixers: commands that rewrite files, as opposed to checks that report.

A fixer is deliberately not part of `check`'s aggregate and never gates a
run -- the ancestor tool split `gen-contents` out of its checks for
exactly this reason, and several real findings (`STALE CONTENTS`) name
their fixer in the message. Registration is a separate table from the
check registry on purpose: the two kinds share nothing but the CLI.
"""
FIXERS = {}
# Per-fixer usage line, for a fixer whose arguments aren't files.
USAGE = {}


def fixer(name, usage=None):
    """Registers `fn(root, cfg, args) -> int | None` as the `name`
    subcommand. A returned int is the exit status (None means 0); `usage`
    replaces the default `<file.md> [file.md ...]` usage line."""
    def register(fn):
        assert name not in FIXERS, f"fixer {name!r} registered twice"
        FIXERS[name] = fn
        if usage:
            USAGE[name] = usage
        return fn
    return register
