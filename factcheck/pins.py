"""Pins: prose regions named by structure, so references to "where"
survive the edits that move lines. (The `pins` check that enforces
them lives in checks/pins.py; this module is the engine the pin tools
and plugins share.)

A pin is one entry of the `[[pins]]` array in the config file: an `id`,
a repo-relative `file`, and exactly one selector -- a 1-based `line`; a
`start` (and optional `end`) pair of literal substrings matched per
line; or a `heading`, optionally disambiguated by `level`, naming the
section to resolve. An optional `contains` is a substring the resolved
region must hold: the tripwire that turns "the region moved" into a
finding instead of a silently re-anchored selector.

Pins exist so external tests and tooling can cite a region of prose in
version control without pinning line numbers that any edit invalidates
(#22): `factcheck pin-gen` resolves a selector against today's file and
prints -- or, with `--write`, appends -- the pin's TOML; `factcheck
pin-show` prints where every pin resolves today; and the `pins` check
makes a pin that no longer resolves, or whose `contains` text vanished,
a hard finding.

Uniqueness is deliberate: a `start` or `heading` matching more than one
line is AMBIGUOUS rather than resolved to the first hit, because a
selector that silently re-anchors to an earlier duplicate when prose
moves above it is the drift a pin exists to catch.
"""
import re

from .mdcore import fences

HEADING = re.compile(r'^(#{1,6})\s+(.+?)\s*$')

SELECTOR_KEYS = ('line', 'start', 'heading')
PIN_KEYS = {'id', 'file', 'contains', 'level', 'end', *SELECTOR_KEYS}


class PinError(ValueError):
    """A pin that cannot be interpreted or resolved. `tag` names the
    finding the pins check turns it into -- BAD PIN for malformed
    tables, UNKNOWN PIN FILE, UNRESOLVED PIN, AMBIGUOUS PIN otherwise.
    The CLI pin tools exit 2 on it."""

    def __init__(self, message, tag='UNRESOLVED PIN'):
        super().__init__(message)
        self.tag = tag


def parse_pin(pin, where):
    """One `[[pins]]` table, validated: keys known, `id` and `file`
    present, exactly one selector. Raises PinError (BAD PIN) naming
    `where`."""
    if not isinstance(pin, dict):
        raise PinError(f"{where}: not a [[pins]] table", 'BAD PIN')
    unknown = sorted(set(pin) - PIN_KEYS)
    if unknown:
        raise PinError(f"{where}: unknown key(s): {', '.join(unknown)}",
                       'BAD PIN')
    for key in ('id', 'file'):
        if not isinstance(pin.get(key), str) or not pin[key]:
            raise PinError(f"{where}: {key} must be a non-empty string",
                           'BAD PIN')
    where = f"pin {pin['id']!r}"
    present = [k for k in SELECTOR_KEYS if k in pin]
    if len(present) != 1:
        raise PinError(f"{where}: exactly one of line/start/heading is "
                       f"required (got {present or 'none'})", 'BAD PIN')
    if 'end' in pin and 'start' not in pin:
        raise PinError(f"{where}: end needs start", 'BAD PIN')
    if 'level' in pin and 'heading' not in pin:
        raise PinError(f"{where}: level needs heading", 'BAD PIN')
    for key in ('line', 'level'):
        v = pin.get(key)
        if key in pin and (isinstance(v, bool) or not isinstance(v, int)):
            raise PinError(f"{where}: {key} must be an integer", 'BAD PIN')
    for key in ('start', 'end', 'contains'):
        if key in pin and (not isinstance(pin[key], str) or not pin[key]):
            raise PinError(f"{where}: {key} must be a non-empty string",
                           'BAD PIN')
    if 'line' in pin and pin['line'] < 1:
        raise PinError(f"{where}: line must be >= 1", 'BAD PIN')
    if 'level' in pin and not 1 <= pin['level'] <= 6:
        raise PinError(f"{where}: level must be 1..6", 'BAD PIN')
    return pin


def parse(pins):
    """The `[[pins]]` tables, validated, ids unique."""
    out, seen = [], set()
    for i, pin in enumerate(pins or []):
        pin = parse_pin(pin, f"[[pins]] #{i + 1}")
        if pin['id'] in seen:
            raise PinError(f"duplicate pin id {pin['id']!r}", 'BAD PIN')
        seen.add(pin['id'])
        out.append(pin)
    return out


def resolve(root, pin):
    """(lo, hi, lines) for pin's selector -- 1-based, inclusive -- or
    PinError saying why it doesn't resolve. Heading lines are found
    through the fence-aware scanner, so a `# comment` in a ```sh block
    never masquerades as the heading a pin names."""
    path = root / pin['file']
    try:
        text = path.read_text()
    except OSError as e:
        raise PinError(f"{pin['file']}: {e.strerror or e}",
                       'UNKNOWN PIN FILE')
    lines = text.splitlines()

    if 'line' in pin:
        if pin['line'] > len(lines):
            raise PinError(f"{pin['file']}: line {pin['line']} of a "
                           f"{len(lines)}-line file")
        return pin['line'], pin['line'], lines

    if 'start' in pin:
        hits = [n for n, l in enumerate(lines, 1) if pin['start'] in l]
        if not hits:
            raise PinError(f"{pin['file']}: start {pin['start']!r} "
                           f"matches no line")
        if len(hits) > 1:
            raise PinError(f"{pin['file']}: start {pin['start']!r} "
                           f"matches {len(hits)} lines "
                           f"(first {hits[0]}, last {hits[-1]})",
                           'AMBIGUOUS PIN')
        lo = hits[0]
        if 'end' not in pin:
            return lo, lo, lines
        after = [n for n, l in enumerate(lines[lo:], lo + 1)
                 if pin['end'] in l]
        if not after:
            raise PinError(f"{pin['file']}: end {pin['end']!r} matches "
                           f"no line after {lo}")
        if len(after) > 1:
            raise PinError(f"{pin['file']}: end {pin['end']!r} matches "
                           f"{len(after)} lines after {lo} "
                           f"(first {after[0]}, last {after[-1]})",
                           'AMBIGUOUS PIN')
        return lo, after[0], lines

    want, level = pin['heading'], pin.get('level')
    matches = []
    for no, line, fenced in fences.iter_lines(text):
        if fenced:
            continue
        m = HEADING.match(line)
        if m and m.group(2).strip() == want and level in (None, len(m.group(1))):
            matches.append((no, len(m.group(1))))
    label = f"heading {want!r}" + (f" at level {level}" if level else '')
    if not matches:
        raise PinError(f"{pin['file']}: no {label}")
    if len(matches) > 1:
        raise PinError(f"{pin['file']}: {len(matches)} {label} lines "
                       f"(first {matches[0][0]}) -- set level",
                       'AMBIGUOUS PIN')
    lo, lvl = matches[0]
    hi = len(lines)
    for no, line, fenced in fences.iter_lines(text):
        if fenced or no <= lo:
            continue
        m = HEADING.match(line)
        if m and len(m.group(1)) <= lvl:
            hi = no - 1
            break
    return lo, hi, lines


def span_text(lines, lo, hi):
    """The pinned region's text, for a contains check or a preview."""
    return '\n'.join(lines[lo - 1:hi])
