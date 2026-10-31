"""links: every relative markdown link in the docs scope resolves to a real
file. Fully general -- a link target is unambiguously either a real path or
not, no historical-prose judgement call needed. The fragment half of a link
is `anchors`' job; this one deliberately only checks the file half and says
so."""
import urllib.parse

from ..findings import Finding
from ..mdcore.links import link_targets
from ..registry import check

SEE = "a rename left a reference behind: fix the link or restore the target"


@check('links', order=80)
def check_links(root, cfg):
    """Skips `http(s)://`/`mailto:` targets (nothing on disk to check) and a
    pure in-page anchor (`(#see-also)`, no file component). Percent-decodes
    the target first -- a link to a directory whose name contains a space is
    written percent-encoded, and comparing the raw encoded string against
    the filesystem is what would make this check wrong about a link that
    actually works."""
    findings = []
    for path in cfg.scope('docs'):
        for m in link_targets(path.read_text()):
            target = m.group(1).strip()
            if target.startswith(('http://', 'https://', 'mailto:')):
                continue
            file_part = urllib.parse.unquote(
                target.split('#', 1)[0].strip('<>'))
            if not file_part:
                continue  # pure in-page anchor, e.g. (#see-also)
            resolved = path.parent / file_part
            if not resolved.exists():
                findings.append(Finding(
                    'BROKEN LINK', str(path),
                    f"({target}) -> {resolved} does not exist", see=SEE))
    return findings
