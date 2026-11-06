"""pins: every configured `[[pins]]` entry resolves to exactly one region
of its file today, and any `contains` text still sits inside it -- a pin
that no longer resolves is drift made loud instead of a reference that
silently points somewhere else."""
from ..findings import Finding
from ..pins import PinError, parse, resolve, span_text
from ..registry import check


@check('pins', order=105)
def check_pins(root, cfg):
    """Vacuous with no pins configured."""
    try:
        pins = parse(cfg.section('pins'))
    except PinError as e:
        return [Finding(e.tag, str(cfg.source or 'config'), str(e))]
    findings = []
    for pin in pins:
        path = root / pin['file']
        try:
            lo, hi, lines = resolve(root, pin)
        except PinError as e:
            # resolve() names the file so the pin tools can print its
            # errors standalone; the finding's path already says it.
            msg = str(e)
            prefix = f"{pin['file']}: "
            findings.append(Finding(
                e.tag, str(path),
                msg[len(prefix):] if msg.startswith(prefix) else msg))
            continue
        if 'contains' in pin and pin['contains'] not in span_text(lines, lo, hi):
            findings.append(Finding(
                'DRIFTED PIN', str(path),
                f"pin {pin['id']!r} resolves to lines {lo}-{hi}, but its "
                f"contains-text {pin['contains']!r} is not there any more"))
    return findings
