"""lessons-index: entries, articles, numbering gaps and required fields,
on fixture pages; plus a parity case run against the real index of the
repo the check was generalized from, when that checkout is present."""
import os
import pathlib
import unittest

from .helpers import Tree

from factcheck.checks import lessons

CFG = {'lessons': {'page': 'docs/lessons.md'}}
# Two entries verbatim from the source repo's index (its §1 and §2 shapes),
# so the entry pattern is tested against real input, not only against
# the fixture author's model of it.
REAL_1 = ('- **§1** [A tool that reports success has not been tested]'
          '(lessons/1-success-is-not-tested.md) — test a checker against '
          'a case it should catch, in the same commit; prefer shapes that '
          'cannot lose evidence. Home: AGENTS.md "Before calling it done"; '
          'skill `agent-scripts`. Enforced: none (reminded by the '
          'lesson-reminder hook on creating a script).')
REAL_2 = ('- **§2** [When a tool contradicts you, suspect yourself first]'
          '(lessons/2-suspect-yourself-first.md) — check your own '
          'assumption (which commit, which shell semantics) before calling '
          'a tool broken. Home: AGENTS.md "Before calling it done". '
          'Enforced: none.')


class LessonsIndex(Tree):
    def setUp(self):
        super().setUp()
        self.write('docs/lessons/1-success-is-not-tested.md',
                   '# 1. A tool that reports success has not been tested\n')
        self.write('docs/lessons/2-suspect-yourself-first.md',
                   '# 2. When a tool contradicts you, suspect yourself first\n')

    def tags(self, page, data=CFG):
        self.write('docs/lessons.md', page)
        return sorted(f.tag for f in
                      lessons.check_lessons_index(self.root, self.cfg(data)))

    def test_real_entries_are_clean(self):
        self.assertEqual(self.tags(f'# Lessons\n\n{REAL_1}\n{REAL_2}\n'), [])

    def test_unconfigured_is_vacuous(self):
        self.write('docs/lessons.md', 'anything\n')
        self.assertEqual(lessons.check_lessons_index(self.root, self.cfg()),
                         [])

    def test_configured_page_missing(self):
        self.assertEqual(
            [f.tag for f in lessons.check_lessons_index(
                self.root, self.cfg({'lessons': {'page': 'nope.md'}}))],
            ['MISSING LESSONS PAGE'])

    def test_gap_missing_field_and_article(self):
        page = f'{REAL_1}\n' + REAL_2.replace(' Enforced: none.', '') + \
            '\n- **§4** [T](lessons/4-t.md) — r. Home: x. Enforced: y.\n'
        self.assertEqual(self.tags(page), [
            'LESSON FIELD', 'MISSING ARTICLE', 'MISSING ARTICLE',
            'MISSING LESSON'])

    def test_wrong_link_duplicate_and_malformed(self):
        page = (f'{REAL_1}\n{REAL_2}\n'
                + REAL_2.replace('2-suspect', '1-success') + '\n'
                + '- **§9 no brackets\n')
        self.assertEqual(self.tags(page), [
            'DUPLICATE LESSON', 'LESSON LINK', 'MALFORMED LESSON'])

    def test_article_name_and_title(self):
        self.write('docs/lessons/Notes.md', 'x\n')
        self.write('docs/lessons/2-suspect-yourself-first.md', '# Two\n')
        self.write('docs/lessons/0-human-README.md', '# about\n')
        self.assertEqual(self.tags(f'{REAL_1}\n{REAL_2}\n'), [
            'LESSON ARTICLE NAME', 'LESSON ARTICLE TITLE'])

    def test_double_dash_separator_and_custom_fields(self):
        page = '- **#1** [T](lessons/1-success-is-not-tested.md) -- r. Why: x.\n'
        data = {'lessons': {'page': 'docs/lessons.md', 'marker': '#',
                            'fields': ['Why']}}
        self.write('docs/lessons/2-suspect-yourself-first.md', '# 2. x\n')
        self.assertEqual(self.tags(page, data), ['MISSING LESSON'])


class LessonsLayouts(Tree):
    """Where the page and the article directory sit relative to each other,
    and the branches the first suite left unexercised."""

    def run_check(self, data):
        return sorted(f.tag for f in
                      lessons.check_lessons_index(self.root, self.cfg(data)))

    def entry(self, link, n=1):
        return f'- **§{n}** [T]({link}) — r. Home: x. Enforced: y.\n'

    def test_article_dir_outside_the_page_dir(self):
        self.write('wiki/arts/1-a.md', '# 1. A\n')
        data = {'lessons': {'page': 'docs/l.md', 'dir': 'wiki/arts'}}
        self.write('docs/l.md', self.entry('../wiki/arts/1-a.md'))
        self.assertEqual(self.run_check(data), [])
        # Resolves to docs/wiki/arts/1-a.md, which is not the article.
        self.write('docs/l.md', self.entry('wiki/arts/1-a.md'))
        self.assertEqual(self.run_check(data), ['LESSON LINK'])

    def test_root_level_page_and_sibling_prefixed_dir(self):
        self.write('L/1-a.md', '# 1. A\n')
        self.write('L.md', self.entry('./L/1-a.md'))
        self.assertEqual(self.run_check({'lessons': {'page': 'L.md'}}), [])
        self.write('wikifoo/x/1-a.md', '# 1. A\n')
        self.write('wiki/l.md', self.entry('../wikifoo/x/1-a.md'))
        self.assertEqual(self.run_check(
            {'lessons': {'page': 'wiki/l.md', 'dir': 'wikifoo/x/'}}), [])

    def test_duplicate_article_and_configured_exempt(self):
        self.write('docs/l/1-a.md', '# 1. A\n')
        self.write('docs/l/1-b.md', '# 1. B\n')
        self.write('docs/l/NOTES.md', 'x\n')
        self.write('docs/l.md', self.entry('l/1-a.md'))
        data = {'lessons': {'page': 'docs/l.md', 'exempt': ['NOTES.md']}}
        self.assertEqual(self.run_check(data), ['DUPLICATE ARTICLE'])

    def test_page_inside_its_own_article_dir_is_not_an_article(self):
        self.write('docs/1-a.md', '# 1. A\n')
        self.write('docs/l.md', self.entry('1-a.md'))
        self.assertEqual(self.run_check(
            {'lessons': {'page': 'docs/l.md', 'dir': 'docs'}}), [])

    def test_field_name_must_be_whole(self):
        self.write('docs/l/1-a.md', '# 1. A\n')
        self.write('docs/l.md', '- **§1** [T](l/1-a.md) — r. NotHome: x. '
                   'Enforced: y.\n')
        self.assertEqual(self.run_check({'lessons': {'page': 'docs/l.md'}}),
                         ['LESSON FIELD'])


SOURCE = pathlib.Path(os.environ.get(
    'FACTCHECK_LESSONS_PARITY_REPO', '/nonexistent'))


@unittest.skipUnless((SOURCE / 'wiki/agent-lessons-learned.md').is_file(),
                     'set FACTCHECK_LESSONS_PARITY_REPO to a nixos-configs '
                     'checkout to run the parity case')
class Parity(unittest.TestCase):
    """The real index the check was generalized from: clean today."""

    def test_source_index_is_clean(self):
        from factcheck.config import Config
        cfg = Config(SOURCE, {'lessons': {
            'page': 'wiki/agent-lessons-learned.md',
            'dir': 'wiki/agent-lessons-learned'}})
        self.assertEqual(lessons.check_lessons_index(SOURCE, cfg), [])


if __name__ == '__main__':
    unittest.main()
