"""anchors: every `#fragment` on a markdown link resolves to a real heading
on the target page, slugged the way GitHub renders it. This is the check
`links` explicitly does not do, and the gap between them is where a wrong
anchor once sat unnoticed: the file existed, the fragment didn't, and no
check looked."""
import urllib.parse

from ..findings import Finding
from ..mdcore.links import link_targets
from ..mdcore.slugs import github_slug
from ..registry import check

SEE = "a rename left a reference behind: fix the link or restore the target"


def _page_anchors(path):
    """Every heading anchor a real GitHub render of `path` would produce, as
    a set of slugs."""
    from ..mdcore.headings import iter_headings
    seen = {}
    return {github_slug(text, seen) for _, text in iter_headings(path.read_text())}


@check('anchors', order=90)
def check_anchors(root, cfg):
    """Same-file (`(#see-also)`) and into-another-page fragments both.
    Skips a target `links` would already flag as a broken file path --
    nothing to check the fragment against, and no point duplicating that
    finding."""
    cache = {}
    findings = []
    for path in cfg.scope('docs'):
        for m in link_targets(path.read_text()):
            target = m.group(1).strip()
            if target.startswith(('http://', 'https://', 'mailto:')):
                continue
            if '#' not in target:
                continue
            file_part, _, frag = target.partition('#')
            file_part = urllib.parse.unquote(file_part.strip('<>'))
            frag = urllib.parse.unquote(frag)
            if not frag:
                continue  # a bare (#) with nothing after it -- not real
            resolved = (path.parent / file_part) if file_part else path
            if not resolved.exists():
                continue  # links already reports this
            if resolved not in cache:
                cache[resolved] = _page_anchors(resolved)
            if frag not in cache[resolved]:
                findings.append(Finding(
                    'BROKEN ANCHOR', str(path),
                    f"({target}) -> {resolved} has no heading matching "
                    f"#{frag}", see=SEE))
    return findings
