"""IR checks for the wearable forearm cuff family (wave P2) — every
wearable promise is MEASURED on the final molded loop and the published
frame, never postulated.

Family gate: a form without ``arm_r_inner``/``payload_cv`` frame keys is
not a cuff — checks pass vacuously (the checks_clamp discipline).

Honest scope note: 2D checks cover the section plane. The extrusion
end-rims (X faces) cannot be rounded in the section; their comfort is the
fillet stage's business and stays outside ``comfort_edge_radius_ok``.
"""

from __future__ import annotations

import math

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .molded import joint_is_tangent
from .part import PartForm
from .section import ArcSeg, LineSeg, Pt

#: Donning window vs the FLESH diameter: below 0.75 the limb cannot push
#: through; above 1.02 the cuff free-falls off even soft tissue (1.00..1.02
#: still hangs on flesh while the straps close — measured semantics).
DONNING_LO, DONNING_HI = 0.75, 1.02
#: Snap-retention window for the payload mouth vs the payload diameter
#: (the checks_snap physics constants).
PAYLOAD_GAP_LO, PAYLOAD_GAP_HI = 0.4, 0.97
MIN_STRAP_BRIDGE = 5.0


def _finding(check: str, ok: bool, message: str, *, measured: float | None = None,
             limit: float | None = None, critical: bool = True) -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        measured=measured,
        limit=limit,
        critical=critical and not ok,
    )


def _not_a_cuff(form: PartForm) -> bool:
    return "arm_r_inner" not in form.frame


def _no_payload_clip(form: PartForm) -> bool:
    """Socket-variant cuffs carry no integrated snap-C — payload checks
    gate on their own keys, never hiding the ARM checks."""
    return "payload_cv" not in form.frame


def _vacuous(check: str, why: str = "not a cuff form") -> Finding:
    return Finding(check=check, status=Status.PASS, level=Level.FORM,
                   message=why)


def _sweep_deg(arc: ArcSeg) -> float:
    a = math.degrees(math.atan2(arc.a.v - arc.center.v, arc.a.u - arc.center.u))
    b = math.degrees(math.atan2(arc.b.v - arc.center.v, arc.b.u - arc.center.u))
    return (b - a) % 360.0 if arc.ccw else (a - b) % 360.0


@register_probe("form.body_clearance_ok")
def check_body_clearance_ok(form: PartForm, ctx=None) -> Finding:
    check = "form.body_clearance_ok"
    if _not_a_cuff(form):
        return _vacuous(check)
    f = form.frame
    r_ai = f["arm_r_inner"]
    center = Pt(0.0, 0.0)
    arcs = [s for s in form.section.outer.tagged("body_contact")
            if isinstance(s, ArcSeg) and "fillet" not in s.tags]
    if not arcs:
        return _finding(check, False, "no body_contact arcs in the profile")
    problems: list[str] = []
    worst_r = max(abs(a.radius - r_ai) for a in arcs)
    worst_c = max(a.center.dist(center) for a in arcs)
    if worst_r > 0.05:
        problems.append(f"body arc radius off the frame by {worst_r:.3f}")
    if worst_c > 0.05:
        problems.append(f"body arc center off by {worst_c:.3f}")
    circ = form.params.get("body_circumference",
                           form.params.get("arm_circumference"))
    clearance = form.params.get("body_clearance",
                                form.params.get("arm_clearance"))
    slack = None
    if circ is not None and clearance is not None:
        slack = r_ai - circ / (2.0 * math.pi)
        if slack < clearance - 0.1:
            problems.append(
                f"radial slack {slack:.2f} below the declared skin "
                f"clearance {clearance:g}")
    return _finding(
        check, not problems,
        (f"arm cavity r={r_ai:g} with {slack:.2f} mm measured skin slack"
         if not problems and slack is not None
         else "arm cavity matches the frame" if not problems
         else "; ".join(problems)),
        measured=slack if slack is not None else worst_r,
        limit=clearance if slack is not None else 0.05,
    )


@register_probe("form.arm_mouth_dons_ok")
def check_arm_mouth_dons_ok(form: PartForm, ctx=None) -> Finding:
    check = "form.arm_mouth_dons_ok"
    if _not_a_cuff(form):
        return _vacuous(check)
    if not form.section.outer.tagged("body_contact"):
        return _finding(check, False, "no body_contact chain to measure")
    # The limb enters through the THROAT: the narrowest horizontal aperture
    # at/below the mouth-tip level (tab inner edges; tip fillets ride the
    # widening circle and must not inflate the measurement).
    band_v = form.frame["arm_mouth_tip_v"] + 0.5
    left, right = [], []
    for seg in form.section.outer.segments:
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            pt = seg.point_at(t)
            if pt.v > band_v:
                continue
            (right if pt.u > 0.0 else left).append(abs(pt.u))
    if not left or not right:
        return _finding(check, False, "mouth throat has no boundary points")
    measured = min(left) + min(right)
    d_eff = form.params.get("body_d_eff")
    if d_eff is None:
        circ = form.params.get("body_circumference",
                               form.params.get("arm_circumference"))
        if circ is None:
            return _finding(check, False,
                            "no body_d_eff/arm_circumference to size the mouth")
        d_eff = circ / math.pi
    lo, hi = DONNING_LO * d_eff, DONNING_HI * d_eff
    ok = lo <= measured <= hi
    return _finding(
        check, ok,
        (f"mouth {measured:.1f} within the donning window "
         f"[{lo:.1f}, {hi:.1f}] over a {d_eff:.1f} limb" if ok else
         f"mouth {measured:.1f} outside [{lo:.1f}, {hi:.1f}] for a "
         f"{d_eff:.1f} limb — " + (
             "cannot don over flesh; reduce arm_capture_deg"
             if measured < lo else
             "wider than the limb, the cuff falls off — increase "
             "arm_capture_deg or reduce clearance")),
        measured=measured, limit=hi if measured > hi else lo,
    )


@register_probe("form.comfort_edge_radius_ok")
def check_comfort_edge_radius_ok(form: PartForm, ctx=None) -> Finding:
    check = "form.comfort_edge_radius_ok"
    if _not_a_cuff(form):
        return _vacuous(check)
    r_need = float(form.frame.get("comfort_edge_r", 1.2))
    segs = list(form.section.outer.segments)
    problems: list[str] = []
    fillet_rs: list[float] = []
    n = len(segs)
    for i, seg in enumerate(segs):
        if "body_contact" not in seg.tags or "fillet" in seg.tags:
            continue
        for j in (i - 1, (i + 1) % n):
            other = segs[j]
            if "body_contact" in other.tags:
                continue
            if "pad_wall" in other.tags or "pad_land" in other.tags:
                continue  # pocket edges live under the TPU pad
            if "fillet" in other.tags and isinstance(other, ArcSeg):
                fillet_rs.append(other.radius)
                if other.radius < r_need - 0.05:
                    problems.append(
                        f"contact-edge fillet r={other.radius:.2f} below "
                        f"comfort_edge_r {r_need:g} near ({seg.a.u:.1f}, "
                        f"{seg.a.v:.1f})")
                continue
            prev, nxt = (other, seg) if j == i - 1 else (seg, other)
            if not joint_is_tangent(prev, nxt):
                problems.append(
                    f"sharp body-contact corner at ({nxt.a.u:.1f}, "
                    f"{nxt.a.v:.1f})")
    return _finding(
        check, not problems,
        (f"all body-contact edge fillets >= {r_need:g}" if not problems
         else "; ".join(problems[:4])),
        measured=min(fillet_rs) if fillet_rs else None, limit=r_need,
    )


@register_probe("form.pad_recess_exists")
def check_pad_recess_exists(form: PartForm, ctx=None) -> Finding:
    check = "form.pad_recess_exists"
    if _not_a_cuff(form):
        return _vacuous(check)
    f = form.frame
    r_ai, recess = f["arm_r_inner"], f["pad_recess"]
    want = int(f.get("land_count", 0.0))
    flats = [s for s in form.section.outer.tagged("pad_land")
             if isinstance(s, LineSeg)]
    problems: list[str] = []
    matched = 0
    for i in range(want):
        target = Pt(f[f"land_{i}_u"], f[f"land_{i}_v"])
        near = [s for s in flats if s.point_at(0.5).dist(target) <= 0.3]
        if not near:
            problems.append(f"pad land {i} missing near ({target.u:.1f}, "
                            f"{target.v:.1f})")
            continue
        seg = near[0]
        if abs(seg.length - f[f"land_{i}_w"]) > 0.6:
            problems.append(
                f"pad land {i} width {seg.length:.1f} != {f[f'land_{i}_w']:g}")
        dist = seg.point_at(0.5).dist(Pt(0.0, 0.0))
        if not (r_ai + recess - 0.05 <= dist <= r_ai + recess + 0.05):
            problems.append(
                f"pad land {i} at radial {dist:.2f}, wanted "
                f"{r_ai + recess:.2f} (recess must go OUTWARD)")
        matched += 1
    if matched < want:
        problems.append(f"only {matched}/{want} pad lands found")
    return _finding(
        check, not problems,
        f"{want} TPU pad lands recessed {recess:g} outward" if not problems
        else "; ".join(problems),
        measured=float(matched), limit=float(want),
    )


@register_probe("form.payload_mount_not_on_skin_side")
def check_payload_mount_not_on_skin_side(form: PartForm, ctx=None) -> Finding:
    check = "form.payload_mount_not_on_skin_side"
    if _no_payload_clip(form):
        return _vacuous(check, "no integrated payload clip on this form")
    f = form.frame
    p_cv, r_ao, r_pi = f["payload_cv"], f["arm_r_outer"], f["payload_r_inner"]
    problems: list[str] = []
    if p_cv <= 0.0:
        problems.append(f"payload center at v={p_cv:g} — the skin side")
    if p_cv < r_ao + r_pi:
        problems.append(
            f"payload cavity at {p_cv:g} interpenetrates the arm ring "
            f"(needs >= {r_ao + r_pi:g})")
    faces = form.section.outer.tagged("payload_mouth_face")
    if not faces:
        problems.append("no payload mouth faces — a closed payload ring")
    elif not all(s.point_at(0.5).v > p_cv for s in faces):
        problems.append("payload mouth opens toward the arm, not away")
    return _finding(
        check, not problems,
        "payload clip rides outside the ring and opens away from the body"
        if not problems else "; ".join(problems),
        measured=p_cv, limit=r_ao + r_pi,
    )


@register_probe("form.payload_retention_ok")
def check_payload_retention_ok(form: PartForm, ctx=None) -> Finding:
    check = "form.payload_retention_ok"
    if _no_payload_clip(form):
        return _vacuous(check, "no integrated payload clip on this form")
    f = form.frame
    declared = f["payload_arc_deg"]
    arcs = [s for s in form.section.outer.tagged("payload_contact")
            if isinstance(s, ArcSeg)]
    if not arcs:
        return _finding(check, False, "no payload_contact arc in the profile")
    coverage = sum(_sweep_deg(a) for a in arcs)
    gap = arcs[0].a.dist(arcs[-1].b)
    payload_d = form.params.get("payload_d",
                                2.0 * (f["payload_r_inner"] - 0.3))
    problems: list[str] = []
    if abs(coverage - declared) > 9.0:
        problems.append(
            f"cavity coverage {coverage:.1f} deg vs declared {declared:g}")
    if coverage <= 185.0:
        problems.append(f"coverage {coverage:.1f} <= 185 — no arc retention")
    lo, hi = PAYLOAD_GAP_LO * payload_d, PAYLOAD_GAP_HI * payload_d
    if not lo <= gap <= hi:
        problems.append(
            f"payload mouth {gap:.1f} outside the snap window "
            f"[{lo:.1f}, {hi:.1f}]")
    return _finding(
        check, not problems,
        f"payload arc {coverage:.0f} deg, mouth {gap:.1f} — real snap "
        "retention" if not problems else "; ".join(problems),
        measured=gap, limit=hi,
    )


@register_probe("form.strap_access_ok")
def check_strap_access_ok(form: PartForm, ctx=None) -> Finding:
    check = "form.strap_access_ok"
    if _not_a_cuff(form):
        return _vacuous(check)
    f = form.frame
    r_ai = f["arm_r_inner"]
    tab_top, tab_bot = f["tab_v_top"], f["tab_v_bot"]
    strap_w = form.params.get("body_strap_width",
                              form.params.get("strap_w", 25.0))
    tabs = [r.name for r in form.regions if r.name.startswith("strap_land")]
    if not tabs:
        return _finding(check, False, "no strap_land regions on the form")
    problems: list[str] = []
    for tab in tabs:
        boxes = [c.box for c in form.cutboxes
                 if c.name.startswith(f"strap_slot_{tab}")]
        if len(boxes) != 2:
            problems.append(f"{tab}: {len(boxes)} strap slots, wanted a pair")
            continue
        boxes = sorted(boxes, key=lambda b: b.y0)
        for b in boxes:
            if b.x1 - b.x0 < strap_w + 1.0:
                problems.append(
                    f"{tab}: slot span {b.x1 - b.x0:.1f} below strap width "
                    f"{strap_w:g}+1")
            if not (b.z0 < tab_bot - 0.5 and b.z1 > tab_top + 0.5):
                problems.append(f"{tab}: slot does not pierce the tab")
            ny = min(max(0.0, b.y0), b.y1)
            nz = min(max(0.0, b.z0), b.z1)
            if math.hypot(ny, nz) < r_ai:
                problems.append(f"{tab}: slot cuts into the arm circle")
        bridge = boxes[1].y0 - boxes[0].y1
        if bridge < MIN_STRAP_BRIDGE:
            problems.append(
                f"{tab}: strap bar {bridge:.1f} below {MIN_STRAP_BRIDGE:g}")
    return _finding(
        check, not problems,
        f"strap slot pairs pierce {len(tabs)} tabs clear of the skin"
        if not problems else "; ".join(problems),
    )


@register_probe("form.dovetail_socket_profile_ok")
def check_dovetail_socket_profile_ok(form: PartForm, ctx=None) -> Finding:
    """The socket groove is a REAL dovetail, measured on the loop: two
    flank segments whose bottom ends sit wider apart than their top ends
    by >= 1 mm total, at the declared widths and depth."""
    check = "form.dovetail_socket_profile_ok"
    f = form.frame
    if "groove_top_w" not in f:
        return _vacuous(check, "no dovetail socket on this form")
    flanks = [s for s in form.section.outer.tagged("groove_flank")
              if isinstance(s, LineSeg)]
    if len(flanks) != 2:
        return _finding(check, False,
                        f"{len(flanks)} groove flanks in the profile, need 2")
    problems: list[str] = []
    tops, bottoms = [], []
    for s in flanks:
        top, bot = (s.a, s.b) if s.a.v > s.b.v else (s.b, s.a)
        tops.append(top)
        bottoms.append(bot)
    top_w = abs(tops[0].u - tops[1].u)
    bot_w = abs(bottoms[0].u - bottoms[1].u)
    depth = abs(tops[0].v - bottoms[0].v)
    if abs(top_w - f["groove_top_w"]) > 0.05:
        problems.append(f"opening {top_w:.2f} != declared {f['groove_top_w']:g}")
    if abs(bot_w - f["groove_bottom_w"]) > 0.05:
        problems.append(f"bottom {bot_w:.2f} != declared {f['groove_bottom_w']:g}")
    if bot_w < top_w + 1.0:
        problems.append(f"no undercut: bottom {bot_w:.2f} vs top {top_w:.2f}")
    if abs(depth - f["groove_depth"]) > 0.05:
        problems.append(f"depth {depth:.2f} != declared {f['groove_depth']:g}")
    return _finding(
        check, not problems,
        f"female dovetail {top_w:.1f}/{bot_w:.1f} x {depth:.1f} measured"
        if not problems else "; ".join(problems),
        measured=bot_w - top_w, limit=1.0,
    )


@register_probe("form.dovetail_foot_profile_ok")
def check_dovetail_foot_profile_ok(form: PartForm, ctx=None) -> Finding:
    """The adapter foot is a REAL male dovetail: measured flank widths
    match the frame and the wide end is the FREE end (retention)."""
    check = "form.dovetail_foot_profile_ok"
    f = form.frame
    if "dovetail_root_w" not in f:
        return _vacuous(check, "no dovetail foot on this form")
    flanks = [s for s in form.section.outer.tagged("dovetail_flank")
              if isinstance(s, LineSeg)]
    if len(flanks) != 2:
        return _finding(check, False,
                        f"{len(flanks)} foot flanks in the profile, need 2")
    tops, bottoms = [], []
    for s in flanks:
        top, bot = (s.a, s.b) if s.a.v > s.b.v else (s.b, s.a)
        tops.append(top)
        bottoms.append(bot)
    root_w = abs(tops[0].u - tops[1].u)
    wide_w = abs(bottoms[0].u - bottoms[1].u)
    height = abs(tops[0].v - bottoms[0].v)
    problems: list[str] = []
    if abs(root_w - f["dovetail_root_w"]) > 0.05:
        problems.append(f"root {root_w:.2f} != declared {f['dovetail_root_w']:g}")
    if abs(wide_w - f["dovetail_top_w"]) > 0.05:
        problems.append(f"wide end {wide_w:.2f} != declared {f['dovetail_top_w']:g}")
    if wide_w < root_w + 0.5:
        problems.append("free end not wider than root — no retention")
    if abs(height - f["dovetail_h"]) > 0.05:
        problems.append(f"height {height:.2f} != declared {f['dovetail_h']:g}")
    return _finding(
        check, not problems,
        f"male dovetail {root_w:.1f}/{wide_w:.1f} x {height:.1f} measured"
        if not problems else "; ".join(problems),
        measured=wide_w - root_w, limit=0.5,
    )
