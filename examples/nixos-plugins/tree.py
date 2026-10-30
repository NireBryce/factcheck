"""Static reading of a dirs-as-categories flake tree: the modules,
categories and hosts as the files say them, for checks and generated
regions. Read from the files rather than evaluated, so it runs without
nix and on fixture trees.

This is a plugin (not core) because the tree conventions it reads are
the source repo's house style: module files as `{ nixos = ...; }`
attribute sets with four-space top-level keys, `includes.<class> = [...]`
host import lists, `mkHost`/`mkDarwinHost` roster lines. None of that is
secret -- it is just one repo's shape, and another repo's plugin would
read a different shape.

Config (`[tree]`), with the source repo's values as defaults:

    [tree]
    modules = "flake/modules"
    areas = ["general-config", "hardware-config", "homelab-config",
             "users-config"]          # the areas the wiki indexes
    hosts-file = "flake/modules/host-config/hosts.nix"
    host-config-dir = "flake/modules/host-config"
    name-prefix = "nire-"              # stripped for short names; "" keeps full
    host-constructors = { nixos = "mkHost", darwin = "mkDarwinHost" }
"""
import pathlib
import re

CLASS_KEYS = ('nixos', 'homeManager', 'darwin')
COMMENT = re.compile(r'#[^\n]*')
# A key of a module file's top-level attribute set: the house style puts
# those at exactly four spaces, with `nixos =`, `homeManager.foo =` or
# `includes.nixos =`.
TOP_KEY = re.compile(r'(?m)^ {4}(\w+)(?:\.(\w+))?[\w.]*\s*=')
FLAG = re.compile(r'\bfolderIsCategory\s*=\s*(true|false)\s*;')
# `includes.<class> = [ "a" "b" ];` -- how a host or the home aggregate
# names what it includes.
INCLUDES = re.compile(r'includes\.(\w+)\s*=\s*\[(.*?)\]', re.S)
ENABLES = re.compile(r'enables\.(\w+)\s*=\s*\[(.*?)\]', re.S)

_CATEGORIES = {}


def cfg(root, section='tree'):
    from factcheck.config import Config
    return Config(root).section(section)


def _settings(root):
    s = cfg(root)
    return {
        'modules': s.get('modules', 'flake/modules'),
        'areas': tuple(s.get('areas', ['general-config', 'hardware-config',
                                       'homelab-config', 'users-config'])),
        'hosts_file': s.get('hosts-file',
                            'flake/modules/host-config/hosts.nix'),
        'host_dir': s.get('host-config-dir', 'flake/modules/host-config'),
        'prefix': s.get('name-prefix', 'nire-'),
        'ctors': s.get('host-constructors',
                       {'nixos': 'mkHost', 'darwin': 'mkDarwinHost'}),
    }


def _visible(path, base):
    """Not under a `_`-prefixed path component -- import-tree skips those."""
    return '/_' not in '/' + str(path)[len(str(base)) + 1:]


def module_classes(path, text=None):
    """The classes a module file declares -- its top-level class keys, and
    any class it has `includes` for -- or an empty set for a file that is
    not a module file (defaults.nix, a flake-parts module)."""
    if path.name == 'defaults.nix':
        return set()
    classes = set()
    for key, sub in TOP_KEY.findall(
            COMMENT.sub('', path.read_text()) if text is None else text):
        if key in CLASS_KEYS:
            classes.add(key)
        elif key == 'includes' and sub in CLASS_KEYS:
            classes.add(sub)
    return classes


def all_categories(root):
    """category name -> directory, for every category under the modules
    dir: a folder below the top level with a subfolder holding a module
    file, or one whose files set folderIsCategory (`false` opts out).

    Cached, keyed on every file's path, mtime and size, so a fixture tree
    a test edits between calls is read afresh."""
    st = _settings(root)
    modules = root / st['modules']
    files = [p for p in modules.rglob('*.nix') if _visible(p, modules)]
    key = (str(pathlib.Path(root).resolve()),
           tuple((str(p), s.st_mtime_ns, s.st_size)
                 for p in files for s in [p.stat()]))
    if key not in _CATEGORIES:
        _CATEGORIES.clear()
        _CATEGORIES[key] = _read_categories(modules, files)
    return dict(_CATEGORIES[key])


def _read_categories(modules, files):
    # Paths as strings relative to modules/: pathlib's ancestor checks
    # were most of the runtime.
    base = len(str(modules)) + 1
    texts = {p: COMMENT.sub('', p.read_text()) for p in files}
    rel = {p: str(p)[base:] for p in files}
    module_dirs = {rel[p].rpartition('/')[0]
                   for p in files if module_classes(p, texts[p])}
    flags_in, folders = {}, set()
    for p in files:
        d = rel[p].rpartition('/')[0]
        flags_in.setdefault(d, set()).update(FLAG.findall(texts[p]))
        while d:
            folders.add(d)
            d = d.rpartition('/')[0]
    cats = {}
    for d in sorted(folders):
        if '/' not in d:
            continue                                   # an area
        flags = flags_in.get(d, set())
        if flags == {'true'} or (flags != {'false'}
                                 and any(m.startswith(d + '/')
                                         for m in module_dirs)):
            cats[d.rpartition('/')[2]] = modules / d
    return cats


def find_categories(root):
    """category name -> directory, for the categories in the configured
    areas -- the ones the docs index (everything else is deliberately
    excluded there, so the checks have nothing to compare against and
    don't look)."""
    st = _settings(root)
    modules = root / st['modules']
    return {n: d for n, d in all_categories(root).items()
            if d.relative_to(modules).parts[0] in st['areas']}


def actual_hosts(root):
    """host name (with its prefix) -> class, read straight from the hosts
    file. The one roster: checks and generated regions both derive from
    it, so a host added there appears in both with no edit here."""
    st = _settings(root)
    ctors = st['ctors']
    rx = re.compile(
        r'^\s*(' + re.escape(st['prefix']) + r'[\w-]+)\s*=\s*('
        + '|'.join(re.escape(c) for c in ctors.values()) + r')\b', re.M)
    text = COMMENT.sub('', (root / st['hosts_file']).read_text())
    by_ctor = {v: k for k, v in ctors.items()}
    return {name: by_ctor[ctor]
            for name, ctor in rx.findall(text)}


def category_classes(category_dir):
    """The classes declared by any module file under this category's own
    directory tree. A nested category's files live physically under the
    umbrella's tree too, so this walks straight through a nested category
    rather than stopping at it: what a Class(es) column claims is "what
    including this name actually wires in"."""
    classes = set()
    for p in category_dir.rglob('*.nix'):
        if _visible(p, category_dir):
            classes |= module_classes(p)
    return classes


def categories_under(root, d):
    """The categories nested anywhere under category directory `d`."""
    prefix = str(d) + '/'
    return [c for c in all_categories(root).values()
            if str(c).startswith(prefix)]


def nested_category_names(root, categories, name):
    """`name` plus every category nested (at any depth) under its own
    directory. Including a category includes everything beneath it, so
    for "does this host import category X" a host that includes the
    umbrella counts as importing X even though X never appears literally
    in the host's own `includes`."""
    if name not in categories:
        return {name}
    d = categories[name]
    return {name} | {c.name for c in categories_under(root, d)}


def roster(root):
    """(short names in roster order, the nixos-class ones as a set). A
    short name is the prefixed name without its prefix, which is how the
    per-host files and the docs' Imported by columns write it."""
    st = _settings(root)
    hosts = actual_hosts(root)
    short = lambda name: name.removeprefix(st['prefix']) if st['prefix'] \
        else name
    return ([short(n) for n in hosts],
            {short(n) for n, cls in hosts.items() if cls == 'nixos'})


def host_imports(root, categories, hosts):
    """host short-name -> set of category names it effectively imports --
    the names in its own `includes`, expanded through any umbrella
    category among them."""
    st = _settings(root)
    out = {}
    for host in hosts:
        p = root / st['host_dir'] / f'{host}-configuration.nix'
        if not p.exists():
            print(f"WARN  expected host file missing: {p}")
            continue
        text = COMMENT.sub('', p.read_text())
        literal = set()
        for _, names in INCLUDES.findall(text):
            literal.update(re.findall(r'"([\w-]+)"', names))
        effective = set()
        for n in literal:
            effective |= nested_category_names(root, categories, n)
        out[host] = effective
    return out


def static_document(root):
    """A module-graph-style document (categories, modules with their
    classes, includes and enables) as far as the files say it -- for
    drawing without nix."""
    st = _settings(root)
    modules = root / st['modules']
    rel = lambda p: p.relative_to(modules).as_posix()
    doc = {'version': 1, 'classes': list(CLASS_KEYS), 'folders': [],
           'categories': {n: {'dir': rel(d), 'members': [], 'nested': [],
                              'flag': None}
                          for n, d in all_categories(root).items()},
           'modules': {}, 'includes': {}, 'enables': {}}
    for p in sorted(modules.rglob('*.nix')):
        if not _visible(p, modules):
            continue
        classes = module_classes(p)
        if not classes:
            continue
        name = p.parent.name if p.name == 'default.nix' else p.stem
        doc['modules'][name] = {
            'path': rel(p), 'classes': [c for c in CLASS_KEYS if c in classes]}
        text = COMMENT.sub('', p.read_text())
        for kind, pattern in (('includes', INCLUDES), ('enables', ENABLES)):
            for cls, names in pattern.findall(text):
                doc[kind].setdefault(name, {})[cls] = \
                    re.findall(r'"([\w-]+)"', names)
    return doc
