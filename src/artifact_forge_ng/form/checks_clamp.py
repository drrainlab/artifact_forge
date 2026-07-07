"""IR checks for the split branch clamp family (Bio-1) — the saddle must be
the declared branch circle with an OPEN mouth at the mating plane (the
split-clamp invariant: never a closed hole around a living branch), the TPU
pad lands must really exist, the axial channel must clear the saddle and the
rail fixing pockets, and the dovetail must measurably be a dovetail.
Self-registers on import.

Every check PASSes with "not a clamp form" when the clamp frame keys are
absent — other archetypes never subscribe these, but a probe must never
crash on foreign geometry.
"""

from __future__ import annotations

import math

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm
from .section import ArcSeg, LineSeg, Pt

#: A clamping bolt axis must stay this far outside the mouth half-width.
BOLT_MOUTH_MARGIN = 2.0
#: Radial clearance the channel keeps to the saddle apex / rail pockets.
CHANNEL_CLEARANCE = 2.0
#: Minimum honest dovetail: undercut of at least 2*rail_h*tan(6 deg).
MIN_DOVETAIL_ANGLE_DEG = 6.0

_CLAMP_KEYS = ("mate_z", "saddle_r", "saddle_cz", "saddle_mouth_half", "clamp_gap")


def _finding(check: str, ok: bool, message: str, *, measured: float | None = None,
             limit: float | None = None) -> Finding:
    return Finding(
        check=check, status=Status.PASS if ok else Status.FAIL, level=Level.FORM,
        message=message, critical=not ok, measured=measured, limit=limit,
    )


def _not_a_clamp(form: PartForm) -> bool:
    return any(k not in form.frame for k in _CLAMP_KEYS)


def _bolt_axes_crossing_mate(form: PartForm) -> list[tuple[str, float]]:
    """(name, y) of every fastener axis that crosses/touches the mating
    plane: clearance holes (they bottom out on it) and Z-pilot bores whose
    span reaches it. The rail fixing pockets live far from the mate plane
    and are excluded by construction."""
    mate_z = form.frame["mate_z"]
    axes: list[tuple[str, float]] = []
    for i, h in enumerate(form.holes):
        x, y, z_top = h.at
        lo, hi = z_top - h.through, z_top
        if lo - 1.0 <= mate_z <= hi + 1.0:
            axes.append((f"hole_{i}", y))
    for b in form.bores:
        if b.axis != "Z":
            continue
        lo, hi = min(b.span), max(b.span)
        if lo - 1.0 <= mate_z <= hi + 1.0:
            axes.append((b.name, b.center[1]))
    return axes


def check_saddle_geometry_ok(form: PartForm) -> Finding:
    check = "form.saddle_geometry_ok"
    if _not_a_clamp(form):
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="not a clamp form")
    f = form.frame
    r, gap, mate_z = f["saddle_r"], f["clamp_gap"], f["mate_z"]
    mouth_half = f["saddle_mouth_half"]
    center = Pt(0.0, f["saddle_cz"])
    problems: list[str] = []

    branch_d = form.params.get("nominal_branch_d")
    if branch_d is not None and abs(r - branch_d / 2.0) > 0.05:
        problems.append(
            f"saddle_r {r:g} does not match nominal_branch_d/2 = {branch_d / 2.0:g}")

    arcs = [s for s in form.section.outer.tagged("saddle_contact")
            if isinstance(s, ArcSeg)]
    if not arcs:
        return _finding(check, False, "no saddle_contact arcs in the profile")
    worst_r = max(abs(a.radius - r) for a in arcs)
    worst_c = max(a.center.dist(center) for a in arcs)
    if worst_r > 0.05:
        problems.append(f"saddle arc radius off by {worst_r:.3f}")
    if worst_c > 0.05:
        problems.append(f"saddle arc center off by {worst_c:.3f}")

    # the compression-gap invariant: the arc center sits gap/2 BEYOND the
    # mating plane (outside the material)
    if abs(abs(f["saddle_cz"] - mate_z) - gap / 2.0) > 0.02:
        problems.append(
            f"saddle center {f['saddle_cz']:g} is not gap/2 = {gap / 2.0:g} "
            f"beyond the mating plane {mate_z:g}")

    # the split-clamp invariant: the mouth is OPEN at the mating edge —
    # arc-chain endpoints land ON the plane, on both sides
    tips = [pt for a in arcs for pt in (a.a, a.b)
            if abs(pt.v - mate_z) <= 0.1]
    if not any(pt.u > 0.3 for pt in tips) or not any(pt.u < -0.3 for pt in tips):
        problems.append(
            "saddle mouth does not open at the mating plane — a closed "
            "branch hole without a split")
    else:
        measured_mouth = max(abs(pt.u) for pt in tips)
        if abs(measured_mouth - mouth_half) > 0.1:
            problems.append(
                f"mouth half-width {measured_mouth:.2f} != declared "
                f"{mouth_half:.2f}")

    # every clamping bolt axis stays clear of the open mouth
    for name, y in _bolt_axes_crossing_mate(form):
        if abs(y) < mouth_half + BOLT_MOUTH_MARGIN:
            problems.append(
                f"bolt axis {name} at y={y:g} sits over the saddle mouth "
                f"(needs |y| >= {mouth_half + BOLT_MOUTH_MARGIN:.1f})")

    return _finding(
        check, not problems,
        f"saddle r={r:g} centered gap/2 beyond the mating plane, mouth open, "
        "bolts clear of the mouth" if not problems else "; ".join(problems),
        measured=worst_r, limit=0.05,
    )


def check_pad_lands_present(form: PartForm) -> Finding:
    check = "form.pad_lands_present"
    if _not_a_clamp(form):
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="not a clamp form")
    f = form.frame
    expected = int(f.get("land_count", 0))
    center = Pt(0.0, f["saddle_cz"])
    recess = f.get("pad_recess", 0.0)
    want_dist = f["saddle_r"] + recess
    flats = [s for s in form.section.outer.tagged("pad_land")
             if isinstance(s, LineSeg)]
    problems: list[str] = []
    if expected == 0:
        problems.append("frame declares no pad lands (land_count missing)")
    if len(flats) != expected:
        problems.append(f"{len(flats)} tagged pad lands, expected {expected}")
    for i in range(expected):
        key = f"land_{i}_u"
        if key not in f:
            problems.append(f"frame lacks land_{i}_* keys")
            continue
        target = Pt(f[f"land_{i}_u"], f[f"land_{i}_v"])
        near = min(flats, key=lambda s: s.point_at(0.5).dist(target),
                   default=None)
        if near is None or near.point_at(0.5).dist(target) > 1.0:
            problems.append(f"no pad land near ({target.u:.1f},{target.v:.1f})")
            continue
        if near.length < f[f"land_{i}_w"] - 0.1:
            problems.append(
                f"land {i} width {near.length:.2f} < {f[f'land_{i}_w']:g} - 0.1")
        ab = near.b - near.a
        dist = abs(ab.cross(center - near.a)) / ab.norm()
        if abs(dist - want_dist) > 0.1:
            problems.append(
                f"land {i} recessed {dist - f['saddle_r']:.2f}, "
                f"expected {recess:g} +-0.1")
    return _finding(
        check, not problems,
        f"{expected} flat pad land(s), width and {recess:g} recess verified"
        if not problems else "; ".join(problems),
        measured=float(len(flats)), limit=float(expected),
    )


def check_clamp_channel_clear(form: PartForm) -> Finding:
    check = "form.clamp_channel_clear"
    f = form.frame
    if "channel_z" not in f:
        if _not_a_clamp(form):
            return Finding(check=check, status=Status.PASS, level=Level.FORM,
                           message="not a clamp form")
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="no axial channel declared")
    axis = form.section.width_axis
    z, y, d = f["channel_z"], f["channel_y"], f["channel_d"]
    bore = next(
        (b for b in form.bores
         if b.axis == axis and abs(b.center[2] - z) < 0.1
         and abs(b.center[1] - y) < 0.1),
        None,
    )
    if bore is None:
        return _finding(check, False,
                        "declared axial channel has no matching bore")
    problems: list[str] = []
    lo, hi = min(bore.span), max(bore.span)
    if lo > 1e-6 or hi < form.width - 1e-6:
        problems.append(
            f"channel span [{lo:g}, {hi:g}] does not cover the body "
            f"[0, {form.width:g}]")
    if bore.overshoot[0] <= 0.0 or bore.overshoot[1] <= 0.0:
        problems.append("channel is not open at both ends (zero overshoot)")
    apex = f.get("saddle_apex_v")
    if apex is not None and z - bore.d / 2.0 < apex + CHANNEL_CLEARANCE:
        problems.append(
            f"channel floor {z - bore.d / 2.0:.1f} cuts into the saddle "
            f"apex zone (needs >= {apex + CHANNEL_CLEARANCE:.1f})")
    for b in form.bores:
        if b.axis == "Z" and b.name.startswith("rail_fix") and 0.0 in b.overshoot:
            floor = min(b.span)
            if z + bore.d / 2.0 + CHANNEL_CLEARANCE > floor:
                problems.append(
                    f"channel top {z + bore.d / 2.0:.1f} reaches the "
                    f"{b.name} pocket floor {floor:.1f} - {CHANNEL_CLEARANCE:g}")
    return _finding(
        check, not problems,
        f"channel d={d:g} spans the body, open both ends, clear of saddle "
        "and rail pockets" if not problems else "; ".join(problems),
        measured=z, limit=apex,
    )


def check_dovetail_rail_profile(form: PartForm) -> Finding:
    check = "form.dovetail_rail_profile"
    if _not_a_clamp(form):
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="not a clamp form")
    f = form.frame
    if "rail_v0" not in f:
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="no rail declared")
    flanks = [s for s in form.section.outer.tagged("rail_flank")
              if isinstance(s, LineSeg)]
    if len(flanks) != 2:
        return _finding(check, False,
                        f"{len(flanks)} tagged rail flanks, expected 2")
    vs = [pt.v for s in flanks for pt in (s.a, s.b)]
    v_root, v_top = min(vs), max(vs)
    rail_h = v_top - v_root
    root_us = sorted(pt.u for s in flanks for pt in (s.a, s.b)
                     if abs(pt.v - v_root) < 0.1)
    top_us = sorted(pt.u for s in flanks for pt in (s.a, s.b)
                    if abs(pt.v - v_top) < 0.1)
    if len(root_us) != 2 or len(top_us) != 2:
        return _finding(check, False, "rail flanks do not span root to top")
    root_w = root_us[1] - root_us[0]
    top_w = top_us[1] - top_us[0]
    problems: list[str] = []
    if rail_h < 4.0:
        problems.append(f"rail height {rail_h:.2f} < 4")
    undercut_min = 2.0 * rail_h * math.tan(math.radians(MIN_DOVETAIL_ANGLE_DEG))
    if top_w - root_w < undercut_min:
        problems.append(
            f"top {top_w:.2f} - root {root_w:.2f} = {top_w - root_w:.2f} < "
            f"{undercut_min:.2f} — not a dovetail, just a ridge")
    if abs(root_us[0] + root_us[1]) > 0.2 or abs(top_us[0] + top_us[1]) > 0.2:
        problems.append("rail flanks are not symmetric about the centerline")
    return _finding(
        check, not problems,
        f"male dovetail: root {root_w:.1f} -> top {top_w:.1f} over "
        f"h {rail_h:.1f}" if not problems else "; ".join(problems),
        measured=top_w - root_w, limit=undercut_min,
    )


register_probe("form.saddle_geometry_ok")(
    lambda form, ctx: check_saddle_geometry_ok(form))
register_probe("form.pad_lands_present")(
    lambda form, ctx: check_pad_lands_present(form))
register_probe("form.clamp_channel_clear")(
    lambda form, ctx: check_clamp_channel_clear(form))
register_probe("form.dovetail_rail_profile")(
    lambda form, ctx: check_dovetail_rail_profile(form))
