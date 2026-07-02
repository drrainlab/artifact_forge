"""IR checks for slotted combs — openness, retention and tooth count,
measured on tagged segments and a ray-cast, no CAD. Self-registers.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm
from .section import ArcSeg, LineSeg, ProfileLoop


def _finding(check: str, ok: bool, message: str) -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=not ok,
    )


def _boundary_crossings_below(loop: ProfileLoop, u: float, v_from: float) -> list[float]:
    """v-coordinates where a downward ray at ``u`` crosses the boundary."""
    crossings: list[float] = []
    for seg in loop.segments:
        samples = 16 if isinstance(seg, ArcSeg) else 1
        pts = [seg.point_at(i / samples) for i in range(samples + 1)]
        for a, b in zip(pts, pts[1:]):
            if (a.u - u) * (b.u - u) > 0:
                continue
            if abs(b.u - a.u) < 1e-12:
                continue
            t = (u - a.u) / (b.u - a.u)
            v = a.v + t * (b.v - a.v)
            if v < v_from:
                crossings.append(v)
    return sorted(crossings, reverse=True)


def check_slots_open_topped(form: PartForm) -> Finding:
    """A downward ray through each slot center must first hit material at
    the cavity BOTTOM — a lid over the throat (closed slot) is caught by the
    first crossing sitting near the top edge instead."""
    f = form.frame
    count = int(f.get("slot_count", 0))
    if count == 0:
        return _finding("form.slots_open_topped", False, "frame declares no slots")
    cv = f["cavity_cv"]
    top = f["total_h"]
    closed = []
    for i in range(count):
        u = f[f"slot_cx_{i}"]
        crossings = _boundary_crossings_below(form.section.outer, u, top + 1.0)
        if not crossings or crossings[0] > cv:
            closed.append(i)
    return _finding(
        "form.slots_open_topped",
        not closed,
        "every slot open to the top edge"
        if not closed
        else f"closed slots: {closed}",
    )


def check_slot_throat_retention(form: PartForm) -> Finding:
    """Measured throat width (distance between each slot's vertical throat
    walls — exact, fillet-trimming preserves their u) must stay narrower
    than the cable."""
    f = form.frame
    cable_d = form.params.get("cable_d")
    count = int(f.get("slot_count", 0))
    if cable_d is None or count == 0:
        return _finding("form.slot_throat_retention", False, "unmeasurable")
    problems = []
    for i in range(count):
        walls = [
            s
            for s in form.section.outer.tagged(f"slot_{i}")
            if isinstance(s, LineSeg) and "throat" in s.tags
        ]
        if len(walls) < 2:
            problems.append(f"slot {i}: throat walls missing")
            continue
        us = sorted(s.a.u for s in walls)
        measured = us[-1] - us[0]
        if not measured < cable_d - 1e-6:
            problems.append(
                f"slot {i}: throat {measured:.2f} >= cable {cable_d:.2f} — no retention"
            )
    return _finding(
        "form.slot_throat_retention",
        not problems,
        "all throats narrower than the cable" if not problems else "; ".join(problems),
    )


def check_teeth_count_matches(form: PartForm) -> Finding:
    import math

    declared = int(form.frame.get("slot_count", 0))
    cavities = sum(
        1
        for s in form.section.outer.tagged("cavity_inner")
        if isinstance(s, ArcSeg) and abs(s.sweep) > math.radians(200)
    )
    ok = cavities == declared and declared > 0
    return _finding(
        "form.teeth_count_matches",
        ok,
        f"{cavities} cavities vs {declared} declared slots",
    )


register_probe("form.slots_open_topped")(lambda form, ctx: check_slots_open_topped(form))
register_probe("form.slot_throat_retention")(
    lambda form, ctx: check_slot_throat_retention(form)
)
register_probe("form.teeth_count_matches")(
    lambda form, ctx: check_teeth_count_matches(form)
)
