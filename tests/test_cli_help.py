"""Per-command help and the ancestor's command names (issue 9)."""
import io
import unittest

from factcheck import cli


def run(*argv):
    out = io.StringIO()
    return cli.main(list(argv), out=out), out.getvalue()


class Help(unittest.TestCase):
    def test_old_gen_contents_names_its_replacement(self):
        for argv in (['gen-contents'], ['gen-contents', 'wiki/page.md']):
            rc, out = run(*argv)
            self.assertEqual(rc, 2)
            self.assertIn('fix-contents <page.md...>', out)
            self.assertNotIn('unexpected argument', out)

    def test_fixer_help_is_its_own_usage_and_summary(self):
        rc, out = run('fix-contents', '--help')
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith('usage: factcheck fix-contents <file.md>'))
        self.assertIn('Contents block', out)
        rc, out = run('fix-refs', '-h')
        self.assertTrue(out.startswith('usage: factcheck fix-refs apply|dry-run'))
        self.assertIn('fix-refs: rewrite references', out)

    def test_check_help_uses_the_module_introduction(self):
        rc, out = run('links', '--help')
        self.assertEqual(rc, 0)
        self.assertIn('links [repo-root]', out)
        self.assertIn('links: every relative markdown link', out)

    def test_flag_position_does_not_matter(self):
        self.assertEqual(run('--help', 'links'), run('links', '--help'))

    def test_bare_help_and_unknown_command(self):
        rc, out = run('--help')
        self.assertEqual(rc, 0)
        self.assertIn('<command> --help', out)
        self.assertEqual(run('nope', '--help')[0], 2)


if __name__ == '__main__':
    unittest.main()
