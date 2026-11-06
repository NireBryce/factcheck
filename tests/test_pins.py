"""pins: the selectors (line, start/end, heading+level), the ambiguity
and drift findings, the malformed-table cases, and the pin-gen / pin-show
tools. Fixture texts are shaped like real prose pages -- a heading with
body lines and a following sibling -- because a selector keyed on a shape
no consumer has tests nothing."""
import io

from .helpers import Tree

from factcheck import cli
from factcheck.checks import pins as pins_check
from factcheck.pins import PinError, parse, resolve, span_text

PAGE = """# Page

## Target

alpha body line

## Next

tail line
"""


class Engine(Tree):
    def setUp(self):
        super().setUp()
        self.write('docs/p.md', PAGE)

    def resolve(self, pin):
        return resolve(self.root, pin)

    def test_line_selector(self):
        lo, hi, _ = self.resolve({'file': 'docs/p.md', 'line': 5})
        self.assertEqual((lo, hi), (5, 5))

    def test_line_past_eof_does_not_resolve(self):
        with self.assertRaises(PinError) as ctx:
            self.resolve({'file': 'docs/p.md', 'line': 99})
        self.assertEqual(ctx.exception.tag, 'UNRESOLVED PIN')

    def test_start_end_spans_inclusive(self):
        lo, hi, _ = self.resolve(
            {'file': 'docs/p.md', 'start': '## Target', 'end': '## Next'})
        self.assertEqual((lo, hi), (3, 7))

    def test_start_without_end_is_one_line(self):
        lo, hi, _ = self.resolve({'file': 'docs/p.md', 'start': 'alpha'})
        self.assertEqual((lo, hi), (5, 5))

    def test_start_matching_nothing_and_matching_twice(self):
        with self.assertRaises(PinError) as no:
            self.resolve({'file': 'docs/p.md', 'start': 'zzz'})
        self.assertEqual(no.exception.tag, 'UNRESOLVED PIN')
        self.write('docs/two.md', 'dup\nmid\ndup\n')
        with self.assertRaises(PinError) as amb:
            self.resolve({'file': 'docs/two.md', 'start': 'dup'})
        self.assertEqual(amb.exception.tag, 'AMBIGUOUS PIN')

    def test_end_matched_only_after_start(self):
        # The same text sits before the start line, too: an end search
        # that included it would resolve backwards.
        self.write('docs/after.md', 'zz y\n## A\nzz y\n')
        lo, hi, _ = self.resolve(
            {'file': 'docs/after.md', 'start': '## A', 'end': 'zz y'})
        self.assertEqual((lo, hi), (2, 3))

    def test_heading_resolves_to_next_same_level(self):
        lo, hi, _ = self.resolve({'file': 'docs/p.md', 'heading': 'Target'})
        self.assertEqual((lo, hi), (3, 6))

    def test_subheading_stays_inside_the_span(self):
        self.write('docs/sub.md',
                   '# P\n\n## A\n\n### A1\n\nx\n\n## B\n\n')
        lo, hi, _ = self.resolve({'file': 'docs/sub.md', 'heading': 'A'})
        self.assertEqual((lo, hi), (3, 8))

    def test_heading_in_a_fence_is_not_a_heading(self):
        self.write('docs/f.md',
                   '# P\n\n```sh\n# Target\n```\n\n## Target\n\nbody\n')
        lo, hi, _ = self.resolve({'file': 'docs/f.md', 'heading': 'Target'})
        self.assertEqual((lo, hi), (7, 9))

    def test_duplicate_heading_needs_level(self):
        self.write('docs/twice.md', '# A\n\nx\n\n## A\n\n## B\n')
        with self.assertRaises(PinError) as amb:
            self.resolve({'file': 'docs/twice.md', 'heading': 'A'})
        self.assertEqual(amb.exception.tag, 'AMBIGUOUS PIN')
        # The name alone is ambiguous; the level picks one. The level-1
        # section runs to EOF -- only a heading at level <= 1 ends it.
        lo, hi, _ = self.resolve(
            {'file': 'docs/twice.md', 'heading': 'A', 'level': 1})
        self.assertEqual((lo, hi), (1, 7))
        lo, hi, _ = self.resolve(
            {'file': 'docs/twice.md', 'heading': 'A', 'level': 2})
        self.assertEqual((lo, hi), (5, 6))

    def test_missing_file_is_its_own_tag(self):
        with self.assertRaises(PinError) as ctx:
            self.resolve({'file': 'docs/none.md', 'line': 1})
        self.assertEqual(ctx.exception.tag, 'UNKNOWN PIN FILE')

    def test_parse_rejects_malformed_pins(self):
        cases = [
            {'file': 'p.md'},                        # no id
            {'id': 'x'},                             # no file
            {'id': 'x', 'file': 'p.md'},             # no selector
            {'id': 'x', 'file': 'p.md', 'line': 1,
             'heading': 'A'},                        # two selectors
            {'id': 'x', 'file': 'p.md', 'end': 'y'},  # end without start
            {'id': 'x', 'file': 'p.md', 'heading': 'A', 'level': 9},
            {'id': 'x', 'file': 'p.md', 'line': 1, 'nope': 1},
            'not a table',
        ]
        for pin in cases:
            with self.assertRaises(PinError) as ctx:
                parse([pin])
            self.assertEqual(ctx.exception.tag, 'BAD PIN', pin)

    def test_parse_rejects_duplicate_ids(self):
        with self.assertRaises(PinError) as ctx:
            parse([{'id': 'x', 'file': 'p.md', 'line': 1},
                   {'id': 'x', 'file': 'q.md', 'line': 1}])
        self.assertEqual(ctx.exception.tag, 'BAD PIN')

    def test_span_text_joins_the_region(self):
        _, _, lines = self.resolve({'file': 'docs/p.md', 'heading': 'Target'})
        self.assertIn('alpha body line', span_text(lines, 3, 6))


class Check(Tree):
    def setUp(self):
        super().setUp()
        self.write('docs/p.md', PAGE)

    def run_check(self, pins):
        return pins_check.check_pins(
            self.root, self.cfg({'pins': pins}))

    def test_vacuous_without_pins(self):
        self.assertEqual(pins_check.check_pins(self.root, self.cfg()), [])

    def test_resolved_pin_is_clean(self):
        self.assertEqual(self.run_check([
            {'id': 't', 'file': 'docs/p.md', 'heading': 'Target',
             'contains': 'alpha'}]), [])

    def test_drifted_contains_is_a_hard_finding(self):
        f = self.run_check([
            {'id': 't', 'file': 'docs/p.md', 'heading': 'Target',
             'contains': 'long gone'}])
        self.assertEqual([x.tag for x in f], ['DRIFTED PIN'])
        self.assertFalse(f[0].review)

    def test_unresolved_ambiguous_and_unknown_file(self):
        self.assertEqual([x.tag for x in self.run_check([
            {'id': 'a', 'file': 'docs/p.md', 'heading': 'Nope'},
            {'id': 'b', 'file': 'docs/p.md', 'line': 999},
            {'id': 'c', 'file': 'docs/none.md', 'line': 1},
        ])], ['UNRESOLVED PIN', 'UNRESOLVED PIN', 'UNKNOWN PIN FILE'])

    def test_bad_table_names_the_config_file(self):
        f = pins_check.check_pins(
            self.root, self.cfg({'pins': [{'id': 'x'}]}))
        self.assertEqual([x.tag for x in f], ['BAD PIN'])
        # A dict-config has no source file; the fallback label is
        # 'config'. A file-backed config names itself.
        self.assertEqual(f[0].path, 'config')


class Tools(Tree):
    def setUp(self):
        super().setUp()
        self.write('docs/p.md', PAGE)

    def run_cli(self, *argv):
        # Not `run` -- that name is TestCase's own machinery.
        out = io.StringIO()
        code = cli.main(['--root', str(self.root), *argv], out=out)
        return code, out.getvalue()

    def test_pin_gen_prints_toml(self):
        code, out = self.run_cli('pin-gen', 'docs/p.md', '--id', 't',
                             '--heading', 'Target', '--level', '2')
        self.assertEqual(code, 0)
        self.assertIn('[[pins]]', out)
        self.assertIn('heading = "Target"', out)
        # auto-contains trips on the body, not the guarded heading line
        self.assertIn('contains = "alpha body line"', out)

    def test_pin_gen_write_appends_to_the_config(self):
        code, out = self.run_cli('pin-gen', 'docs/p.md', '--id', 't',
                             '--start', 'alpha', '--write')
        self.assertEqual(code, 0)
        self.assertIn('wrote', out)
        cfg_file = self.root / '.agents/factcheck'
        self.assertIn('id = "t"', cfg_file.read_text())

    def test_pin_gen_refuses_an_unresolvable_pin(self):
        code, out = self.run_cli('pin-gen', 'docs/p.md', '--id', 't',
                             '--heading', 'Nope')
        self.assertEqual(code, 2)
        self.assertIn('unresolvable', out)

    def test_pin_gen_refuses_absolute_files(self):
        code, out = self.run_cli('pin-gen', str(self.root / 'docs/p.md'),
                             '--id', 't', '--line', '1')
        self.assertEqual(code, 2)
        self.assertIn('repo-relative', out)

    def test_pin_show_reports_resolution_and_exit_code(self):
        self.write('.agents/factcheck',
                   '[[pins]]\nid = "ok"\nfile = "docs/p.md"\n'
                   'heading = "Target"\n'
                   '[[pins]]\nid = "gone"\nfile = "docs/p.md"\n'
                   'heading = "Nope"\n')
        code, out = self.run_cli('pin-show')
        self.assertEqual(code, 1)
        self.assertIn('ok docs/p.md:3-6', out)
        self.assertIn('gone', out)
        code, out = self.run_cli('pin-show', 'ok')
        self.assertEqual(code, 0)
        self.assertIn('ok docs/p.md:3-6', out)
        code, out = self.run_cli('pin-show', 'zz')
        self.assertEqual(code, 2)

    def test_pin_show_is_vacuous_without_pins(self):
        code, out = self.run_cli('pin-show')
        self.assertEqual(code, 0)
        self.assertIn('no pins configured', out)


if __name__ == '__main__':
    unittest.main()
