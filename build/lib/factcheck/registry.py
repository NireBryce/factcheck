"""The check registry.

`@check("name")` on `fn(root, cfg) -> [Finding]` makes `fn` the subcommand
`name` and part of `check`'s aggregate run. There is no second list of
names to keep in step: a check that isn't registered isn't a subcommand,
and one that is registered can't be missing from either.

`order` fixes where a check's findings print in `check`'s combined output;
a check without one runs after all ordered checks, in registration order.

`needs` names capabilities the check requires (e.g. `needs=("nix",)` --
see `capabilities`). A check whose capability is unavailable is skipped,
with a line saying so; it is never silently absent.

Re-registration semantics, kept deliberately from this registry's ancestor:
a plugin module may be exec'd afresh (a new function object each time), so
the same module+qualname *replaces* its entry and keeps the original
registration sequence; a *different* function under a taken name is a bug
and asserts.
"""
CHECKS = {}
_UNORDERED = 10_000


class Check:
    """A registered check: its name, print order, registration sequence,
    function, and required capabilities."""

    def __init__(self, name, order, seq, fn, needs):
        self.name = name
        self.order = order
        self.seq = seq
        self.fn = fn
        self.needs = tuple(needs)


def check(name, order=None, needs=()):
    """Registers `fn(root, cfg) -> [Finding]` as the subcommand `name`."""
    def register(fn):
        old = CHECKS.get(name)
        if old is not None:
            same = (old.fn.__module__, old.fn.__qualname__) == (
                fn.__module__, fn.__qualname__)
            assert same, f"check {name!r} registered twice"
        CHECKS[name] = Check(
            name,
            _UNORDERED if order is None else order,
            old.seq if old else len(CHECKS),
            fn,
            needs)
        return fn
    return register


def registered():
    """[(name, Check)] in run order."""
    return [(c.name, c) for c in
            sorted(CHECKS.values(), key=lambda c: (c.order, c.seq))]


def names():
    """Registered check names, in run order."""
    return [name for name, _ in registered()]
