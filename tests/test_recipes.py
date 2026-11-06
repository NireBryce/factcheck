"""recipes: mention-vs-justfile, the override form, templates, and the
configured-but-missing justfile case."""
from .helpers import Tree

from factcheck.checks import recipes

JUSTFILE = """\
# the recipe list
build:
    echo building

push target: build
    echo pushing

mod agent 'scripts/agent.just'
"""


class Recipes(Tree):
    def setUp(self):
        super().setUp()
        self.write('.justfile', JUSTFILE)
        self.write('docs/guide.md', '')

    def findings(self, data=None):
        return recipes.check_recipes(self.root, self.cfg(data))

    def test_clean(self):
        self.write('docs/guide.md', 'run `just build` or `just agent x`.\n')
        self.assertEqual(self.findings(), [])

    def test_unknown_recipe(self):
        self.write('docs/guide.md', 'run `just buidl`.\n')
        f = self.findings()
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0].tag, 'UNKNOWN RECIPE')
        self.assertIn("'buidl'", f[0].message)

    def test_mod_name_counts_as_a_recipe(self):
        self.write('docs/guide.md', 'run `just agent`.\n')
        self.assertEqual(self.findings(), [])

    def test_override_form_checks_the_recipe_not_the_key(self):
        self.write('docs/guide.md', 'run `just host=x build`.\n')
        self.assertEqual(self.findings(), [])

    def test_template_placeholder_skipped(self):
        self.write('docs/guide.md', 'run `just host=<name> <recipe>`.\n')
        self.assertEqual(self.findings(), [])

    def test_recipe_with_quoted_default_is_found(self):
        self.write('.justfile', JUSTFILE + "publish dir='.':\n    true\n")
        self.write('docs/guide.md', 'run `just publish`.\n')
        self.assertEqual(self.findings(), [])

    def test_no_justfile_no_config_passes(self):
        (self.root / '.justfile').unlink()
        self.write('docs/guide.md', 'no just here\n')
        self.assertEqual(self.findings(), [])

    def test_configured_but_missing_justfile_is_a_finding(self):
        (self.root / '.justfile').unlink()
        f = self.findings({'recipes': {'justfile': '.justfile'}})
        self.assertEqual([x.tag for x in f], ['MISSING JUSTFILE'])

    def test_unqualified_default_justfile_is_found(self):
        # `justfile` is just's own first-choice default name; a repo using
        # it with nothing configured used to get no check at all.
        self.root.joinpath('.justfile').unlink()
        self.write('justfile', JUSTFILE)
        self.write('docs/guide.md', 'run `just build` or `just gone`.\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['UNKNOWN RECIPE'])
        self.assertIn("'gone'", f[0].message)

    def test_default_name_matches_case_insensitively(self):
        # just matches directory entries with eq_ignore_ascii_case
        # (src/search.rs, just 1.58.0), so `Justfile` is a justfile.
        self.root.joinpath('.justfile').unlink()
        self.write('Justfile', JUSTFILE)
        self.write('docs/guide.md', 'run `just build`.\n')
        self.assertEqual(self.findings(), [])

    def test_flags_in_a_mention_are_not_recipes(self):
        # `just --list`, `just -n build`: a leading flag is not the recipe
        # being run, and `just --list` names no recipe at all.
        self.write('docs/guide.md',
                   'run `just --list`, `just -n build`, `just build`.\n')
        self.assertEqual(self.findings(), [])

    def test_unknown_recipe_still_found_behind_flags(self):
        self.write('docs/guide.md', 'run `just -n gone`.\n')
        f = self.findings()
        self.assertEqual([x.tag for x in f], ['UNKNOWN RECIPE'])
        self.assertIn("'gone'", f[0].message)

    def test_value_taking_flags_step_over_their_value(self):
        # From `just --help` (1.58.0): -f/--justfile and -d/--working-
        # directory take one value, --set takes two.
        self.write('docs/guide.md',
                   'run `just --justfile other.just build`, '
                   '`just -d sub build`, `just --set host h build`.\n')
        self.assertEqual(self.findings(), [])

    def test_command_and_evaluate_name_no_recipe(self):
        # --command runs an arbitrary command and --evaluate prints
        # variables; what follows them is not a recipe.
        self.write('docs/guide.md',
                   'run `just -c bash -c \'ls\'` and `just --evaluate host`.\n')
        self.assertEqual(self.findings(), [])

    def test_justfile_location_is_configurable(self):
        self.write('tools/Justfile', 'deploy:\n    true\n')
        self.write('docs/guide.md', 'run `just deploy`.\n')
        self.assertEqual(
            self.findings({'recipes': {'justfile': 'tools/Justfile'}}), [])


if __name__ == '__main__':
    unittest.main()
