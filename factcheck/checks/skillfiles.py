"""skill-files: the skill files themselves, turned inward.

Skill prose is re-read even less than the docs (loaded on trigger,
written once) and rots the same way, so the wiki-side lookups apply to
it: `just <recipe>` mentions (backticked anywhere, bare inside fenced
code -- a raw-text scan would drown in prose like "just say what you're
doing"), skill mentions, relative links, and repo-rooted backtick paths
(prefix-scoped: bare names are prose shorthand). Plus the things only a
SKILL.md has: frontmatter `name` matching its directory, a one-sentence
description with no repo paths, the optional `when_to_use` under the
harness's listing cap, plain-YAML-safe values, the `**Needs:**` tag
line, and a ban on dynamic-injection syntax (```! blocks and inline
!`commands` run at skill load, with no prompt)."""
import re

from ..findings import Finding
from ..mdcore import fences
from ..registry import check
from .recipes import justfile_recipes
from .skills import SKILL_MENTION

FRONTMATTER_NAME = re.compile(r'^name: (.+)$', re.M)
FRONTMATTER_DESC = re.compile(r'^description: (.+)$', re.M)
# A description or when_to_use may not carry a repo path; this matches the
# shapes that read as one -- a repo top-level prefix or a leading ./ ../ --
# without firing on topic shorthand or a mount point.
DESC_PATH_PREFIXES = ('wiki', 'flake', '.agents', '.github', 'scripts')


def _desc_path(prefixes):
    return re.compile(
        r'(?:\.{1,2}/|(?:' + '|'.join(re.escape(p) for p in prefixes)
        + r')/[\w./-]+)')
DESC_SENTENCE_END = re.compile(r'[.!?](?:\s|$)')
FRONTMATTER_WHEN = re.compile(r'^when_to_use:(.*)$', re.M)
FRONTMATTER_KEY = re.compile(r'^([^\s:#][^:]*):', re.M)
# `!` then a backtick, at line start or after whitespace: inline injection.
INJECTION = re.compile(r'(?:^|\s)!`')
# A plain (unquoted) YAML scalar can't open with an indicator character or
# contain ': ' / ' #' -- the hand-rolled regexes read such a line fine
# while the harness's YAML parser rejects or truncates it.
YAML_PLAIN_BAD_START = tuple('"\'[]{}>|*&!%@`,?#-')
YAML_PLAIN_BAD_INNER = (': ', ' #')
NEEDS_LINE = re.compile(r'^\*\*Needs:\*\*[ \t]*(.*)$', re.M)
BARE_JUST = re.compile(r'\bjust ([a-z][\w-]*)')

DEFAULTS = {
    'frontmatter-keys': ['name', 'description', 'when_to_use'],
    'desc-max-words': 30,       # REVIEW only: names the outliers
    'when-max-words': 40,       # REVIEW only: "short trigger phrases"
    'listing-cap': 1536,        # the harness's description+when_to_use cap
    'rooted-prefixes': list(DESC_PATH_PREFIXES),
    'needs-tags': ['bash-guards'],
    'needs-cue': (r'\bsops (?:-[deirs]\b|--(?:decrypt|encrypt|extract|'
                  r'rotate|in-place)\b|decrypt|updatekeys|edit)|'
                  r'/run/secrets|reset --hard|\bnix eval\b'),
    'needs-cue-tag': 'bash-guards',
}


def _just_mentions_in_skill(text):
    """`just <recipe>` mentions in a skill file: backticked anywhere, bare
    inside fenced code blocks. Prose ("just say what you're doing") sits
    outside both, which is what keeps this free of the false positives a
    raw-text scan drowns in."""
    found = [m.group(1) for m in re.compile(r'`just ([^`]+)`').finditer(text)]
    for _, line, kind in fences.scan_lines(text):
        if kind == fences.BODY:
            found.extend(m.group(1) for m in BARE_JUST.finditer(line))
    return found


def _check_needs(rel, text, tags_allowed, cue_rx, cue_tag):
    """The `**Needs:**` tag line: placed between the H1 and the first
    `## ` heading, every value in the configured vocabulary, and present
    whenever the body runs a command the configured cue covers -- so one
    tag, defined once, replaces a "this assumes X" sentence in each
    skill. Tag lines count only as prose: an example inside a fence is
    documentation, not the skill's own tag."""
    findings = []
    body = text.split('---', 2)[2] if text.startswith('---') else text
    seen_h2 = False
    tags = set()
    for _n, line, kind in fences.scan_lines(body):
        if kind != fences.TEXT:
            continue
        if line.startswith('## '):
            seen_h2 = True
        m = NEEDS_LINE.match(line)
        if not m:
            continue
        if seen_h2:
            findings.append(Finding(
                'NEEDS PLACEMENT', str(rel),
                "the **Needs:** line belongs between the H1 and the first "
                "'## ' heading"))
            continue
        for tag in (t.strip() for t in m.group(1).split(',')):
            if tag not in tags_allowed:
                findings.append(Finding(
                    'UNKNOWN TAG', str(rel),
                    f"**Needs:** '{tag}' -- not one of {sorted(tags_allowed)}; "
                    f"extend the vocabulary deliberately"))
            tags.add(tag)
    if cue_tag not in tags:
        cue = cue_rx.search(body) if cue_rx else None
        if cue:
            findings.append(Finding(
                'MISSING TAG', str(rel),
                f"mentions '{cue.group(0)}', which the guards tied to "
                f"'{cue_tag}' cover -- add `**Needs:** {cue_tag}` under "
                f"the H1"))
    return findings


def _check_injection(rel, text):
    findings = []
    for n, line, kind in fences.scan_lines(text):
        if kind == fences.OPENER:
            if line.lstrip().startswith("```!"):
                findings.append(Finding(
                    'INJECTION', f"{rel}:{n}",
                    "a ```! block runs at skill load, with no prompt -- "
                    "spell the command in ## Applies to instead"))
            continue
        if kind == fences.TEXT and INJECTION.search(line):
            findings.append(Finding(
                'INJECTION', f"{rel}:{n}",
                "an inline !`command` runs at skill load, with no prompt; "
                "in prose, don't put ! directly before a backtick"))
    return findings


def _check_frontmatter_extras(rel, head, desc, st):
    """Unknown keys, YAML plain-scalar safety, and the optional
    `when_to_use` -- short trigger phrases the harness appends to the
    description in its skill listing."""
    findings = []
    keys = set(st['frontmatter-keys'])
    cap = st['listing-cap']
    desc_path = _desc_path(st['rooted-prefixes'])
    for m in FRONTMATTER_KEY.finditer(head):
        key = m.group(1).strip()
        if key not in keys:
            findings.append(Finding(
                'UNKNOWN KEY', str(rel),
                f"frontmatter key '{key}' -- not one of {sorted(keys)}; a "
                f"misspelt key is silently ignored, so extend the key set "
                f"deliberately"))
    for line in head.splitlines():
        if line[:1].isspace() and line.strip():
            findings.append(Finding(
                'FRONTMATTER SHAPE', str(rel),
                f"indented/continuation line '{line.strip()[:40]}' -- every "
                f"value stays on one line"))
    values = [('description', desc)]
    when_m = FRONTMATTER_WHEN.search(head)
    when = when_m.group(1).strip() if when_m else None
    if when is not None:
        values.append(('when_to_use', when))
        if not when:
            findings.append(Finding(
                'WHEN_TO_USE SHAPE', str(rel),
                "when_to_use is empty or a block scalar"))
        if desc_path.search(when):
            findings.append(Finding(
                'WHEN_TO_USE SHAPE', str(rel),
                "when_to_use contains a repo path"))
        total = len(desc) + len(when)
        if total > cap:
            findings.append(Finding(
                'WHEN_TO_USE SHAPE', str(rel),
                f"description + when_to_use is {total} chars, over the "
                f"{cap}-char listing cap -- the tail is truncated"))
        if len(when.split()) > st['when-max-words']:
            findings.append(Finding(
                'REVIEW', str(rel),
                f"when_to_use is {len(when.split())} words (over "
                f"{st['when-max-words']}) -- trigger detail that belongs in "
                f"## Applies to", review=True))
    for key, value in values:
        if value and (value.startswith(YAML_PLAIN_BAD_START)
                      or any(x in value for x in YAML_PLAIN_BAD_INNER)):
            findings.append(Finding(
                'FRONTMATTER SHAPE', str(rel),
                f"{key} is not a plain YAML scalar (leading indicator "
                f"character, ': ', or ' #') -- the harness's YAML parse "
                f"fails or truncates it; reword"))
    return findings


@check('skill-files', order=50)
def check_skill_files(root, cfg):
    s = cfg.section('skill-files')
    st = {**DEFAULTS, **s}
    st['needs-tags'] = set(st['needs-tags'])
    cue_rx = re.compile(st['needs-cue']) if st['needs-cue'] else None
    desc_path = _desc_path(st['rooted-prefixes'])
    rooted = re.compile(
        r'`((?:' + '|'.join(re.escape(p) for p in st['rooted-prefixes'])
        + r')/[\w./-]+)`')

    skills_dirs = cfg.section('skills').get('dirs', ['.agents/skills'])
    skills_dir = root / skills_dirs[0]
    if not skills_dir.exists():
        return []
    jf = root / (cfg.section('recipes').get('justfile') or '.justfile')
    recipes = justfile_recipes(jf) if jf.exists() else set()
    real = {p.name for p in skills_dir.iterdir() if p.is_dir()}

    findings = []
    for path in sorted(skills_dir.rglob('*.md')):
        rel = path.relative_to(root)
        text = path.read_text()

        # Relative links (a narrower shape than links': no percent-decoding
        # yet no fragment checking -- the file half only).
        for m in re.compile(r'\]\(([^)\s]+)\)').finditer(text):
            target = m.group(1).split('#', 1)[0]
            if (not target or '<' in target or '*' in target
                    or target.startswith(('http://', 'https://', 'mailto:'))):
                continue
            if not (path.parent / target).resolve().exists():
                findings.append(Finding(
                    'MISSING LINK', str(rel),
                    f"({m.group(1)}) resolves to nothing"))

        seen = set()
        for mention in _just_mentions_in_skill(text):
            if mention in seen:
                continue
            seen.add(mention)
            tokens = mention.split()
            if not tokens or '<' in mention:
                continue
            name = (tokens[1] if '=' in tokens[0] and len(tokens) > 1
                    else tokens[0])
            if name not in recipes:
                findings.append(Finding(
                    'UNKNOWN RECIPE', str(rel),
                    f"`just {mention}` -- '{name}' is not a recipe in "
                    f"{jf.relative_to(root).as_posix()}"))

        for m in rooted.finditer(text):
            candidate = m.group(1).rstrip('/')
            if '<' in candidate or '*' in candidate:
                continue
            if not (root / candidate).exists():
                findings.append(Finding(
                    'MISSING PATH', str(rel),
                    f"`{candidate}` does not exist at the repo root"))

        for m in SKILL_MENTION.finditer(text):
            name = m.group(1) or m.group(2)
            if name not in real:
                findings.append(Finding(
                    'UNKNOWN SKILL', str(rel),
                    f"'{name}' has no {skills_dirs[0]}/{name}/ directory"))

        if path.name != 'SKILL.md':
            continue
        if not text.startswith('---'):
            findings.append(Finding(
                'NO FRONTMATTER', str(rel),
                "SKILL.md must open with a --- name/description block"))
            continue
        head = text.split('---', 2)[1]
        name_m = FRONTMATTER_NAME.search(head)
        desc_m = FRONTMATTER_DESC.search(head)
        if not name_m:
            findings.append(Finding(
                'NO NAME', str(rel), "frontmatter has no name:"))
            continue
        if name_m.group(1).strip() != path.parent.name:
            findings.append(Finding(
                'NAME MISMATCH', str(rel),
                f"frontmatter name '{name_m.group(1).strip()}' != directory "
                f"'{path.parent.name}'"))
        if not desc_m:
            findings.append(Finding(
                'NO DESCRIPTION', str(rel), "frontmatter has no description:"))
            continue
        desc = desc_m.group(1).strip()
        if desc_path.search(desc):
            findings.append(Finding(
                'DESCRIPTION SHAPE', str(rel),
                "description contains a repo path"))
        if '(' in desc:
            findings.append(Finding(
                'DESCRIPTION SHAPE', str(rel),
                "parenthetical in description"))
        if len(DESC_SENTENCE_END.findall(desc)) > 1:
            findings.append(Finding(
                'DESCRIPTION SHAPE', str(rel),
                "description is more than one sentence"))
        if len(desc.split()) > st['desc-max-words']:
            findings.append(Finding(
                'REVIEW', str(rel),
                f"description is {len(desc.split())} words (over "
                f"{st['desc-max-words']}) -- scope detail that belongs in "
                f"## Applies to", review=True))
        findings += _check_frontmatter_extras(rel, head, desc, st)
        findings += _check_injection(rel, text)
        findings += _check_needs(rel, text, st['needs-tags'], cue_rx,
                                 st['needs-cue-tag'])
    return findings
