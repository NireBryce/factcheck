"""generated: every registered region appears where it must and renders
exactly what its source produces today. Regions themselves are plugins'
to define -- they encode the repo's facts; this is only the
generate-then-lint half."""
from .. import genregions
from ..registry import check


@check('generated', order=130)
def check_generated(root, cfg):
    findings, _notes = genregions.run(root, cfg.scope('pages'), write=False)
    return findings
