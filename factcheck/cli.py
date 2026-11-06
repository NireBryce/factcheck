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

from . import capabilities, checks, config, fixers, gitfiles, plugins, registry
from .findings import Finding, see_lines

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
  pin-gen <file> ...   print (or --write: append) a pin's TOML, resolved
                       against today's file
  pin-show [ID]        where each configured pin resolves today
  <command> --help     that command's usage and what it does

global options:
  --root PATH          repository to check (default: cwd)
  --config PATH        config file location (default: <root>/.agents/factcheck;
                       legacy <root>/factcheck.toml still read)
  --skip=a,b           leave named checks out of `check`
"""

# The pin tools are neither checks nor fixers: they read config and prose
# and write nothing but a pin's own TOML. Named in one place so the root
# and argument handling in main() treats them alike.
PIN_TOOLS = ('pin-gen', 'pin-show')

PIN_TOOL_HELP = {
    'pin-gen': (
        "usage: factcheck pin-gen <file> --id NAME "
        "(--line N | --start S [--end E] | --heading NAME [--level N]) "
        "[--contains TEXT] [--write]\n"
        "pin-gen: resolve a selector against the file as it stands today "
        "and print the pin's TOML (--write appends it to the config "
        "file). contains is filled with the region's first non-blank "
        "line unless given, so every generated pin is a drift tripwire."),
    'pin-show': (
        "usage: factcheck pin-show [ID]\n"
        "pin-show: print where every configured pin resolves today, as "
        "`id file:lo-hi` plus a preview; exit 1 when any pin does not "
        "resolve, so external tooling can treat that as drift."),
}


def _capability_skips():
    """{name: capability} for checks whose capability isn't available."""
    out = {}
    for name, c in registry.registered():
        missing = [n for n in c.needs if not capabilities.available(n)]
        if missing:
            out[name] = missing[0]
    return out


class _BadCheckResult(Exception):
    """A check returned something other than an iterable of Findings."""


def _findings_of(name, c, result):
    """`result` as a list of Findings, or _BadCheckResult naming the check.

    A plugin that cannot import factcheck (a stdlib-only hook module) can
    hand back plain strings, and a check that forgets `return` hands back
    None. Without this, the run died later in `see_lines` with an
    AttributeError that named neither the check nor its plugin."""
    where = f"check {name!r} ({c.fn.__module__}.{c.fn.__qualname__})"
    want = "; a check must return a list of factcheck.findings.Finding"
    if (result is None or isinstance(result, (str, bytes))
            or not hasattr(result, '__iter__')):
        raise _BadCheckResult(
            f"{where} returned {type(result).__name__}{want}")
    items = list(result)
    bad = sorted({type(f).__name__ for f in items
                  if not isinstance(f, Finding)})
    if bad:
        raise _BadCheckResult(
            f"{where} returned a list containing {', '.join(bad)}{want}")
    return items


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

    # `disabled` is validated strictly too, like --skip: the config
    # records decisions, and a name nothing answers to is a stale
    # decision the run should surface, not silently drop. It sits after
    # plugins.load (cli.main), so plugin-registered names are legal here.
    disabled = cfg.disabled()
    if (unknown := disabled - set(registry.names())):
        out.write(f"unknown check(s) in [checks] disabled: "
                  f"{sorted(unknown)}\n")
        return 2
    all_findings = []
    no_git = []
    # A check named as the command while switched off would fall through
    # the loop and read as "no findings" -- a false claim, the wrong-repo
    # green in miniature. The aggregate stays silent (the config is the
    # record); a direct invocation is refused loudly, like a check that
    # could not run.
    if cmd != 'check' and (cmd in disabled or cmd in skip):
        how = ('[checks] disabled' if cmd in disabled else '--skip')
        out.write(f"{cmd}: switched off by {how} -- refusing to report a "
                  f"findings-less pass; remove it there or run `check`\n")
        return 2
    for name, c in registry.registered():
        if cmd not in (name, 'check') or name in skip or name in disabled:
            continue
        if name in cap_skip:
            out.write(f"{name}: skipped (needs {cap_skip[name]}, "
                      f"unavailable here)\n")
            continue
        try:
            all_findings += _findings_of(name, c, c.fn(root, cfg))
        except gitfiles.NotAGitCheckout as e:
            out.write(f"{name}: skipped -- {e}; it reads git-tracked "
                      f"files\n")
            no_git.append(name)
        except _BadCheckResult as e:
            out.write(f"{e}\n")
            return 2

    if cmd == 'check' and skip:
        out.write(f"check: skipped {', '.join(sorted(skip))} (--skip)\n")

    for f in all_findings:
        out.write(str(f) + '\n')
    for line in see_lines(all_findings):
        out.write(line + '\n')
    hard = [f for f in all_findings if not f.review]
    if no_git:
        pass  # the could-not-run line below is the status
    elif not all_findings:
        out.write(f"{cmd}: no findings\n")
    elif not hard:
        out.write(f"{cmd}: only REVIEW findings (heuristic, needs a human "
                  f"look) -- not failing on those alone\n")
    if no_git:
        # A check that couldn't run is not a pass: say so in the status.
        out.write(f"{cmd}: {len(no_git)} check(s) could not run without "
                  f"a git checkout -- pass the repository with --root\n")
        return 2
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
    if cmd in PIN_TOOLS:
        out.write(PIN_TOOL_HELP[cmd] + '\n')
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
            # After a pin tool's command word, unknown --flags are the
            # tool's own (--id, --heading, ...), parsed there; anywhere
            # else an unknown flag is an error, as it always was.
            if positional and positional[0] in PIN_TOOLS:
                positional.append(a)
                i += 1
            else:
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
    # A fixer's or pin tool's arguments are its files, never the root:
    # taking the first one as the root would load config from
    # `<page>/.agents/factcheck`.
    root_arg = (positional[1] if len(positional) > 1
                and cmd not in fixers.FIXERS and cmd not in PIN_TOOLS
                else None)
    root = Path(root_override or root_arg or Path.cwd()).resolve()
    if not root.is_dir():
        given = root_override or root_arg
        out.write(f"not a directory: {given} -- `{cmd}` takes an optional "
                  f"repository root (or --root); to run one check, name it "
                  f"(`factcheck checks` lists them)\n")
        return 2
    if len(positional) > 1 and cmd not in ('check', *registry.names(),
                                           *fixers.FIXERS, *PIN_TOOLS):
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

    # The pin tools read config and prose and print; they need no plugin
    # registrations, so they dispatch before plugins load.
    if cmd in PIN_TOOLS:
        return _pin_tool(cmd, root, cfg, positional[1:], out)

    plugins.load(cfg)
    return _run_checks(cmd, root, cfg, skip, out)


def _pin_tool(cmd, root, cfg, args, out):
    from . import pins as pins_mod

    if cmd == 'pin-show':
        return _pin_show(root, cfg, args, out)

    flags, positional = {}, []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--write':
            flags['write'] = 'yes'
            i += 1
        elif a.startswith('--') and '=' in a:
            flags.setdefault(a[2:].split('=', 1)[0],
                             a.split('=', 1)[1])
            i += 1
        elif a.startswith('--'):
            if i + 1 >= len(args):
                out.write(f"{a} needs a value\n" + PIN_TOOL_HELP['pin-gen'])
                return 2
            flags[a[2:]] = args[i + 1]
            i += 2
        else:
            positional.append(a)
            i += 1
    unknown = sorted(set(flags) - {'id', 'line', 'start', 'end', 'heading',
                                   'level', 'contains', 'write'})
    if unknown:
        out.write(f"unknown flag(s): {', '.join(unknown)}\n"
                  + PIN_TOOL_HELP['pin-gen'])
        return 2
    if len(positional) != 1 or not positional[0]:
        out.write(PIN_TOOL_HELP['pin-gen'])
        return 2
    if not flags.get('id'):
        out.write("pin-gen needs --id NAME\n" + PIN_TOOL_HELP['pin-gen'])
        return 2
    file_arg = positional[0]
    if Path(file_arg).is_absolute():
        out.write(f"pin files are repo-relative: {file_arg}\n")
        return 2
    pin = {'id': flags['id'], 'file': file_arg}
    for int_flag in ('line', 'level'):
        if int_flag in flags:
            try:
                pin[int_flag] = int(flags[int_flag])
            except ValueError:
                out.write(f"--{int_flag} must be an integer: "
                          f"{flags[int_flag]!r}\n")
                return 2
    for str_flag in ('start', 'end', 'heading', 'contains'):
        if str_flag in flags:
            pin[str_flag] = flags[str_flag]
    try:
        pins_mod.parse_pin(pin, f"pin {pin['id']!r}")
        lo, hi, lines = pins_mod.resolve(root, pin)
    except pins_mod.PinError as e:
        out.write(f"will not generate an unresolvable pin: {e}\n")
        return 2
    if 'contains' not in pin:
        span = pins_mod.span_text(lines, lo, hi).splitlines()
        if 'heading' in pin:
            # The heading line is already guarded by the heading selector
            # itself; tripwire on the body's first line instead.
            span = span[1:]
        first = next((l.strip() for l in span if l.strip()), '')
        if first:
            pin['contains'] = first

    def toml_str(s):
        import json
        return json.dumps(s)

    block = ['[[pins]]', f"id = {toml_str(pin['id'])}",
             f"file = {toml_str(pin['file'])}"]
    for key in ('line', 'start', 'end', 'heading', 'level', 'contains'):
        if key in pin:
            block.append(f"{key} = " + (str(pin[key])
                                        if isinstance(pin[key], int)
                                        else toml_str(pin[key])))
    text = '\n'.join(block) + '\n'
    if flags.get('write'):
        target = (cfg.source if cfg.source and cfg.source.is_file()
                  else root / config.CONFIG_FILE)
        target.parent.mkdir(parents=True, exist_ok=True)
        sep = '' if not target.exists() or \
            target.read_text().endswith('\n') else '\n'
        with open(target, 'a') as f:
            f.write(sep + text)
        out.write(f"wrote {target}:\n{text}")
    else:
        out.write(text)
        out.write(f"-- append to {cfg.source or root / config.CONFIG_FILE} "
                  f"or rerun with --write\n")
    return 0


def _pin_show(root, cfg, args, out):
    from . import pins as pins_mod

    try:
        all_pins = pins_mod.parse(cfg.section('pins'))
    except pins_mod.PinError as e:
        out.write(f"{e}\n")
        return 2
    if args:
        wanted = set(args)
        all_pins = [p for p in all_pins if p['id'] in wanted]
        missing = wanted - {p['id'] for p in all_pins}
        if missing:
            out.write(f"no such pin(s): {', '.join(sorted(missing))}\n")
            return 2
    if not all_pins:
        out.write("no pins configured\n")
        return 0
    failures = 0
    for pin in all_pins:
        try:
            lo, hi, lines = pins_mod.resolve(root, pin)
        except pins_mod.PinError as e:
            out.write(f"{pin['id']} {pin['file']}: {e}\n")
            failures += 1
            continue
        preview = next((l.strip() for l in
                        pins_mod.span_text(lines, lo, hi).splitlines()
                        if l.strip()), '')
        if len(preview) > 72:
            preview = preview[:69] + '...'
        out.write(f"{pin['id']} {pin['file']}:{lo}-{hi}  {preview}\n")
    return 1 if failures else 0
