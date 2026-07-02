"""IR checks for the J-hook family — the tip lip really rises by lip_h,
and the bay entry between lip tip and plate stays open. Self-registers.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm
from .regions import Rect2D


def _finding(check: str, ok: bool, message: str, **kw) -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=not ok,
        **kw,
    )


def check_tip_lip_present(form: PartForm) -> Finding:
    f = form.frame
    lip_h = form.params.get("lip_h")
    tips = form.section.outer.tagged("lip_tip")
    if lip_h is None or not tips or "bay_center_v" not in f:
        return _finding("form.tip_lip_present", False, "lip unmeasurable")
    tip_v = max(max(s.a.v, s.b.v) for s in tips)
    measured = tip_v - f["bay_center_v"]
    ok = abs(measured - lip_h) <= 0.05
    return _finding(
        "form.tip_lip_present",
        ok,
        f"lip rise {measured:.2f} vs declared {lip_h:.2f}",
        measured=measured,
        limit=lip_h,
        unit="mm",
    )


MIN_ENTRY_GAP = 4.0


def check_bay_open_top(form: PartForm) -> Finding:
    """No material inside the entry window between the lip tip and the
    plate underside — a lip welded to the plate is a closed bay."""
    f = form.frame
    if "lip_tip_v" not in f:
        return _finding("form.bay_open_top", False, "frame declares no bay")
    gap = f["entry_gap"]
    if gap < MIN_ENTRY_GAP:
        return _finding(
            "form.bay_open_top",
            False,
            f"entry gap {gap:.1f} < {MIN_ENTRY_GAP:g} mm",
            measured=gap,
            limit=MIN_ENTRY_GAP,
        )
    window = Rect2D(
        f["bay_center_u"] - f["r_in"] * 0.6,
        f["lip_tip_v"] + 0.3,
        f["bay_center_u"] + f["r_in"] * 0.6,
        -0.3,
    )
    intruders = 0
    for seg in form.section.outer.segments:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            if window.contains(seg.point_at(t)):
                intruders += 1
                break
    return _finding(
        "form.bay_open_top",
        intruders == 0,
        f"entry gap {gap:.1f} mm clear"
        if intruders == 0
        else f"{intruders} segment(s) intrude into the entry window",
        measured=gap,
    )


register_probe("form.tip_lip_present")(lambda form, ctx: check_tip_lip_present(form))
register_probe("form.bay_open_top")(lambda form, ctx: check_bay_open_top(form))
