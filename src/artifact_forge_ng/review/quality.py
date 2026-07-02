"""Shape-quality review v0 — deliberately modest (per the project's own
safety rails): IR metrics first, mesh metrics optional and absent here,
NEVER blocks a build whose topology is correct. Boxiness is a WARN; hard
identity checks (symmetric ring, mouth direction) live in contract/topology
validators, not here.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..form.molded import INTENTIONAL_TAGS, joint_is_tangent
from ..form.part import PartForm


def shape_quality(form: PartForm) -> tuple[dict[str, float], list[Finding]]:
    loop = form.section.outer
    total = 0
    tangent = 0
    for prev, nxt in loop.joints():
        if (prev.tags | nxt.tags) & INTENTIONAL_TAGS:
            continue
        total += 1
        if joint_is_tangent(prev, nxt):
            tangent += 1
    moldedness = tangent / total if total else 1.0
    boxiness = 1.0 - moldedness
    arc_length = sum(
        s.length for s in loop.segments if type(s).__name__ == "ArcSeg"
    )
    curved_fraction = arc_length / loop.perimeter() if loop.perimeter() else 0.0

    scores = {
        "moldedness_score": round(moldedness, 3),
        "boxiness_score": round(boxiness, 3),
        "curved_fraction": round(curved_fraction, 3),
    }

    findings: list[Finding] = [
        Finding(
            check="quality.moldedness",
            status=Status.PASS if moldedness > 0.85 else Status.WARN,
            level=Level.QUALITY,
            message=f"moldedness {moldedness:.2f} (tangent joints / joints)",
            measured=moldedness,
            limit=0.85,
        )
    ]
    if boxiness > 0.3:
        findings.append(
            Finding(
                check="quality.boxiness",
                status=Status.WARN,
                level=Level.QUALITY,
                message=f"boxiness {boxiness:.2f} — profile reads as boxy primitives",
                suggestion="increase blend radii or use a molded section builder",
                measured=boxiness,
                limit=0.3,
            )
        )
    return scores, findings
