"""IR checks for the wall tool ring mount family — the saddle must match
the declared tool, the mouth must retain yet admit it, the anchors must be
reachable, and the ring must actually be carried by the flange. Plus the
family's honesty warning: AF verifies the plastic, never the wall.
Self-registers on import.
"""

from __future__ import annotations

import math

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm
from .section import ArcSeg, Pt
from .silhouette import cavity_coverage_deg

#: The molded pass rounds the mouth tips, shaving a few degrees of arc.
ARC_TOL_DEG = 9.0
#: Post-molding retention floor: the measured throat must stay this much
#: narrower than the tool body.
RETENTION_MARGIN_MM = 0.3


from .checks_common import make_finding
_finding = make_finding


def check_tool_saddle_radius_ok(form: PartForm) -> Finding:
    tool_d = form.params.get("tool_d")
    clearance = form.params.get("clearance")
    if tool_d is None or clearance is None:
        return _finding("form.tool_saddle_radius_ok", False,
                        "no tool_d/clearance params")
    expected = tool_d / 2.0 + clearance
    center = Pt(form.frame["saddle_cu"], form.frame["saddle_cz"])
    arcs = [s for s in form.section.outer.tagged("saddle_contact")
            if isinstance(s, ArcSeg)]
    if not arcs:
        return _finding("form.tool_saddle_radius_ok", False,
                        "no saddle_contact arcs in the profile")
    worst_r = max(abs(a.radius - expected) for a in arcs)
    worst_c = max(a.center.dist(center) for a in arcs)
    ok = worst_r <= 0.05 and worst_c <= 0.05
    return _finding(
        "form.tool_saddle_radius_ok", ok,
        f"saddle radius off by {worst_r:.3f}, center off by {worst_c:.3f} "
        f"(expected r {expected:.2f} at (0, {center.v:g}))",
        measured=expected + worst_r, limit=expected,
    )


def check_tool_clearance_ok(form: PartForm) -> Finding:
    tool_d = form.params.get("tool_d")
    clearance = form.params.get("clearance")
    d_eff = form.frame.get("d_eff")
    if tool_d is None or clearance is None or d_eff is None:
        return _finding("form.tool_clearance_ok", False,
                        "no tool_d/clearance/d_eff to measure")
    consistent = abs(d_eff - tool_d - 2.0 * clearance) <= 0.02
    sane = 0.2 <= clearance <= 2.2
    ok = consistent and sane
    return _finding(
        "form.tool_clearance_ok", ok,
        f"effective bore {d_eff:.2f} vs tool {tool_d:g} + 2x{clearance:g} "
        f"clearance" + ("" if sane else " (clearance outside 0.2..2.2)"),
        measured=(d_eff - tool_d) / 2.0, limit=clearance,
        suggestion="" if ok else "clearance 0.5=tight fit, 1.0=normal, 1.5=loose",
    )


def check_retention_angle_ok(form: PartForm) -> Finding:
    declared = form.frame.get("capture_deg")
    if declared is None:
        return _finding("form.retention_angle_ok", False, "no capture_deg in frame")
    center = Pt(form.frame["saddle_cu"], form.frame["saddle_cz"])
    measured = cavity_coverage_deg(form.section.outer, center)
    ok = abs(measured - declared) <= ARC_TOL_DEG and measured > 190.0
    return _finding(
        "form.retention_angle_ok", ok,
        f"saddle wraps {measured:.1f} deg vs declared {declared:g} deg "
        "(retention needs > 190)",
        measured=measured, limit=declared,
    )


def check_mouth_gap_ok(form: PartForm) -> Finding:
    """The physical throat, measured on the FINAL (molded) loop: minimum
    left-right free chord in the mouth band. Sampling every segment catches
    the fillet arcs the molded pass inserted at the tips."""
    tool_d = form.params.get("tool_d")
    d_eff = form.frame.get("d_eff")
    tip_v = form.frame.get("mouth_tip_v")
    if tool_d is None or d_eff is None or tip_v is None:
        return _finding("form.mouth_gap_ok", False, "no mouth frame keys")
    right: list[Pt] = []
    left: list[Pt] = []
    for seg in form.section.outer.segments:
        for i in range(13):
            pt = seg.point_at(i / 12.0)
            if pt.v < tip_v - 1.0:
                continue
            if pt.u > 0.3:
                right.append(pt)
            elif pt.u < -0.3:
                left.append(pt)
    if not right or not left:
        return _finding("form.mouth_gap_ok", False,
                        "mouth band has no left/right material to measure")
    gap = min(p.dist(q) for p in right for q in left)
    lo, hi = 0.7 * d_eff, tool_d - RETENTION_MARGIN_MM
    ok = lo <= gap <= hi
    return _finding(
        "form.mouth_gap_ok", ok,
        f"mouth throat {gap:.2f} vs tool {tool_d:g} "
        f"(must stay within {lo:.1f}..{hi:.1f}: narrower cannot insert, "
        "wider never retains)",
        measured=gap, limit=hi,
        suggestion="" if ok else "adjust capture_deg (wider arc = narrower mouth)",
    )


def check_mount_hole_positions_ok(form: PartForm) -> Finding:
    spacing = form.params.get("mount_spacing")
    flange_h = form.params.get("flange_h")
    collar_h = form.frame.get("collar_h", form.width)
    head_r = form.frame.get("screw_head_r", 5.0)
    if spacing is None or flange_h is None:
        return _finding("form.mount_hole_positions_ok", False,
                        "no mount_spacing/flange_h params")
    if len(form.holes) != 2:
        return _finding("form.mount_hole_positions_ok", False,
                        f"expected exactly 2 anchor holes, found {len(form.holes)}")
    (x0, y0, _), (x1, y1, _) = (h.at for h in form.holes)
    problems: list[str] = []
    if max(abs(y0), abs(y1)) > 0.01:
        problems.append("holes off the flange centerline")
    if abs(abs(x1 - x0) - spacing) > 0.05:
        problems.append(
            f"hole spacing {abs(x1 - x0):.2f} != declared {spacing:g}")
    lo_x, hi_x = min(x0, x1), max(x0, x1)
    if lo_x < collar_h + head_r + 3.5:
        problems.append(
            f"lower anchor at {lo_x:.1f} too close to the collar "
            f"(needs >= {collar_h + head_r + 3.5:.1f})")
    if hi_x > flange_h - head_r - 3.0:
        problems.append(
            f"upper anchor at {hi_x:.1f} too close to the flange top edge")
    return _finding(
        "form.mount_hole_positions_ok", not problems,
        "both anchors on the centerline, clear of collar and edges"
        if not problems else "; ".join(problems),
        measured=abs(x1 - x0), limit=spacing,
        suggestion="" if not problems else "reduce mount_spacing or grow flange_h",
    )


def check_ribs_connect_saddle_to_flange(form: PartForm) -> Finding:
    f = form.frame
    keys = ("ring_wall", "fusion_half_w", "saddle_r", "r_outer", "saddle_cz", "flange_t")
    if any(k not in f for k in keys):
        return _finding("form.ribs_connect_saddle_to_flange", False,
                        "no ring frame keys to measure")
    ring_wall, fusion = f["ring_wall"], f["fusion_half_w"]
    r_i, r_o = f["saddle_r"], f["r_outer"]
    s, t = f["saddle_cz"], f["flange_t"]
    problems: list[str] = []
    if fusion < 2.0 * ring_wall:
        problems.append(
            f"fusion half-width {fusion:.1f} < {2.0 * ring_wall:g} — the ring "
            "hangs on a sliver")
    for rib in form.ribs:
        b = rib.box
        if b.z0 > t - 0.4:
            problems.append(f"rib {rib.name!r} does not weld into the flange")
        min_y = 0.0 if b.y0 <= 0.0 <= b.y1 else min(abs(b.y0), abs(b.y1))
        ring_low = s - math.sqrt(max(r_o * r_o - min_y * min_y, 0.0))
        if min_y >= r_o - 0.5:
            problems.append(f"rib {rib.name!r} floats outside the ring flank")
        elif b.z1 < ring_low + 0.5:
            problems.append(f"rib {rib.name!r} does not reach the ring flank")
        if min_y < r_i + 0.5:
            cavity_low = s - math.sqrt(max(r_i * r_i - min_y * min_y, 0.0))
            if b.z1 > cavity_low - 0.3:
                problems.append(f"rib {rib.name!r} would cut into the saddle cavity")
    return _finding(
        "form.ribs_connect_saddle_to_flange", not problems,
        "ring fused and every gusset bridges flange to ring"
        if not problems else "; ".join(problems),
        measured=fusion, limit=2.0 * ring_wall,
    )


def check_anchor_wall_strength_unverified(form: PartForm) -> Finding:
    """ALWAYS a warning, never a pass — AF estimated the plastic geometry
    and the load path, but wall material and anchor pull-out rating are
    external assumptions it cannot measure."""
    load_n = form.frame.get("load_n_est", 0.0)
    moment = form.frame.get("moment_nmm_est", 0.0)
    return Finding(
        check="form.anchor_wall_strength_unverified",
        status=Status.WARN,
        level=Level.FORM,
        message=(
            f"designed for ~{load_n:.0f} N tool weight, ~{moment / 1000.0:.1f} N*m "
            "moment at the anchors (safety factor included) — wall material and "
            "anchor rating are external assumptions AF does not verify"
        ),
        measured=moment,
        suggestion="use anchors rated for the wall type; drywall needs toggle bolts",
    )


register_probe("form.tool_saddle_radius_ok")(
    lambda form, ctx: check_tool_saddle_radius_ok(form))
register_probe("form.tool_clearance_ok")(
    lambda form, ctx: check_tool_clearance_ok(form))
register_probe("form.retention_angle_ok")(
    lambda form, ctx: check_retention_angle_ok(form))
register_probe("form.mouth_gap_ok")(
    lambda form, ctx: check_mouth_gap_ok(form))
register_probe("form.mount_hole_positions_ok")(
    lambda form, ctx: check_mount_hole_positions_ok(form))
register_probe("form.ribs_connect_saddle_to_flange")(
    lambda form, ctx: check_ribs_connect_saddle_to_flange(form))
register_probe("form.anchor_wall_strength_unverified")(
    lambda form, ctx: check_anchor_wall_strength_unverified(form))
