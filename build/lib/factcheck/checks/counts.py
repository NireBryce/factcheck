"""counts: prose count claims ("all five hosts", "two of the three NixOS
hosts") against actual counts.

The claims rot silently -- a roster change doesn't read the prose that
totals it -- so the check extracts the claim shapes and compares them to
a *counter*: a registered Python function (from a plugin, e.g. a roster
parser) or a config-declared value (`total = 5`, or `{ glob = "..." }`
counting files). The claim shapes are the general part: "all N <thing>",
"all N <class> <thing>", "M of the N <class> <thing>" -- with the class
scoping and the deliberate "all"/"of the" requirement that keeps
historical prose ("three hosts were removed") out of scope."""
import re

from ..findings import Finding
from ..registry import check

NUM = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+)'
NUMWORD = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
           'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11,
           'twelve': 12}

# name -> fn(root, cfg) -> int, from plugins. Config-declared counters
# (static ints, {glob = ...}) need no registration.
COUNTERS = {}


def register_counter(name):
    """Decorator registering `fn(root, cfg) -> int` as counter `name`."""
    def register(fn):
        COUNTERS[name] = fn
        return fn
    return register


def _claim_patterns(noun, classes):
    def w(word):
        return re.escape(word)
    cls = '|'.join(w(c) for c in classes)
    return [
        # "all five hosts", "all 4 hosts" -> the total counter
        (re.compile(rf'\ball ({NUM}) {w(noun)}\b', re.I), 'total'),
        # "all three nixos hosts" -> that class's counter
        (re.compile(rf'\ball ({NUM}) ({cls}) {w(noun)}\b', re.I), 'class'),
        # "Two of the three nixos hosts" -> M only checked against N; N
        # against the class (what M counts is claim-specific prose)
        (re.compile(rf'\b({NUM}) of the ({NUM}) ({cls}) {w(noun)}\b', re.I),
         'of-class'),
    ]


def _num(word):
    return NUMWORD.get(word.lower()) or int(word)


def _counter_value(name, root, cfg):
    # Config declares win over registered plugins: an explicit number in
    # factcheck.toml is the repo's word over whatever a plugin guesses.
    declared = cfg.section('counts').get('counters', {}).get(name)
    if isinstance(declared, int):
        return declared
    if isinstance(declared, dict) and 'glob' in declared:
        return len(list(root.glob(declared['glob'])))
    if name in COUNTERS:
        return COUNTERS[name](root, cfg)
    return None


@check('counts', order=120)
def check_counts(root, cfg):
    s = cfg.section('counts')
    noun = s.get('noun', 'hosts')
    classes = [c.lower() for c in s.get('classes', ['nixos', 'darwin'])]
    source = s.get('source', 'hosts.nix')
    counters = {'total': s.get('total-counter', 'total')}
    counters.update({c: s.get(f'{c}-counter', c) for c in classes})

    if not (s.get('counters') or any(name in COUNTERS
                                     for name in counters.values())):
        # Nothing feeds the counts: the check is a no-op here, the same
        # way recipes is on a repo with no justfile.
        return []
    values = {key: _counter_value(name, root, cfg)
              for key, name in counters.items()}
    if any(v is None for v in values.values()):
        missing = sorted(k for k, v in values.items() if v is None)
        return [Finding(
            'NO COUNTER', source,
            f"no counter for {', '.join(missing)} -- register one from a "
            f"plugin or declare it under [counts.counters]")]

    findings = []
    for path in cfg.scope('docs'):
        text = path.read_text()
        for rx, kind in _claim_patterns(noun, classes):
            for m in rx.finditer(text):
                words = [g for g in m.groups() if g is not None]
                if kind == 'total':
                    claimed, actual = _num(words[0]), values['total']
                    if claimed != actual:
                        findings.append(Finding(
                            'STALE', str(path),
                            f"'{m.group(0)}' says {claimed} {noun} but "
                            f"{source} defines {actual}", sep='    '))
                elif kind == 'class':
                    cls = words[1].lower()
                    claimed, actual = _num(words[0]), values[cls]
                    if claimed != actual:
                        findings.append(Finding(
                            'STALE', str(path),
                            f"'{m.group(0)}' says {claimed} {cls} {noun} "
                            f"but {source} defines {actual}", sep='    '))
                else:
                    lead = _num(words[0])
                    total, cls = _num(words[1]), words[2].lower()
                    if lead > total:
                        findings.append(Finding(
                            'STALE', str(path),
                            f"'{m.group(0)}' -- {lead} exceeds {total}",
                            sep='    '))
                    if total != values[cls]:
                        findings.append(Finding(
                            'STALE', str(path),
                            f"'{m.group(0)}' says {total} {cls} {noun} but "
                            f"{source} defines {values[cls]}", sep='    '))
    return findings
