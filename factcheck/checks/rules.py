"""rules: path-scoped rule files (`.agents/rules/*.md`).

Each must open with frontmatter whose only field is `paths:` -- the only
field harnesses read; anything else is silently ignored -- as a non-empty
list of quoted globs. Every glob must match at least one git-tracked file:
a glob that matches nothing means the rule never loads, and nothing says
so. And the pointer file (AGENTS.md) must name each rule, because
harnesses without rule support depend on that pointer."""
import re

from ..findings import Finding
from ..globs import glob_regex
from ..gitfiles import tracked_files
from ..registry import check

# A rule's frontmatter: `---\n...\n---\n` opening the file, strict on
# purpose.
RULE_FRONTMATTER = re.compile(r'\A---\n(.*?)\n---\n', re.S)
# A `paths:` item: `  - "glob"`, nothing else.
RULE_PATH_ITEM = re.compile(r'^\s+-\s+"([^"]+)"\s*$')

SEE = ("a rule that never loads protects nothing: fix the frontmatter or "
       "the glob, and name the file in the pointer doc")


def rule_files(root, rules_dir):
    """`<rules_dir>/**/*.md`, sorted. Missing dir means the repo has no
    path-scoped rules: nothing to check."""
    d = root / rules_dir
    return sorted(d.rglob('*.md')) if d.is_dir() else []


def rule_globs(root, rules_dir):
    """{rules filename: [globs]} from frontmatter, leniently -- `rules`
    reports a malformed one."""
    out = {}
    base = root / rules_dir
    for path in rule_files(root, rules_dir):
        m = RULE_FRONTMATTER.match(path.read_text())
        lines = m.group(1).splitlines() if m else []
        out[path.relative_to(base).as_posix()] = [
            i.group(1) for i in map(RULE_PATH_ITEM.match, lines) if i]
    return out


@check('rules', order=160)
def check_rules(root, cfg):
    s = cfg.section('rules')
    rules_dir = s.get('dir', '.agents/rules')
    pointer = s.get('pointer', 'AGENTS.md')
    findings = []
    rules = rule_files(root, rules_dir)
    if not rules:
        return findings
    tracked = tracked_files(root)
    pointer_text = (root / pointer).read_text()
    for path in rules:
        rel = path.relative_to(root).as_posix()
        if rel not in pointer_text:
            findings.append(Finding(
                'UNLISTED RULE', rel,
                f"{pointer} does not name it -- harnesses without rule "
                f"support would never see it", see=SEE))
        m = RULE_FRONTMATTER.match(path.read_text())
        if not m:
            findings.append(Finding(
                'RULE FRONTMATTER', rel,
                "no leading --- frontmatter block -- without `paths:` it "
                "loads in every session", see=SEE))
            continue
        lines = [l for l in m.group(1).splitlines() if l.strip()]
        if not lines or lines[0].rstrip() != 'paths:':
            findings.append(Finding(
                'RULE FRONTMATTER', rel,
                "frontmatter must be `paths:` followed by a list of quoted "
                "globs", see=SEE))
            continue
        globs = []
        for line in lines[1:]:
            item = RULE_PATH_ITEM.match(line)
            if not item:
                findings.append(Finding(
                    'RULE FRONTMATTER', rel,
                    f"unexpected line {line!r} -- `paths` is the only field "
                    f'harnesses read, as `  - "glob"` items', see=SEE))
                continue
            globs.append(item.group(1))
        if not globs:
            findings.append(Finding(
                'RULE FRONTMATTER', rel, "`paths:` is empty", see=SEE))
        for g in globs:
            rx = glob_regex(g)
            if not any(rx.match(f) for f in tracked):
                findings.append(Finding(
                    'DEAD RULE GLOB', rel,
                    f"{g!r} matches no tracked file -- the rule would "
                    f"never load", see=SEE))
    return findings
