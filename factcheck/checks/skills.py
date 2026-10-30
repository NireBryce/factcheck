"""skills: every "skill `name`" / "`name` skill" mention in the docs scope
against real skill directories -- same shape and motivation as `recipes`,
for a skill rename instead of a recipe rename. Plain "the `name`" is
deliberately NOT matched: most backtick tokens in prose are code
identifiers, and the word "skill" right next to the backticks is what
distinguishes a skill mention from one."""
import re

from ..findings import Finding
from ..registry import check

SKILL_MENTION = re.compile(r'[Ss]kill `([a-zA-Z][\w-]*)`|`([a-zA-Z][\w-]*)` skill\b')

SEE = "a rename left a reference behind: fix the doc or rename the skill back"


@check('skills', order=40)
def check_skills(root, cfg):
    dirs = cfg.section('skills').get('dirs', ['.agents/skills'])
    real = set()
    for d in dirs:
        sd = root / d
        if sd.is_dir():
            real |= {p.name for p in sd.iterdir() if p.is_dir()}

    findings = []
    for path in cfg.scope('docs'):
        for m in SKILL_MENTION.finditer(path.read_text()):
            name = m.group(1) or m.group(2)
            if name not in real:
                if len(dirs) == 1:
                    where = f"has no {dirs[0].rstrip('/')}/{name}/ directory"
                else:
                    where = f"names no directory under {', '.join(dirs)}"
                findings.append(Finding(
                    'UNKNOWN SKILL', str(path), f"'{name}' {where}",
                    see=SEE))
    return findings
