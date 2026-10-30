"""Capabilities a check can declare it needs.

A check with `needs=("nix",)` runs only where the capability exists. The
runner skips it otherwise -- with a printed line, never silently -- which
is the generalization of the ancestor tool's `--skip=generated` flag: a
machine without the external tool gets a stated skip instead of a red run
or a quiet hole.
"""
import shutil

_CAPABILITIES = {
    'nix': lambda: shutil.which('nix') is not None,
}


def available(name):
    probe = _CAPABILITIES.get(name)
    return probe() if probe else False
