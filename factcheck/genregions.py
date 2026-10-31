"""Generated regions: tables a repo can derive from its own facts, written
into marked regions of the pages that carry them, and kept current by
generate-then-lint rather than detect-then-hand-fix.

A region is delimited in the markdown by two comment lines:

    <!-- generated:<name> -- <where its facts come from> -->
    ...table...
    <!-- /generated -->

Everything between them is rewritten on a write run, the start marker's
note included. Hand-written columns (prose nobody can derive -- a role
description, a "who imports this" note) are preserved per row, matched by
the row's key cell; a new row's hand cells start empty, which `check`
reports as a finding until someone fills them in, and a disappeared row's
hand text is reported on the write run so nothing vanishes silently.

Region definitions come from the `REGIONS` registry here: core ships the
engine, plugins ship the regions (they encode the repo's own facts --
roster files, module trees). The `generated` check wraps `run`; the
`fix-generated` fixer is the write half, calling it with `write=True`.
"""
import re

from . import capabilities
from .mdcore import fences

START = re.compile(r'(?m)^<!-- generated:([\w-]+)\b[^\n]*-->[ \t]*$')
END = '<!-- /generated -->'
REGION = re.compile(
    r'(?ms)^<!-- generated:(?P<name>[\w-]+)\b[^\n]*?-->[ \t]*\n'
    r'(?P<body>.*?)^<!-- /generated -->[ \t]*$')
END_LINE = re.compile(r'(?m)^<!-- /generated -->[ \t]*$')
CELL_SPLIT = re.compile(r'(?<!\\)\|')

# name -> Region
REGIONS = {}


def register(region):
    """Registers a Region/Block definition. Same module+name replaces, so
    a plugin exec'd afresh updates its entry instead of asserting."""
    old = REGIONS.get(region.name)
    if old is not None and old.source_file != region.source_file:
        raise AssertionError(f"region {region.name!r} registered twice")
    REGIONS[region.name] = region
    return region


class GenError(Exception):
    """A source the generator needs is missing or unreadable -- reported
    as a finding rather than rendering a table from half the facts."""


def render_table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '---|' * len(headers)]
    lines += ['| ' + ' | '.join(r) + ' |' for r in rows]
    return '\n'.join(lines)


def parse_table(body):
    """[{header: cell}, ...] for the first markdown table in `body`; [] if
    there is none (a region being adopted for the first time)."""
    lines = [l.strip() for l in body.splitlines()
             if l.strip().startswith('|')]
    if len(lines) < 2:
        return []

    def split(l):
        return [c.strip() for c in CELL_SPLIT.split(l.strip('|'))]
    headers = split(lines[0])
    return [dict(zip(headers, split(l))) for l in lines[2:]]


def _same_key(row_id, cell):
    """Does an existing row's key cell belong to `row_id`? The cell itself,
    or the id as a whole word-ish token in it, so a re-rendered key cell (a
    link target that changed, say) still finds its old hand-written
    cells."""
    return cell == row_id or row_id in re.findall(r'[\w-]+', cell)


class Region:
    """One generated table. `rows_fn(root)` yields (row_id, {header: cell})
    for the derived columns, in display order; `hand` names the columns
    carried over from the existing table. `needs` names capabilities the
    row source requires -- a region whose capability is unavailable is
    skipped with a stated REVIEW finding, never silently and never as a
    hard failure (the whole point of generating before checking is that a
    machine missing the generator's tool still checks everything else).
    `tool_name` is what the marker names as the regenerator; a plugin
    replacing an ancestor tool's regions passes that tool's command so
    rendered regions stay byte-identical across the switch."""

    source_file = '<region>'

    def __init__(self, name, page, source, headers, key, hand, rows_fn,
                 needs=(), tool_name='factcheck'):
        self.name, self.page, self.source = name, str(page), source
        self.headers, self.key, self.hand = headers, key, hand
        self.rows_fn, self.needs = rows_fn, tuple(needs)
        self.tool_name = tool_name

    def marker(self):
        note = (f'from {self.source}, by {self.tool_name}; change the '
                f'source, not this table')
        if self.hand:
            note += '. Hand-written, kept per row: ' + ', '.join(self.hand)
        return f'<!-- generated:{self.name} -- {note} -->'

    def render(self, root, old_body):
        """(region text, empty hand cells, dropped old rows)."""
        old = parse_table(old_body)
        out, empty, used = [], [], set()
        for row_id, cells in self.rows_fn(root):
            prev = next((i for i, r in enumerate(old)
                         if i not in used
                         and _same_key(row_id, r.get(self.key, ''))), None)
            if prev is not None:
                used.add(prev)
            for col in self.hand:
                cells[col] = old[prev].get(col, '') if prev is not None else ''
                if not cells[col]:
                    empty.append((row_id, col))
            out.append([cells[h] for h in self.headers])
        dropped = [r for i, r in enumerate(old) if i not in used]
        text = (self.marker() + '\n\n'
                + render_table(self.headers, out) + '\n\n' + END)
        return text, empty, dropped


class Block(Region):
    """A generated region that is not a table: `body_fn(root)` is the whole
    text, rewritten as a unit. No hand-written cells, so no dropped
    rows."""

    def __init__(self, name, page, source, body_fn, needs=(),
                 tool_name='factcheck'):
        super().__init__(name, page, source, [], None, [], None, needs,
                         tool_name)
        self.body_fn = body_fn

    def render(self, root, old_body):
        return (self.marker() + '\n\n' + self.body_fn(root) + '\n\n' + END,
                [], [])


def _unfenced(text):
    """Text with every fenced line blanked, length kept -- a marker shown
    as an example inside a fence is not a region, and offsets still index
    the original."""
    return fences.blank_fences(text)


def run(root, pages, write):
    """Walks `pages` (a file list, typically the `pages` scope) for regions.
    Returns (findings as Finding, notes) -- findings are what `check`
    fails on; notes are what a write run reports (dropped rows' hand
    text). With `write`, stale regions are rewritten in place."""
    from .findings import Finding
    findings, notes, seen = [], [], {}
    for page in pages:
        text = page.read_text()
        rel = page.relative_to(root).as_posix()
        scan = _unfenced(text)
        starts = START.findall(scan)
        ends = len(END_LINE.findall(scan))
        regions = list(REGION.finditer(scan))
        if len(starts) != len(regions) or ends != len(regions):
            findings.append(Finding(
                'BROKEN REGION', rel,
                f"{len(starts)} generated start marker(s), {ends} end "
                f"marker(s), {len(regions)} well-formed region(s) -- every "
                f"`<!-- generated:<name> ... -->` line needs its own "
                f"`{END}`"))
        new_text, pos = [], 0
        for m in regions:
            name = m.group('name')
            seen.setdefault(name, []).append(rel)
            region = REGIONS.get(name)
            if region is None:
                findings.append(Finding(
                    'UNKNOWN REGION', rel,
                    f"'generated:{name}' is not a registered region "
                    f"({', '.join(sorted(REGIONS)) or 'none registered'})"))
                continue
            if missing := [n for n in region.needs
                           if not capabilities.available(n)]:
                findings.append(Finding(
                    'REGION NEEDS', rel,
                    f"region '{name}' needs {missing[0]}, unavailable here "
                    f"-- everything else still checked", review=True))
                continue
            try:
                fresh, empty, dropped = region.render(
                    root, text[m.start('body'):m.end('body')])
            except GenError as e:
                findings.append(Finding(
                    'GEN ERROR', rel, f"region '{name}': {e}"))
                continue
            for row_id, col in empty:
                findings.append(Finding(
                    'EMPTY HAND CELL', rel,
                    f"region '{name}' row '{row_id}' has no {col} -- it is "
                    f"hand-written; fill it in (the generated columns come "
                    f"from {region.source})"))
            if fresh != text[m.start():m.end()]:
                if write:
                    for r in dropped:
                        if not any(r.get(c) for c in region.hand):
                            continue  # nothing hand-written was lost
                        notes.append(
                            f"dropped  {rel}: region '{name}' row "
                            f"{r.get(region.key, '?')!r} (no longer in "
                            f"{region.source}); its hand cells were "
                            f"{ {c: r.get(c, '') for c in region.hand} }")
                    new_text.append(text[pos:m.start()] + fresh)
                    pos = m.end()
                else:
                    findings.append(Finding(
                        'STALE GENERATED', rel,
                        f"region '{name}' does not match {region.source} -- "
                        f"regenerate (edit the source, not the region)"))
        if write and new_text:
            page.write_text(''.join(new_text) + text[pos:])
            notes.append(f"updated  {rel}")
    for name, region in REGIONS.items():
        where = seen.get(name, [])
        if region.page not in where:
            findings.append(Finding(
                'MISSING REGION', region.page,
                f"no 'generated:{name}' region -- its table is gone, moved, "
                f"or lost its markers, so nothing keeps it current"))
        if len(where) != len(set(where)):
            findings.append(Finding(
                'DUPLICATE REGION', name,
                f"'generated:{name}' appears more than once on one page: "
                f"{sorted(set(p for p in where if where.count(p) > 1))}"))
    return findings, notes
