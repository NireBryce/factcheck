"""Doc-rot stress suite: seeded mutations against a small corpus that
exercises every core check's trigger shape.

This is the stdlib-only stand-in for property testing (#22): no
hypothesis, so determinism comes from `random.Random(seed)` and the
property is stated as a loop -- for every mutation operator and every
seed, exactly one rot is applied to a corpus that was clean, and
`factcheck check` must catch it with the expected finding tag. Cosmetic
noise (seeded filler sentences) rides along with each mutation so no
trigger is pinned to one byte position. The corpus stays clean under
noise alone.

What tests cannot do here is prove fitness for a real repo's prose; the
parity runs against the consumer checkout are that instrument. Every
tag these operators expect was read off the checks themselves, not
assumed.
"""
import io
import random
import subprocess
import unittest

from .helpers import Tree

from factcheck import checks  # noqa: F401  (registers every check)
from factcheck import cli, genregions

PAST_DATE = '2026-01-01'

REGION_BODY = 'A generated line that must stay current.\n'
# The region's place in the page is hand-authored -- genregions rewrites
# inside the markers, it does not insert them.
REGION_TEXT = (
    '<!-- generated:stress-block -- from the stress corpus, by factcheck; '
    'change the source, not this table -->\n\n'
    + REGION_BODY + '\n\n<!-- /generated -->\n')

PAGE = f"""# The Corpus Page

_Last modified: {PAST_DATE}_

## Contents

- [One](#one)
- [Two](#two)

## One

All three hosts run on impermanence, as of the last roster read.
Run `just build` first, and the `deploy` skill explains the rest.
See [the other page](other.md).

## Two

Impermanence for everyone.
"""

OTHER = f"""# Other

_Last modified: {PAST_DATE}_

## Contents

- [Half](#half)

## Half

A short page needs no sibling and no more prose than this.

{REGION_TEXT}
"""

LESSONS_PAGE = """- **§1** [First](lessons/1-first.md) — the first rule. Home: AGENTS.md. Enforced: hook.
"""

# Cosmetic filler: sentences no check has a claim about.
NOISE = [
    'A plain sentence with no claims at all.',
    'Prose continues below this line, unchanged in meaning.',
    'This paragraph exists to move every later line down.',
]

CORPUS = {
    '.justfile': 'build:\n\techo building\n',
    '.agents/skills/deploy/.gitkeep': '',
    'wiki/page.md': PAGE,
    'wiki/other.md': OTHER,
    'docs/lessons.md': LESSONS_PAGE,
    'docs/lessons/1-first.md': '# 1. First\n',
}

CFG = {
    'scopes': {'docs': ['wiki/page.md', 'docs/lessons.md'],
               'pages': ['wiki/page.md', 'wiki/other.md']},
    'skills': {'dirs': ['.agents/skills']},
    'lessons': {'page': 'docs/lessons.md'},
    'counts': {'counters': {'total': 3, 'nixos': 2, 'darwin': 1}},
    'pins': [{'id': 'two-body', 'file': 'wiki/page.md', 'heading': 'Two',
              'contains': 'Impermanence for everyone.'}],
}



def git_init(root):
    """The corpus as a checkout: the git-reading checks skip (loudly,
    exit 2) without one. tests/__init__ has stripped any inherited
    hook's GIT_* env, so this lands in the temp repo only."""
    for args in (('git', 'init', '-q', str(root)),
                 ('git', '-C', str(root), 'config', 'user.email',
                  'stress@test'),
                 ('git', '-C', str(root), 'config', 'user.name', 'stress'),
                 ('git', '-C', str(root), 'add', '-A'),
                 ('git', '-C', str(root), 'commit', '-qm', 'corpus')):
        subprocess.run(args, check=True, capture_output=True)


def write_corpus(root, files, seed):
    """`files` (rel -> text, None to omit) plus `seed`'s noise, then the
    generated region rendered by factcheck itself (byte-exact markers),
    then git."""
    rng = random.Random(seed)
    noise = rng.sample(NOISE, rng.randint(1, len(NOISE)))
    page = files.get('wiki/page.md')
    if page is not None:
        files['wiki/page.md'] = page.replace(
            '## Two\n', '## Two\n\n' + '\n'.join(noise) + '\n', 1)
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    genregions.run(root, [root / 'wiki/other.md'], write=True)


def run_check(root, cfg_data):
    from factcheck.config import Config
    buf = io.StringIO()
    code = cli._run_checks('check', root, Config(root, cfg_data), set(), buf)
    return code, buf.getvalue()


# Every operator: one rot, and the tag that must catch it. Tags were
# read off each check's findings, not assumed.
OPS = {
    'recipe_renamed': (
        lambda files: files.update(
            {'.justfile': 'build2:\n\techo building\n'}), 'UNKNOWN RECIPE'),
    'link_target_gone': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'].replace(
                '(other.md)', '(other2.md)')}), 'BROKEN LINK'),
    'anchor_gone': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'] + 'See [this](#nope).\n'}),
        'BROKEN ANCHOR'),
    'heading_renamed': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'].replace(
                '## Two', '## Two Renamed', 1)}), 'STALE CONTENTS'),
    'contents_entry_dropped': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'].replace(
                '- [Two](#two)\n', '')}), 'STALE CONTENTS'),
    'date_removed': (
        lambda files: files.update(
            {'wiki/page.md': '\n'.join(
                l for l in files['wiki/page.md'].splitlines()
                if 'Last modified' not in l) + '\n'}),
        'MISSING LAST-MODIFIED'),
    'date_in_the_future': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'].replace(
                PAST_DATE, '2099-01-01')}), 'FUTURE DATE'),
    'conflict_markers_left': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'] +
                '<<<<<<< head\n=======\n>>>>>>> branch\n'}),
        'CONFLICT MARKER'),
    'lesson_article_deleted': (
        lambda files: files.update({'docs/lessons/1-first.md': None}),
        'BROKEN LINK'),
    'lesson_numbering_gap': (
        lambda files: files.update(
            {'docs/lessons.md': files['docs/lessons.md'] +
                '- **§3** [Third](lessons/3-third.md) — the third rule. '
                'Home: AGENTS.md. Enforced: hook.\n'}),
        'BROKEN LINK'),
    'skill_renamed': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'].replace(
                '`deploy` skill', '`deploy2` skill')}), 'UNKNOWN SKILL'),
    'count_claim_drifted': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'].replace(
                'All three hosts', 'All four hosts')}), 'STALE'),
    'bare_count_claim': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'] +
                'Six skills live in .agents/skills.\n'}), 'BARE COUNT'),
    'pinned_prose_drifted': (
        lambda files: files.update(
            {'wiki/page.md': files['wiki/page.md'].replace(
                'Impermanence for everyone.', 'Impermanence for some.')}),
        'DRIFTED PIN'),
    # generated_region_edited is applied post-render in corpus(): the
    # mutator below runs before factcheck writes the region.
    'generated_region_edited': (
        lambda files: None, 'STALE GENERATED'),
}


class Stress(Tree):
    def corpus(self, op_name, seed):
        """The corpus with `seed`'s noise, plus operator `op_name`'s rot
        (None: noise alone), in a root wiped clean of every earlier
        subTest's files."""
        import shutil
        shutil.rmtree(self.root)
        self.root.mkdir()
        genregions.register(genregions.Block(
            name='stress-block', page='wiki/other.md',
            source='the stress corpus', body_fn=lambda _: REGION_BODY))
        try:
            files = dict(CORPUS)
            if op_name is not None:
                OPS[op_name][0](files)
            for rel in [r for r, t in files.items() if t is None]:
                del files[rel]
            write_corpus(self.root, files, seed)
            if op_name == 'generated_region_edited':
                # The rot lands after the region exists: the mutator
                # cannot edit what factcheck has not yet rendered.
                other = self.root / 'wiki/other.md'
                other.write_text(other.read_text().replace(
                    REGION_BODY.rstrip(),
                    'A generated line someone hand-edited.'))
            git_init(self.root)
            return run_check(self.root, CFG)
        finally:
            genregions.REGIONS.pop('stress-block', None)

    def test_noise_alone_stays_clean(self):
        for seed in (1, 2, 3):
            with self.subTest(seed=seed):
                code, out = self.corpus(None, seed)
                self.assertEqual(code, 0, out)

    def test_every_mutation_is_caught(self):
        for op_name, (_, tag) in OPS.items():
            for seed in (1, 2, 3):
                with self.subTest(op=op_name, seed=seed):
                    code, out = self.corpus(op_name, seed)
                    self.assertEqual(code, 1, out)
                    self.assertIn(tag, out)


if __name__ == '__main__':
    unittest.main()
