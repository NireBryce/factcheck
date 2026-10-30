"""Example factcheck plugin: a host-roster counter source, read statically
from the nixos-configs convention (a hosts.nix where each host is one
`<name> = mkHost {...}` / `mkDarwinHost {...}` line) -- no nix evaluation,
so it runs anywhere.

Registers the `total`, `nixos` and `darwin` counters the counts check
consumes. Config:

    [roster]
    file = "flake/modules/host-config/hosts.nix"   # default shown
    name-prefix = "nire-"                          # default shown

Wire it up beside the dogfood config:

    [plugins]
    load = [".../examples/nixos-plugins/roster.py"]
"""
import re

from factcheck.checks.counts import register_counter

HOST_LINE = re.compile(r'^\s*((?:nire-)?[\w-]+)\s*=\s*(mkHost|mkDarwinHost)\b',
                       re.M)


def hosts(root, cfg):
    s = cfg.section('roster')
    p = root / s.get('file', 'flake/modules/host-config/hosts.nix')
    prefix = s.get('name-prefix', 'nire-')
    text = re.sub(r'#[^\n]*', '', p.read_text())
    out = {}
    for name, ctor in HOST_LINE.findall(text):
        if prefix and not name.startswith(prefix):
            continue  # guests and non-host entries, excluded by convention
        out[name] = 'darwin' if ctor.endswith('DarwinHost') else 'nixos'
    return out


@register_counter('total')
def total(root, cfg):
    return len(hosts(root, cfg))


@register_counter('nixos')
def nixos(root, cfg):
    return sum(1 for c in hosts(root, cfg).values() if c == 'nixos')


@register_counter('darwin')
def darwin(root, cfg):
    return sum(1 for c in hosts(root, cfg).values() if c == 'darwin')
