"""Argument handling and dispatch.

The subcommand table IS the check registry: `factcheck <check-name>` runs
one check, `factcheck check` runs them all in registered order, and
`factcheck checks` lists what is registered (built-ins and plugins). A
`--skip=name` that names no check is an error, not a no-op, and every
skip -- explicit or capability-driven -- is printed, never silent.

Exit codes: 0 = clean or only REVIEW findings (stated in the output), 1 =
any hard finding, 2 = usage error.
"""
import sys
from pathlib import Path

from . import capabilities, checks, config, fixers, plugins, registry
from .findings import see_lines

USAGE = """\
usage: factcheck [global options] [command]

commands:
  check                run every registered check (default)
  <check-name>         run one check (`factcheck checks` lists them)
  checks               list registered checks and fixers
  fix-contents <f...>  rewrite pages' Contents blocks (a fixer, not a check)

global options:
  --root PATH          repository to check (default: cwd)
  --config PATH        factcheck.toml location (default: <root>/factcheck.toml)
  --skip=a,b           leave named checks out of `check`
"""


def _capability_skips():
    """{name: capability} for checks whose capability isn't available."""
    out = {}
    for name, c in registry.registered():
        missing = [n for n in c.needs if not capabilities.available(n)]
        if missing:
            out[name] = missing[0]
    return out


def _run_checks(cmd, root, cfg, skip, out):
    if cmd == 'checks':
        for name, c in registry.registered():
            needs = f"  (needs {', '.join(c.needs)})" if c.needs else ''
            out.write(f"{name}{needs}\n")
        if fixers.FIXERS:
            out.write('fixers: ' + ', '.join(sorted(fixers.FIXERS)) + '\n')
        return 0

    cap_skip = _capability_skips()
    if (unknown := skip - set(registry.names())):
        out.write(f"unknown check(s) in --skip: {sorted(unknown)}\n")
        return 2
    if cmd != 'check' and cmd not in registry.names():
        out.write(f"unknown command {cmd!r} -- try `factcheck checks`\n")
        return 2

    all_findings = []
    for name, c in registry.registered():
        if cmd not in (name, 'check') or name in skip:
            continue
        if name in cap_skip:
            out.write(f"{name}: skipped (needs {cap_skip[name]}, "
                      f"unavailable here)\n")
            continue
        all_findings += c.fn(root, cfg)

    if cmd == 'check' and skip:
        out.write(f"check: skipped {', '.join(sorted(skip))} (--skip)\n")

    for f in all_findings:
        out.write(str(f) + '\n')
    for line in see_lines(all_findings):
        out.write(line + '\n')
    hard = [f for f in all_findings if not f.review]
    if not all_findings:
        out.write(f"{cmd}: no findings\n")
    elif not hard:
        out.write(f"{cmd}: only REVIEW findings (heuristic, needs a human "
                  f"look) -- not failing on those alone\n")
    return 1 if hard else 0


def main(argv, out=None):
    out = out or sys.stdout
    root_override = config_override = None
    skip = set()
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('-h', '--help'):
            out.write(USAGE)
            return 0
        elif a == '--root':
            root_override = argv[i + 1]
            i += 2
        elif a.startswith('--root='):
            root_override = a[len('--root='):]
            i += 1
        elif a == '--config':
            config_override = argv[i + 1]
            i += 2
        elif a.startswith('--config='):
            config_override = a[len('--config='):]
            i += 1
        elif a.startswith('--skip='):
            skip |= {s for s in a[len('--skip='):].split(',') if s}
            i += 1
        elif a.startswith('-'):
            out.write(f"unknown flag {a}\n" + USAGE)
            return 2
        else:
            positional.append(a)
            i += 1

    cmd = positional[0] if positional else 'check'
    root = Path(root_override).resolve() if root_override else Path.cwd()
    cfg = config.load(root, config_override)

    # Fixers rewrite files, so they take explicit paths and never join
    # `check`'s aggregate; a fixer name never collides with a check name.
    if cmd in fixers.FIXERS:
        if len(positional) < 2:
            out.write(f"usage: factcheck {cmd} <file.md> [file.md ...]\n")
            return 2
        fixers.FIXERS[cmd](root, cfg, positional[1:])
        return 0

    plugins.load(cfg)
    return _run_checks(cmd, root, cfg, skip - cfg.disabled(), out)
