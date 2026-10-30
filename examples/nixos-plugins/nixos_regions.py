"""The fleet's generated regions: the host table, the categories index
tables, the module-counts table, and the module-tree diagram.

These are the actual tables the docs carry, so this file is the most
repo-shaped plugin in the examples -- it reads the tree plugin and the
docs' page layout, and every fleet fact in its OUTPUT comes from the
configured sources at runtime, not from anything in this file. It exists
to show what "moving the regions at flip time" looks like: copy, wire the
config, and the rendered regions are byte-identical to the tool they
replace (the regions pass `tool_name` so even the marker note is
unchanged).

The module-layout diagram needs `nix run` against the flake -- declared
as a Region capability, so machines without nix skip that one region with
a stated REVIEW finding while everything else still checks.

Config (`[regions]`, all with these defaults):

    [regions]
    flake = "flake"                # the flake the module-graph app runs from
    class-order = ["nixos", "homeManager", "darwin"]
    homelab = "homelab-config/homelab"
    nested-named-max = 3
    pages-dir = "wiki/config-structure/categories"
    tailnet-template = "ts-{short}"
    wipes-import = "impermanence"  # hosts importing this wipe /root
    wipes-darwin-label = "n/a"

    [[regions.module-counts]]
    label = "total `.nix` files under `flake/modules/`"
    # no grep: the files themselves are counted

    [[regions.module-counts]]
    label = "`with pkgs;` package lists"
    grep = "with pkgs;"
"""
import re

from factcheck import genregions
from factcheck.genregions import Block, GenError, Region

import tree

CLASS_ORDER = ['nixos', 'homeManager', 'darwin']


def _settings(root):
    # The regions read both sections: the tree's layout plus their own.
    s = {**tree._settings(root), **tree.cfg(root, 'regions')}
    return {
        'flake': s.get('flake', 'flake'),
        'class_order': s.get('class-order', CLASS_ORDER),
        'homelab': s.get('homelab', 'homelab-config/homelab'),
        'nested_max': int(s.get('nested-named-max', 3)),
        'pages': s.get('pages-dir', 'wiki/config-structure/categories'),
        'tailnet': s.get('tailnet-template', 'ts-{short}'),
        'wipes_import': s.get('wipes-import', 'impermanence'),
        'wipes_darwin': s.get('wipes-darwin-label', 'n/a'),
        'counts': s.get('module-counts', DEFAULT_COUNT_ROWS),
        'prefix': s.get('name-prefix', 'nire-'),
        'modules': s.get('modules', 'flake/modules'),
        'host_dir': s.get('host-config-dir', 'flake/modules/host-config'),
    }


DEFAULT_COUNT_ROWS = [
    {'label': 'total `.nix` files under `flake/modules/`'},
    {'label': 'header comment (`# This is a dirs-as-categories module…`)',
     'grep': '# This is a dirs-as-categories module file, which means'},
    {'label': '`# summary:` / `# package summary:` comment',
     'regex': r'(?m)^\s*# (?:package )?summary:'},
    {'label': '`with pkgs;` package lists', 'grep': 'with pkgs;'},
]

WIKI_GEN = '`just wiki-gen`'


def host_rows(root):
    """The roster in file order. 'Wipes /root?' is whether the host's
    effective import list holds the configured module; darwin has no
    initrd stage this convention touches, hence n/a. A NixOS host that
    does not wipe is bold: it is the exception the docs warn about."""
    cfg = tree.cfg(root)
    st = _settings(root)
    categories = tree.find_categories(root)
    hosts = tree.actual_hosts(root)
    if not hosts:
        raise GenError('hosts file declares no hosts (or moved)')
    shorts = [n.removeprefix(st['prefix']) if st['prefix'] else n
              for n in hosts]
    for s in shorts:
        p = (root / st['host_dir'] / f'{s}-configuration.nix')
        if not p.exists():
            raise GenError(f'no {p.relative_to(root)} for a roster host')
    imports = tree.host_imports(root, categories, shorts)
    for name, cls in hosts.items():
        short = name.removeprefix(st['prefix']) if st['prefix'] else name
        if cls == 'darwin':
            wipes = st['wipes_darwin']
        elif st['wipes_import'] in imports[short]:
            wipes = 'yes'
        else:
            wipes = '**no**'
        yield name, {'Host': f'`{name}`', 'Class': cls,
                     'Wipes `/root`?': wipes,
                     'Tailnet name': '`' + st['tailnet'].format(short=short)
                                     + '`'}


def category_rows(homelab):
    """Index rows for every category with a docs page: the homelab
    umbrella and its nested categories when `homelab`, everything else
    otherwise. Ordered by area then name."""
    def rows(root):
        st = _settings(root)
        modules = root / st['modules']
        pages = root / st['pages']
        found = []
        for name, d in tree.find_categories(root).items():
            rel = d.relative_to(modules).as_posix()
            if (rel == st['homelab']
                    or rel.startswith(st['homelab'] + '/')) != homelab:
                continue
            if (pages / f'{name}.md').exists():
                link = f'{name}.md'
            elif (pages / name / '00-INDEX.md').exists():
                link = f'{name}/00-INDEX.md'
            else:
                continue  # no page, no row
            nested = sorted(c.name for c in tree.categories_under(root, d))
            dir_cell = f'`{rel}/`'
            if 0 < len(nested) <= st['nested_max']:
                dir_cell += ' (+ nested ' + ', '.join(f'`{n}`'
                                                      for n in nested) + ')'
            elif nested:
                dir_cell += f' (+ {len(nested)} nested)'
            classes = tree.category_classes(d)
            ordered = ([c for c in st['class_order'] if c in classes]
                       + sorted(classes - set(st['class_order'])))
            found.append(((rel.split('/')[0], name), name, {
                'Category': f'[{name}]({link})', 'Directory': dir_cell,
                'Class(es)': ', '.join(ordered)}))
        for _, name, cells in sorted(found, key=lambda t: t[0]):
            yield name, cells
    return rows


def count_rows(root):
    """One row per convention the style guide once stated as an inline
    count. The pattern is what the page's 'recompute by hand' grep uses;
    no pattern counts the files themselves."""
    st = _settings(root)
    files = sorted((root / st['modules']).rglob('*.nix'))
    if not files:
        raise GenError(f'no .nix files under {st["modules"]}/')
    texts = [f.read_text() for f in files]
    for row in st['counts']:
        label, grep, regex = row.get('label'), row.get('grep'), row.get('regex')
        if grep is None and regex is None:
            n = len(files)
        elif regex:
            n = sum(1 for t in texts if re.search(regex, t))
        else:
            n = sum(1 for t in texts if grep in t)
        yield label, {'What': label, 'Files': str(n)}


def module_layout(root):
    """Mermaid of the top of the module tree -- areas and their direct
    categories -- drawn by the flake's own module-graph app, fed the
    static reading of `root`. Never evaluates `root`: this runs on
    fixture trees, so the app comes from the configured flake instead."""
    import json
    import subprocess
    st = _settings(root)
    modules = root / st['modules']
    if not modules.is_dir():
        raise GenError(f'no {st["modules"]}/ directory')
    doc = tree.static_document(root)
    if not doc['categories']:
        raise GenError(f'no categories under {st["modules"]}/')
    flake = (root / st['flake']).resolve()
    try:
        r = subprocess.run(
            ['nix', 'run', f'{flake}#module-graph', '--',
             'tree', '-', '--depth', '1', '--categories-only'],
            input=json.dumps(doc), capture_output=True, text=True)
    except FileNotFoundError:
        raise GenError('nix is not installed; the diagram needs the '
                       'module-graph app')
    if r.returncode:
        lines = r.stderr.strip().splitlines()
        raise GenError(
            f'module-graph failed: {lines[-1] if lines else r.returncode}')
    return '```mermaid\n' + r.stdout.rstrip('\n') + '\n```'


def register():
    """Registers the regions. Called at import. The `source` strings are
    verbatim from the tool that wrote the current regions -- the marker
    line is part of the rendered region, so byte-parity across the switch
    needs these exact."""
    tree.cfg  # noqa: B018  (fail fast on import errors, not mid-check)
    genregions.register(Region(
        'hosts-table', 'wiki/fleet/hosts.md',
        "flake/modules/host-config/hosts.nix and each host's import list",
        ['Host', 'Class', 'Role', 'Wipes `/root`?', 'Tailnet name'],
        'Host', ['Role'], host_rows, tool_name=WIKI_GEN))
    for name, homelab, source in (
            ('categories-index-system', False,
             'the categories under flake/modules/ and the pages in '
             'wiki/config-structure/categories/'),
            ('categories-index-homelab', True,
             'the categories under flake/modules/homelab-config/homelab/ '
             'and the pages in wiki/config-structure/categories/')):
        genregions.register(Region(
            name, 'wiki/config-structure/categories/00-INDEX.md', source,
            ['Category', 'Directory', 'Class(es)', 'Imported by'],
            'Category', ['Imported by'], category_rows(homelab),
            tool_name=WIKI_GEN))
    genregions.register(Region(
        'module-counts',
        'wiki/config-structure/module-style-guide-for-agents.md',
        'a count of the .nix files under flake/modules/',
        ['What', 'Files'], 'What', [], count_rows, tool_name=WIKI_GEN))
    genregions.register(Block(
        'module-layout', 'wiki/config-structure/architecture.md',
        'the categories under flake/modules/, drawn by the '
        'flake-module-graph input',
        module_layout, needs=('nix',), tool_name=WIKI_GEN))


register()
