"""counts: the claim shapes against a counter, and the three counter
sources (plugin, config int, config glob) -- plus the rule that config
declarations win over registered plugins, and that an unconfigured repo
gets a vacuous pass."""
from .helpers import Tree

from factcheck.checks import counts

ROSTER = """\
{{ hosts }}
nire-a = mkHost {{ }}
nire-b = mkHost {{ }}
nire-c = mkDarwinHost {{ }}
guest = mkHost {{ }}
"""


class Counts(Tree):
    def setUp(self):
        super().setUp()
        # The counters registry is global; every test starts from empty and
        # loads the roster plugin explicitly (the way a config would).
        self.saved_counters = dict(counts.COUNTERS)
        self.addCleanup(counts.COUNTERS.clear)
        self.addCleanup(counts.COUNTERS.update, self.saved_counters)
        import importlib.util
        import pathlib
        p = (pathlib.Path(__file__).resolve().parent.parent
             / 'examples' / 'nixos-plugins' / 'roster.py')
        spec = importlib.util.spec_from_file_location('roster_test', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.write('flake/modules/host-config/hosts.nix', ROSTER)
        self.write('docs/guide.md', '')

    def findings(self, data=None):
        return counts.check_counts(self.root, self.cfg(data))

    def test_total_claim_clean(self):
        self.write('docs/guide.md', 'All three hosts wipe /root.\n')
        self.assertEqual(self.findings(), [])

    def test_total_claim_stale(self):
        self.write('docs/guide.md', 'All five hosts wipe /root.\n')
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'STALE')
        self.assertIn('says 5', f[0].message)
        self.assertIn('defines 3', f[0].message)
        # The STALE tag renders with the wide separator the ancestor
        # tool's counts findings use -- output format is a contract.
        self.assertTrue(str(f[0]).startswith('STALE    '))

    def test_class_scoped_claim(self):
        self.write('docs/guide.md',
                   'all two NixOS hosts and all one darwin hosts are here.\n')
        self.assertEqual(self.findings(), [])
        self.write('docs/guide.md', 'all three nixos hosts are here.\n')
        self.assertEqual([x.tag for x in self.findings()], ['STALE'])

    def test_of_the_shape(self):
        self.write('docs/guide.md', 'Two of the two NixOS hosts wipe.\n')
        self.assertEqual(self.findings(), [])
        self.write('docs/guide.md', 'Four of the three NixOS hosts wipe.\n')
        self.assertEqual(len(self.findings()), 2)  # exceeds + class mismatch

    def test_historical_prose_does_not_match(self):
        self.write('docs/guide.md',
                   'Three hosts were removed in 2026; the hosts are gone.\n')
        self.assertEqual(self.findings(), [])

    def test_static_counter_from_config(self):
        # Config declarations win over the registered roster.
        self.write('docs/guide.md', 'all four hosts are up.\n')
        self.assertEqual(
            self.findings({'counts': {'counters': {'total': 4}}}), [])

    def test_glob_counter_from_config(self):
        self.write('units/a.md', '')
        self.write('units/b.md', '')
        self.write('docs/guide.md', 'all two units are documented.\n')
        self.assertEqual(
            self.findings({'counts': {'noun': 'units', 'classes': [],
                                      'counters': {'total':
                                                   {'glob': 'units/*.md'}}}}),
            [])

    def test_unconfigured_repo_is_vacuous(self):
        counts.COUNTERS.clear()
        self.write('docs/guide.md', 'all three hosts are up.\n')
        self.assertEqual(self.findings(), [])

    def test_partially_configured_counters_are_a_finding(self):
        counts.COUNTERS.clear()
        self.write('docs/guide.md', 'all three nixos hosts are up.\n')
        f = self.findings({'counts': {'counters': {'total': 3}}})
        self.assertEqual([x.tag for x in f], ['NO COUNTER'])
        self.assertIn('nixos', f[0].message)


if __name__ == '__main__':
    unittest.main()
