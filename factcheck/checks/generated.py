"""generated: every registered region appears where it must and renders
exactly what its source produces today. Regions themselves are plugins'
to define -- they encode the repo's facts; this is only the
generate-then-lint half."""
from pathlib import Path

from .. import genregions, plugins
from ..fixers import fixer
from ..registry import check


@check('generated', order=130)
def check_generated(root, cfg):
    findings, _notes = genregions.run(root, cfg.scope('pages'), write=False)
    return findings


@fixer('fix-generated')
def fix_generated(root, cfg, files):
    """Rewrites every registered region on the named pages from its source,
    keeping hand-written cells per row: the write half of `generated`.
    Plugins are loaded first, since they are where regions come from.
    Prints what it updated, any hand text a dropped row carried, and the
    findings still standing after the write (an empty hand cell to fill
    in); exits 1 while any remain."""
    plugins.load(cfg)
    pages = [(Path(f) if Path(f).is_absolute() else Path.cwd() / f).resolve()
             for f in files]
    root = Path(root).resolve()
    for page in pages:
        if not page.is_file():
            print(f"fix-generated: {page} does not exist")
            return 2
        if not page.is_relative_to(root):
            print(f"fix-generated: {page} is outside the repo root {root} "
                  f"(file arguments resolve against the current directory)")
            return 2
    findings, notes = genregions.run(root, pages, write=True)
    named = {p.relative_to(root).as_posix() for p in pages}
    # A region whose home page wasn't named isn't missing, just not asked
    # about.
    findings = [f for f in findings
                if not (f.tag == 'MISSING REGION' and f.path not in named)]
    for line in notes:
        print(line)
    for f in findings:
        print(f)
    return 1 if findings else 0
