"""The example nixos plugins: fixture tests for the parts a README
paragraph can't prove. Registers are global, so every test snapshots
CHECKS/REGIONS and restores them -- a plugin's checks must not leak into
the built-in run."""
import pathlib
import unittest

from factcheck import genregions, registry
from factcheck.config import Config

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / 'examples' \
    / 'nixos-plugins'


def load_plugin(name):
    import importlib.util, sys
    sys.path.insert(0, str(EXAMPLES))
    spec = importlib.util.spec_from_file_location(
        'example_' + name, EXAMPLES / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['example_' + name] = mod
    spec.loader.exec_module(mod)
    return mod


class PluginCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.saved_checks = dict(registry.CHECKS)
        self.saved_regions = dict(genregions.REGIONS)
        # Cleanups run LIFO: clear first (registered last), then restore.
        self.addCleanup(lambda: registry.CHECKS.update(self.saved_checks))
        self.addCleanup(registry.CHECKS.clear)
        self.addCleanup(lambda: genregions.REGIONS.update(self.saved_regions))
        self.addCleanup(genregions.REGIONS.clear)

    def cfg(self, data=None):
        return Config(self.root, data or {})

    def write(self, rel, text='x\n'):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p


HOSTS = """\
{ hosts }
nire-alpha = mkHost { }
nire-beta = mkHost { }
"""


class Tree(PluginCase):
    def setUp(self):
        super().setUp()
        self.tree = load_plugin('tree')
        self.write('flake/modules/host-config/hosts.nix', HOSTS)
        self.write('flake/modules/host-config/alpha-configuration.nix',
                   '{\n    includes.nixos = [ "shell" "homelab" ];\n}\n')
        self.write('flake/modules/general-config/shell/bash/m.nix',
                   '{\n    nixos = { };\n}\n')
        self.write('flake/modules/homelab-config/homelab/git/forgejo/f.nix',
                   '{\n    nixos = { };\n}\n')

    def test_roster_and_imports(self):
        categories = self.tree.find_categories(self.root)
        self.assertEqual(sorted(categories), ['git', 'homelab', 'shell'])
        imports = self.tree.host_imports(
            self.root, categories, self.tree.roster(self.root)[0])
        # `homelab` is the umbrella: including it imports `git` beneath it.
        self.assertEqual(imports['alpha'], {'shell', 'homelab', 'git'})
        self.assertEqual(self.tree.roster(self.root)[1], {'alpha', 'beta'})


class Imports(PluginCase):
    def setUp(self):
        super().setUp()
        load_plugin('tree')
        imports_table = load_plugin('imports_table')
        self.check = imports_table.check_imports
        self.write('flake/modules/host-config/hosts.nix', HOSTS)
        self.write('flake/modules/host-config/alpha-configuration.nix',
                   '{\n    includes.nixos = [ "shell" ];\n}\n')
        self.write('flake/modules/host-config/beta-configuration.nix',
                   '{\n    includes.nixos = [ ];\n}\n')
        self.write('flake/modules/general-config/shell/bash/m.nix',
                   '{\n    nixos = { };\n}\n')
        self.write('wiki/config-structure/categories/shell.md',
                   '# Shell\n\n## Imported by\n\nAll two hosts.\n')

    def test_blanket_phrase_covers(self):
        self.assertEqual(self.check(self.root, self.cfg()), [])

    def test_missing_host_named(self):
        self.write('wiki/config-structure/categories/shell.md',
                   '# Shell\n\n## Imported by\n\nOnly `beta` today.\n')
        f = self.check(self.root, self.cfg())
        # Both halves: the importer isn't named, and the named host is a
        # non-importer whose 'Only' phrasing is deliberately not a cue.
        self.assertEqual(sorted(x.tag for x in f), ['MISSING', 'REVIEW'])

    def test_exclusion_cue_passes(self):
        self.write('wiki/config-structure/categories/shell.md',
                   '# Shell\n\n## Imported by\n\nNot `beta`; `alpha` '
                   'imports it.\n')
        self.assertEqual(self.check(self.root, self.cfg()), [])


class Secrets(PluginCase):
    def setUp(self):
        super().setUp()
        secrets = load_plugin('secrets')
        self.check = secrets.check_secrets
        self.write('flake/modules/general-config/system/secrets/.sops.yaml',
                   'keys:\n    alpha: &nire-alpha 01\n'
                   '    beta: &nire-beta 02\n')

    def findings(self, text):
        self.write('wiki/page.md', text)
        return self.check(self.root, self.cfg())

    def test_matching_claim_passes(self):
        self.assertEqual(self.findings(
            'The config `.sops.yaml` enrolls `nire-alpha`, `nire-beta` — '
            'all of them.\n'), [])

    def test_missing_and_extra(self):
        f = self.findings(
            '`.sops.yaml` enrolls `nire-alpha`, `nire-gamma` — done.\n')
        self.assertEqual(sorted(x.tag for x in f), ['EXTRA', 'MISSING'])


class Routes(PluginCase):
    def setUp(self):
        super().setUp()
        routes = load_plugin('routes')
        self.check = routes.check_routes
        self.write('flake/modules/homelab-config/homelab/reverse-proxy/caddy/'
                   'caddy.nix',
                   'handle_path /git/* { }\n'
                   'path /grafana /grafana/* { }\n')

    def test_known_routes_pass(self):
        self.write('wiki/page.md',
                   'At `https://git.moose-micro.ts.net/` or `.../grafana/`.\n')
        self.assertEqual(
            self.check(self.root, self.cfg({'routes': {
                'base-domain': 'git.moose-micro.ts.net',
                'sources': ['flake/modules/homelab-config/homelab/'
                            'reverse-proxy/caddy/caddy.nix']}})), [])

    def test_unknown_route(self):
        self.write('wiki/page.md', 'See `.../gone/`.\n')
        f = self.check(self.root, self.cfg({'routes': {
            'base-domain': 'git.moose-micro.ts.net',
            'sources': ['flake/modules/homelab-config/homelab/reverse-proxy/'
                        'caddy/caddy.nix']}}))
        self.assertEqual([x.tag for x in f], ['UNKNOWN ROUTE'])


class LessonsIndex(PluginCase):
    def setUp(self):
        super().setUp()
        lessons = load_plugin('lessons_index')
        self.check = lessons.check_lessons

    def test_clean_index(self):
        self.write('wiki/agent-lessons-learned.md',
                   '- **§1** [T](agent-lessons-learned/1-t.md) — rule. '
                   'Home: x. Enforced: y.\n')
        self.write('wiki/agent-lessons-learned/1-t.md', '# 1. T\n')
        self.assertEqual(self.check(self.root, self.cfg()), [])

    def test_gaps_and_fields(self):
        self.write('wiki/agent-lessons-learned.md',
                   '- **§2** [T](agent-lessons-learned/2-t.md) — rule. '
                   'Home: x.\n')
        self.write('wiki/agent-lessons-learned/2-t.md', '# 2. T\n')
        f = self.check(self.root, self.cfg())
        self.assertEqual(sorted(x.tag for x in f),
                         ['LESSON FIELD', 'MISSING ARTICLE', 'MISSING LESSON'])


class Regions(PluginCase):
    def setUp(self):
        super().setUp()
        load_plugin('tree')
        load_plugin('nixos_regions')
        self.write('flake/modules/host-config/hosts.nix', HOSTS)
        self.write('flake/modules/host-config/alpha-configuration.nix',
                   '{\n    includes.nixos = [ "impermanence" ];\n}\n')
        self.write('flake/modules/host-config/beta-configuration.nix',
                   '{\n    includes.nixos = [ ];\n}\n')

    def test_host_rows_wipes_column(self):
        rows = dict(genregions.REGIONS['hosts-table'].rows_fn(self.root))
        self.assertEqual(rows['nire-alpha']['Wipes `/root`?'], 'yes')
        self.assertEqual(rows['nire-beta']['Wipes `/root`?'], '**no**')
        self.assertEqual(rows['nire-beta']['Tailnet name'], '`ts-beta`')

    def test_marker_names_the_ancestor_tool(self):
        # Byte-identical regions across the switch: the marker names the
        # tool the docs already name.
        self.assertIn('by `just wiki-gen`',
                      genregions.REGIONS['hosts-table'].marker())


if __name__ == '__main__':
    unittest.main()
