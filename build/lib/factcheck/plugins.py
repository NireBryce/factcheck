"""Loading out-of-tree check modules.

A plugin is any Python module that imports `factcheck.registry` and
decorates functions with `@check(...)` at import time -- the same
side-effect-registration the built-in checks use. Config lists them by
repo-relative path:

    [plugins]
    load = ["plugins/my-roster.py"]

Each is loaded by file path with a `factcheck_plugin_<stem>` module name,
so re-running against the same config replaces that plugin's checks (the
registry's module+qualname rule) instead of asserting -- the property that
lets callers exec the tool afresh per invocation.
"""
import importlib.util
import sys


def load(cfg):
    """Load every plugin in `[plugins] load`, in order, path relative to
    the config's root. The plugin's own directory goes on sys.path first,
    so a multi-file plugin can import its sibling modules."""
    for rel in cfg.section('plugins').get('load', []):
        path = (cfg.root / rel).resolve()
        sys.path.insert(0, str(path.parent))
        name = 'factcheck_plugin_' + path.stem.replace('-', '_')
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
