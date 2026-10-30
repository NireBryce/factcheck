"""docrefs: four cross-reference shapes the narrower checks miss, plus the
bare-count rule.

- `just <module> <helper>` where the helper names no recipe in that just
  module (recipes only looks up the first word).
- a `<skills-dir>/<name>` path, or an unquoted hyphenated "skill
  some-name", naming no skill directory. Hyphenated only: a plain "skill
  set" is prose.
- a backticked path under a directory that moved (a data table -- adding
  a future move is one config line).
- a sentence naming exactly one markdown page AND a quoted "…section"
  where that page has no such heading (normalized substring,
  case-insensitive; an ambiguous page reference is skipped, never
  flagged).
- BARE COUNT: a number (from three up -- "two" is the pair idiom, not a
  tally that rots) directly before a countable noun, unless the sentence
  names that many items itself, ends in a colon, carries a date or "as
  of", or opts out with `<!-- count-ok: reason -->`. Quoted examples and
  `code` spans are mentions, not claims; fenced code and generated
  regions are never scanned."""
import re

from ..findings import Finding
from ..mdcore import fences
from ..mdcore.headings import iter_headings
from ..registry import check
from .recipes import COMMENT, JUST_MENTION, JUST_RECIPE

SEE = ("a reference the repo stopped agreeing with: fix the doc or find "
       "where the thing went")

# "skill wiki-sync" with no backticks. Hyphenated names only: a plain
# "skill set" is prose.
SKILL_PLAIN = re.compile(r'\b[Ss]kills? ([a-z]+(?:-[a-z]+)+)\b')
QUOTED_SECTION = re.compile(
    r'["\u201c]([^"\u201c\u201d\n]{3,80})["\u201d]\s+(?:section|heading)\b'
    r'|\b(?:section|heading)\s+["\u201c]([^"\u201c\u201d\n]{3,80})["\u201d]')
MD_REF = re.compile(r'`([\w./-]+\.md)`|\]\(([\w./-]+\.md)(?:#[^)]*)?\)')
SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z])|\n\s*\n')

# Number words a bare-count claim can use. "two"/"2" is deliberately
# absent from the matchable set (it is the pair idiom); three up.
COUNT_WORDS = ('two three four five six seven eight nine ten eleven twelve '
               'thirteen fourteen fifteen sixteen seventeen eighteen '
               'nineteen twenty').split()
BARE_COUNT = re.compile(
    r'(?<!\bof )\b(?P<n>[3-9]|[1-9]\d+|' + '|'.join(COUNT_WORDS[1:]) + r')'
    r'(?:\s+[A-Za-z][\w-]*)?\s+'
    r'(?:files|modules|subdirectories|hosts|recipes|skills)\b', re.I)
COUNT_OK = re.compile(r'<!--\s*count-ok:[^>]*-->')
DATED = re.compile(r'\d{4}-\d{2}-\d{2}|\bas of\b|\bat the time\b', re.I)
NAMED = re.compile(r'`[^`\n]+`|\]\([^)]+\)')
# The generated-region convention: a region's contents are generated, so
# its numbers are claims the region machinery owns, not prose to flag.
GEN_REGION = re.compile(
    r'(?ms)^<!-- generated:[\w-]+\b[^\n]*?-->[ \t]*\n.*?'
    r'^<!-- /generated -->[ \t]*$')
QUOTED = re.compile(r'"[^"\n]*"|\u201c[^\u201d\n]*\u201d|`[^`\n]*`')


def _count_value(tok):
    tok = tok.lower()
    return int(tok) if tok.isdigit() else COUNT_WORDS.index(tok) + 2


def bare_counts(text, nouns=None):
    """Yield (count_token, sentence) for each unaccompanied bare count."""
    if nouns:
        rx = re.compile(
            r'(?<!\bof )\b(?P<n>[3-9]|[1-9]\d+|' + '|'.join(COUNT_WORDS[1:])
            + r')(?:\s+[A-Za-z][\w-]*)?\s+(?:' + '|'.join(map(re.escape, nouns))
            + r')\b', re.I)
    else:
        rx = BARE_COUNT
    text = fences.blank_fences(GEN_REGION.sub('', text))
    for para in re.split(r'\n\s*\n', text):
        if COUNT_OK.search(para):
            continue
        for item in re.split(r'\n(?=\s*(?:[-*]|\d+\.)\s)', para):
            for sent in re.split(r'(?<=[.!?])\s+(?=[A-Z])', item):
                sent = ' '.join(sent.split())
                # Quoted examples ("all four files") and `code` spans are
                # mentions, not claims; "N of M modules" is a measurement.
                m = rx.search(QUOTED.sub(' ', sent))
                if not m or DATED.search(sent) or sent.endswith(':'):
                    continue
                if len(NAMED.findall(sent)) >= _count_value(m.group('n')):
                    continue
                yield m.group('n'), sent


def _norm_heading(text):
    return re.sub(r'[^a-z0-9 ]+', '', text.lower().replace('`', '')).split()


def _resolve_md(root, doc, ref, pages):
    """The one real file a markdown reference means, or None if it is
    missing or ambiguous (then the sentence is skipped, never flagged)."""
    cands = {(doc.parent / ref).resolve(), (root / ref).resolve()}
    cands = {c for c in cands if c.is_file()}
    if not cands and '/' not in ref:
        cands = {p.resolve() for p in pages if p.name == ref}
    return cands.pop() if len(cands) == 1 else None


@check('docrefs', order=170)
def check_docrefs(root, cfg):
    s = cfg.section('docrefs')
    agent_path = s.get('agent-module', '.agents/scripts/agent.just')
    moved = s.get('moved-dirs', {})
    nouns = s.get('count-nouns',
                  ['files', 'modules', 'subdirectories', 'hosts', 'recipes',
                   'skills'])
    exempt = [re.compile(rx) for rx in s.get(
        'exempt', [r'^wiki/agent-lessons-learned', r'-history\.md$'])]
    skills_dirs = cfg.section('skills').get('dirs', ['.agents/skills'])
    skills_dir = root / skills_dirs[0]

    agent = None
    if agent_path:
        p = root / agent_path
        if p.exists():
            agent = set(JUST_RECIPE.findall(COMMENT.sub('', p.read_text())))
    real = ({p.name for p in skills_dir.iterdir() if p.is_dir()}
            if skills_dir.exists() else set())
    pages = cfg.scope('pages')
    skill_path = re.compile(
        re.escape(skills_dirs[0].rstrip('/')) + r'/([A-Za-z][\w-]*)')

    findings = []
    for path in cfg.scope('docs') + [
            p for d in skills_dirs
            for p in (sorted((root / d).rglob('*.md'))
                      if (root / d).is_dir() else [])]:
        text = path.read_text()
        rel = (path.relative_to(root).as_posix()
               if path.is_relative_to(root) else str(path))

        if agent is not None:
            for m in JUST_MENTION.finditer(text):
                tokens = m.group(1).split()
                if len(tokens) < 2 or tokens[0] != 'agent':
                    continue
                helper = tokens[1]
                if not re.fullmatch(r'[a-z][\w-]*', helper):
                    continue  # a placeholder or flag, not a helper name
                if helper not in agent:
                    findings.append(Finding(
                        'UNKNOWN HELPER', rel,
                        f"`just {m.group(1)}` -- '{helper}' is not a recipe "
                        f"in {agent_path}", see=SEE))

        for rx in (skill_path, SKILL_PLAIN):
            for m in rx.finditer(text):
                name = m.group(1)
                line = text[text.rfind('\n', 0, m.start()) + 1:
                            text.find('\n', m.end())]
                if 'git log' in line:
                    continue  # `git log -- <path>` finds a REMOVED skill
                if name not in real:
                    findings.append(Finding(
                        'UNKNOWN SKILL', rel,
                        f"'{name}' has no {skills_dirs[0]}/{name}/ "
                        f"directory", see=SEE))

        for old, new in moved.items():
            for m in re.finditer(
                    r'`[^`\n]*' + re.escape(old) + r'[^`\n]*`', text):
                findings.append(Finding(
                    'MOVED PATH', rel,
                    f"{m.group(0)} -- {old} is now {new}", see=SEE))

        if not any(rx.search(rel) for rx in exempt):
            for n, sent in bare_counts(text, nouns):
                findings.append(Finding(
                    'BARE COUNT', rel,
                    f"'{n} ...' -- {sent[:100]}", see=(
                        "a count of repo things rots: point at where the "
                        "list lives or name the items; a dated record takes "
                        "a date or 'as of', else <!-- count-ok: reason -->")))

        for sentence in SENTENCE_SPLIT.split(text):
            sentence = ' '.join(sentence.split())
            refs = list(MD_REF.finditer(sentence))
            if len({m.group(1) or m.group(2) for m in refs}) != 1:
                continue
            ref = refs[0]
            for qm in QUOTED_SECTION.finditer(sentence):
                # The quote must sit right next to the page reference, with
                # no other backticked name or "skill" between: otherwise
                # the heading belongs to some other page in the sentence.
                a, b = sorted((ref.span(), qm.span()))
                gap = sentence[a[1]:b[0]]
                if len(gap) > 45 or '`' in gap or 'skill' in gap.lower():
                    continue
                target = _resolve_md(root, path, ref.group(1) or ref.group(2),
                                     pages)
                if target is None:
                    continue
                q = qm.group(1) or qm.group(2)
                want = _norm_heading(q)
                heads = [_norm_heading(h)
                         for _, h in iter_headings(target.read_text())]
                if want and not any(
                        any(h[i:i + len(want)] == want
                            for i in range(len(h) - len(want) + 1))
                        for h in heads):
                    findings.append(Finding(
                        'UNKNOWN SECTION', rel,
                        f'heading "{q}" is not in '
                        f'{target.relative_to(root)}', see=SEE))
    return findings
