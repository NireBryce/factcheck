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


def justfile_recipes(path):
    """Recipe names plus module names from a justfile."""
    text = COMMENT.sub('', path.read_text())
    return set(JUST_RECIPE.findall(text)) | set(JUST_MOD.findall(text))


@check('recipes', order=30)
def check_recipes(root, cfg):
    """Handles the `just key=value <recipe>` override form by checking the
    token after the override, not the override itself; skips `<template>`
    placeholders, which aren't literal invocations. A justfile configured
    but missing is a finding; no configuration and no justfile is a repo
    that doesn't use just -- nothing to check."""
    rel = cfg.section('recipes').get('justfile')
    jf = root / (rel or '.justfile')
    if not jf.exists():
        if rel:
            return [Finding('MISSING JUSTFILE', rel,
                            f"configured justfile does not exist")]
        return []
    recipes = justfile_recipes(jf)

    findings = []
    for path in cfg.scope('docs'):
        for m in JUST_MENTION.finditer(path.read_text()):
            tokens = m.group(1).split()
            if not tokens or '<' in m.group(1):
                continue
            name = (tokens[1] if '=' in tokens[0] and len(tokens) > 1
                    else tokens[0])
            if name not in recipes:
                findings.append(Finding(
                    'UNKNOWN RECIPE', str(path),
                    f"`just {m.group(1)}` -- '{name}' is not a recipe in "
                    f"{jf.relative_to(root).as_posix()}", see=SEE))
    return findings
