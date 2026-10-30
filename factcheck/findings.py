"""The Finding model and how findings print.

A finding is a tagged, pathed message. Its leading tag groups it for the
see-advice lines; `review=True` marks a *soft* finding -- heuristic, needs
a human look, and never failing a run on its own (the run prints an
explicit "only REVIEW findings" note rather than passing silently).

Rendering is one line per finding, `TAG<pad> path: message`, REVIEW
findings rendered as `REVIEW   path: message` so `grep -v '^REVIEW'`
separates hard from soft in downstream tooling.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    tag: str
    path: str
    message: str
    review: bool = False
    see: str | None = None

    def __str__(self):
        if self.review:
            return f"REVIEW   {self.path}: {self.message}"
        return f"{self.tag}  {self.path}: {self.message}"


def see_lines(findings):
    """One `-> TAG / TAG: see <advice>` line per distinct piece of see
    advice carried by the findings, in first-seen order. A check attaches
    advice to its findings; the runner prints it once per kind, after the
    findings, so a finding says where to go without every line repeating
    it."""
    by_advice = {}
    for f in findings:
        if not f.see:
            continue
        tags = by_advice.setdefault(f.see, [])
        if f.tag not in tags:
            tags.append(f.tag)
    return [f"  -> {' / '.join(tags)}: see {advice}"
            for advice, tags in by_advice.items()]
