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

# Commands the ancestor tool had under another name. A user (or a doc)
# reaching for the old verb gets the new one, not "unknown command".
RENAMED = {
    'gen-contents': (
        "`gen-contents` is now `factcheck fix-contents <page.md...>`: it "
        "takes the pages to rewrite. There is deliberately no whole-tree "
        "form, which would add Contents blocks to pages exempt from them."),
}

USAGE = """\
usage: factcheck [global options] [command]

commands:
  check                run every registered check (default)
  <check-name>         run one check (`factcheck checks` lists them)
  checks               list registered checks and fixers
  fix-contents <f...>  rewrite pages' Contents blocks (a fixer, not a check)
  fix-refs apply|dry-run [OLD=NEW...]
                       rewrite references to paths moved with `git mv`
  fix-generated <f...> rewrite generated regions from their sources
  <command> --help     that command's usage and what it does

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

    # `disabled` comes from config and is validated loosely: a config may
    # disable a check that isn't registered in this run (its plugin isn't
    # loaded here, say) without that being an error. `--skip` names are
    # validated strictly: a typo there should stop the run, not no-op it.
    disabled = cfg.disabled()
    all_findings = []
    for name, c in registry.registered():
        if cmd not in (name, 'check') or name in skip or name in disabled:
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


def _summary(name, fn):
    """What a check or fixer is, on one line: its module docstring's first
    paragraph when that opens with `<name>:` (how the modules introduce
    themselves), else the function's own docstring's."""
    import inspect

    def first(doc):
        return ' '.join((doc or '').split('\n\n')[0].split())
    mod = first(inspect.getdoc(inspect.getmodule(fn)))
    return mod if mod.startswith(f'{name}:') else first(inspect.getdoc(fn))


def _help(cmd, out):
    """`factcheck <command> --help`: that command's usage and summary;
    with no command, the general usage."""
    if cmd is None:
        out.write(USAGE)
        return 0
    if cmd in RENAMED:
        out.write(RENAMED[cmd] + '\n')
        return 0
    if cmd in fixers.FIXERS:
        out.write(fixers.USAGE.get(
            cmd, f"usage: factcheck {cmd} <file.md> [file.md ...]\n"))
        out.write(_summary(cmd, fixers.FIXERS[cmd]) + '\n')
        return 0
    if cmd in registry.CHECKS:
        out.write(f"usage: factcheck [global options] {cmd} [repo-root]\n")
        out.write(_summary(cmd, registry.CHECKS[cmd].fn) + '\n')
        return 0
    if cmd in ('check', 'checks'):
        out.write(USAGE)
        return 0
    out.write(f"unknown command {cmd!r} -- try `factcheck checks`\n")
    return 2


def main(argv=None, out=None):
    out = out or sys.stdout
    argv = sys.argv[1:] if argv is None else argv
    root_override = config_override = None
    skip = set()
    positional = []
    i = 0
    want_help = False
    while i < len(argv):
        a = argv[i]
        if a in ('-h', '--help'):
            want_help = True
            i += 1
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

    if want_help:
        return _help(positional[0] if positional else None, out)
    cmd = positional[0] if positional else 'check'
    if cmd in RENAMED:
        out.write(RENAMED[cmd] + '\n')
        return 2
    # A check command takes an optional positional repo-root --
    # `factcheck siblings /path/to/repo`, the shape hooks and scripts
    # call with. It must never be silently dropped: a root that stays
    # cwd makes the check scan the wrong repository and exit 0.
    # A fixer's arguments are its files, never the root: taking the first
    # one as the root would load config from `<page>/factcheck.toml`.
    root_arg = (positional[1] if len(positional) > 1
                and cmd not in fixers.FIXERS else None)
    root = Path(root_override or root_arg or Path.cwd()).resolve()
    if len(positional) > 1 and cmd not in ('check', *registry.names(),
                                           *fixers.FIXERS):
        out.write(f"unexpected argument {positional[1]!r} for {cmd!r}\n")
        return 2
    cfg = config.load(root, config_override)

    # Fixers rewrite files, so they take explicit paths and never join
    # `check`'s aggregate; a fixer name never collides with a check name.
    if cmd in fixers.FIXERS:
        if len(positional) < 2:
            out.write(fixers.USAGE.get(
                cmd, f"usage: factcheck {cmd} <file.md> [file.md ...]\n"))
            return 2
        return fixers.FIXERS[cmd](root, cfg, positional[1:]) or 0

    plugins.load(cfg)
    return _run_checks(cmd, root, cfg, skip, out)
