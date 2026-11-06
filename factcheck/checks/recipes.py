"""recipes: every backtick `just <recipe...>` mention in the docs scope
against the justfile's own recipe names -- a rename or removal silently
breaks every doc that told someone to run the old name, and nothing about
`just` itself would complain until someone actually tried it."""
import re

from ..findings import Finding
from ..registry import check

COMMENT = re.compile(r'#[^\n]*')
# A recipe header, e.g. `build:` or `foo dir='.' *args:` -- name, then zero
# or more space-separated parameter/default tokens (which may quote
# defaults), then a bare `:`. `(?!=)` excludes a `name := value` variable
# assignment, just's *other* use of a leading identifier. Without the
# quote/dot in the token class, `dir='.'` made the whole recipe invisible
# to this regex.
JUST_RECIPE = re.compile(r'^([a-zA-Z][\w-]*)(?:\s+[\w=*."\'-]+)*:(?!=)', re.M)
# A just module declaration, e.g. `mod agent 'scripts/agent.just'`
# (optionally `mod?`). `just agent <recipe>` dispatches through it, so the
# module name counts as a recipe for mention-checking.
JUST_MOD = re.compile(r'^mod\??\s+([a-zA-Z][\w-]*)', re.M)
# A backtick-quoted invocation, e.g. `just build` or `just host=x build`.
JUST_MENTION = re.compile(r'`just ([^`]+)`')

SEE = "a rename left a reference behind: fix the doc or restore the recipe"

# The default names just itself searches for, in its own search order --
# read from just 1.58.0's src/search.rs (`JUSTFILE_NAMES`), where each
# directory entry is matched with `eq_ignore_ascii_case`, so `Justfile`
# and friends are found too. `justfile` is just's own first choice, so a
# repo using it without configuration must not read as one that doesn't
# use just. Where just errors on two candidates in one directory
# (MultipleCandidates), this picks the first name's match; a doc checker
# need not refuse to run over the ambiguity.
JUSTFILE_NAMES = ('justfile', '.justfile')


def find_justfile(root):
    """The justfile just would use in `root` with nothing configured, or
    None -- the first of `justfile`/`.justfile` (ASCII-case-insensitive)
    that exists there."""
    for name in JUSTFILE_NAMES:
        for entry in sorted(root.iterdir()):
            if entry.is_file() and entry.name.lower() == name:
                return entry
    return None


def justfile_recipes(path):
    """Recipe names plus module names from a justfile."""
    text = COMMENT.sub('', path.read_text())
    return set(JUST_RECIPE.findall(text)) | set(JUST_MOD.findall(text))


# just's command line, read from `just --help` (just 1.58.0), split by
# what a doc mention of it can hide a recipe behind. VALUE_FLAGS take one
# separate value and TWO_VALUE_FLAGS two (--set VARIABLE VALUE), so the
# value is stepped over with its flag instead of being read as a recipe;
# NO_RECIPE_FLAGS name no recipe at all (--command runs an arbitrary
# command, --evaluate prints variables), so the whole mention is skipped.
# Any other token starting with `-` (--list, -n, --version, ...) is a
# valueless flag stepped over on its own; --flag=value forms carry their
# value attached, and a `key=value` override is a token with `=` in it.
# Short flags written combined (-nv) are skipped wholesale, so one
# embedding a value-taking short (-nf FILE) would leave the value to be
# checked as the recipe.
VALUE_FLAGS = {
    '--alias-style', '--ceiling', '--chooser', '--color', '--command-color',
    '--completions', '--cygpath', '--dotenv-command', '--dump-format',
    '--evaluate-format', '--group', '--indentation', '--jobs', '--justfile',
    '--justfile-name', '--list-heading', '--list-prefix', '--shell',
    '--shell-arg', '--tempdir', '--timestamp-format', '--working-directory',
    '-F', '-E', '-f', '-d',
}
TWO_VALUE_FLAGS = {'--set'}
NO_RECIPE_FLAGS = {'-c', '--command', '--evaluate'}


def mention_recipe(mention):
    """The token of a `just ...` mention that names the recipe being run,
    or None when the mention names none: step over `key=value` overrides
    and over flags -- a value-taking flag's value goes with it -- and the
    first remaining token is the recipe. A mention made only of flags
    (`just --list`) names no recipe."""
    tokens = mention.split()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in NO_RECIPE_FLAGS:
            return None
        if '=' in tok:
            i += 1
        elif tok in TWO_VALUE_FLAGS:
            i += 3
        elif tok in VALUE_FLAGS:
            i += 2
        elif tok.startswith('-'):
            i += 1
        else:
            return tok
    return None


@check('recipes', order=30)
def check_recipes(root, cfg):
    """Checks the recipe-naming token of every backtick `just ...` mention
    (see mention_recipe for the forms it steps over); skips `<template>`
    placeholders, which aren't literal invocations. A justfile configured
    but missing is a finding; no configuration and no justfile is a repo
    that doesn't use just -- nothing to check."""
    rel = cfg.section('recipes').get('justfile')
    jf = root / rel if rel else find_justfile(root)
    if jf is None or not jf.exists():
        if rel:
            return [Finding('MISSING JUSTFILE', rel,
                            f"configured justfile does not exist")]
        return []
    recipes = justfile_recipes(jf)

    findings = []
    for path in cfg.scope('docs'):
        for m in JUST_MENTION.finditer(path.read_text()):
            if '<' in m.group(1):
                continue
            name = mention_recipe(m.group(1))
            if name is not None and name not in recipes:
                findings.append(Finding(
                    'UNKNOWN RECIPE', str(path),
                    f"`just {m.group(1)}` -- '{name}' is not a recipe in "
                    f"{jf.relative_to(root).as_posix()}", see=SEE))
    return findings
