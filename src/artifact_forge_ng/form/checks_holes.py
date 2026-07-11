"""IR checks for hole patterns — minimum web between holes and to the
outline. The builder declares the plate outline in the frame dict (numeric
keys only): rect outlines via ``outline_u0/v0/u1/v1`` (+``outline_corner_r``),
circular ones via ``outline_outer_r`` (+``outline_cx/cy``, ``outline_inner_r``).
``min_web`` comes from the resolved params. Self-registers on import.
"""

from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .part import PartForm
from .patterns import CircleOutline, Outline, RectOutline, min_web_violations
from .regions import Rect2D
from .section import Pt

DEFAULT_MIN_WEB = 3.0


from .checks_common import make_finding
_finding = make_finding


def _outline_from(form: PartForm) -> Outline | None:
    f = form.frame
    if "outline_outer_r" in f:
        return CircleOutline(
            center=(f.get("outline_cx", 0.0), f.get("outline_cy", 0.0)),
            outer_r=f["outline_outer_r"],
            inner_r=f.get("outline_inner_r", 0.0),
        )
    if "outline_u0" in f:
        return RectOutline(
            rect=Rect2D(f["outline_u0"], f["outline_v0"], f["outline_u1"], f["outline_v1"]),
            corner_r=f.get("outline_corner_r", 0.0),
        )
    return None


def _violations(form: PartForm) -> tuple[list[str], list[str]] | None:
    outline = _outline_from(form)
    if outline is None:
        return None
    min_web = form.params.get("min_web", DEFAULT_MIN_WEB)
    # COAXIAL Z-bores are one stepped bore (a bearing seat's pocket over
    # its through hole), not a hole pair — keep only the widest per axis.
    # A bore CENTERED OUTSIDE the outline is a perimeter-sculpting cutter
    # (a lobed knob's finger cove) — it redefines the boundary instead of
    # weakening a web, so it stays out of the web math.
    by_axis: dict[tuple[float, float], float] = {}
    for b in form.bores:
        if b.axis != "Z":
            continue
        if outline.edge_distance(Pt(b.center[0], b.center[1])) < 0.0:
            continue
        key = (round(b.center[0], 3), round(b.center[1], 3))
        by_axis[key] = max(by_axis.get(key, 0.0), b.d / 2.0)
    extra = tuple((x, y, r) for (x, y), r in by_axis.items())
    problems = min_web_violations(form.holes, outline, min_web, extra)
    pair = [p for p in problems if "edge web" not in p]
    edge = [p for p in problems if "edge web" in p]
    return pair, edge


def check_min_web_between_holes(form: PartForm) -> Finding:
    split = _violations(form)
    if split is None:
        return _finding(
            "form.min_web_between_holes", False,
            "builder declared no outline_* frame keys — cannot check webs",
        )
    pair, _ = split
    return _finding(
        "form.min_web_between_holes",
        not pair,
        "hole-to-hole webs ok" if not pair else "; ".join(pair),
    )


def check_holes_within_outline(form: PartForm) -> Finding:
    split = _violations(form)
    if split is None:
        return _finding(
            "form.holes_within_outline", False,
            "builder declared no outline_* frame keys — cannot check edges",
        )
    _, edge = split
    return _finding(
        "form.holes_within_outline",
        not edge,
        "hole-to-edge webs ok" if not edge else "; ".join(edge),
    )


register_probe("form.min_web_between_holes")(
    lambda form, ctx: check_min_web_between_holes(form)
)
register_probe("form.holes_within_outline")(
    lambda form, ctx: check_holes_within_outline(form)
)
