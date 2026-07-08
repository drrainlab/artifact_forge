"""Topology probes — the v1 underdesk-clip invariants (topology.py:236-333)
remapped onto the NG frame, generalized to read every coordinate from the
PartForm frame (never re-derived arithmetic — the v1 frame discipline,
enforced by data flow).

Probe verdicts are geometric facts measured on the compiled solid: a
symmetric C-ring FAILS ``asymmetric_lips_geometry`` no matter what the
parameters claim.
"""

from __future__ import annotations

from ..cad.geometry import Geometry
from ..cad.probes import box_probe, channel_probe, solid_fraction
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from .probes import register_probe


def _finding(check: str, ok: bool, message: str, measured: float | None = None,
             limit: float | None = None) -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.TOPOLOGY,
        message=message,
        critical=True,
        measured=measured,
        limit=limit,
    )


@register_probe("topology.single_connected_solid")
def single_connected_solid(geometry: Geometry, form: PartForm) -> Finding:
    n = geometry.solid_count()
    valid = geometry.is_valid()
    ok = n == 1 and valid
    return _finding(
        "topology.single_connected_solid",
        ok,
        f"{n} solid(s), valid={valid}",
        measured=float(n),
        limit=1.0,
    )


@register_probe("topology.cavity_open")
def cavity_open(geometry: Geometry, form: PartForm) -> Finding:
    """The cable volume along X through the cavity center must be void."""
    f = form.frame
    y, z = f["cavity_center_u"], f["cavity_center_v"]
    d = min(f["mouth_gap"], f["r_cavity"])  # a bundle-ish probe
    probe = channel_probe([(-2.0, y, z), (form.width + 2.0, y, z)], d=d)
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.cavity_open",
        frac < 0.05,
        f"cable path solid fraction {frac:.3f}",
        measured=frac,
        limit=0.05,
    )


@register_probe("topology.mouth_opens_sideways")
def mouth_opens_sideways(geometry: Geometry, form: PartForm) -> Finding:
    """A probe straddling the outer wall at mouth height must pass through
    void — the wall is pierced toward +Y, not closed."""
    f = form.frame
    wall_u, vc = f["wall_outer_u"], f["cavity_center_v"]
    m = f["mouth_half"]
    zone = box_probe(
        form.width * 0.25, wall_u - f["r_outer"] * 0.15, vc - m * 0.5,
        form.width * 0.75, wall_u + 1.0, vc + m * 0.5,
    )
    frac = solid_fraction(geometry.workplane, zone)
    return _finding(
        "topology.mouth_opens_sideways",
        frac < 0.25,
        f"mouth zone solid fraction {frac:.3f} (open mouth is void)",
        measured=frac,
        limit=0.25,
    )


@register_probe("topology.asymmetric_lips_geometry")
def asymmetric_lips_geometry(geometry: Geometry, form: PartForm) -> Finding:
    """Real asymmetry: in the reach band BETWEEN the two tip lengths,
    material exists at the lower lip's height and NOT at the upper's —
    the two-band probe from v1."""
    f = form.frame
    upper_tip, lower_tip = f["upper_lip_tip_u"], f["lower_lip_tip_u"]
    if lower_tip - upper_tip < 2.0:
        return _finding(
            "topology.asymmetric_lips_geometry",
            False,
            f"lip tips too close ({upper_tip:.1f} vs {lower_tip:.1f}) — symmetric",
        )
    vc, m, band = f["cavity_center_v"], f["mouth_half"], f["lip_band"]
    y0, y1 = upper_tip + 0.5, lower_tip - 0.5
    x0, x1 = form.width * 0.25, form.width * 0.75
    lower_zone = box_probe(x0, y0, vc - band - 0.5, x1, y1, vc - m + 0.2)
    upper_zone = box_probe(x0, y0, vc + m - 0.2, x1, y1, vc + band + 0.5)
    lower_frac = solid_fraction(geometry.workplane, lower_zone)
    upper_frac = solid_fraction(geometry.workplane, upper_zone)
    ok = lower_frac > 0.25 and upper_frac < 0.1
    return _finding(
        "topology.asymmetric_lips_geometry",
        ok,
        f"reach band: lower fill {lower_frac:.2f} (needs >0.25), "
        f"upper fill {upper_frac:.2f} (needs <0.1)",
        measured=lower_frac,
    )


@register_probe("topology.flange_above_cradle")
def flange_above_cradle(geometry: Geometry, form: PartForm) -> Finding:
    if not form.plates:
        return _finding("topology.flange_above_cradle", False, "no flange plate")
    plate = form.plates[0]
    slab = box_probe(
        plate.x0 + 2, plate.y0 + 2, plate.z_bottom + 0.2,
        plate.x1 - 2, plate.y1 - 2, plate.z_top - 0.2,
    )
    frac = solid_fraction(geometry.workplane, slab)
    # The hook body may poke into the plate by the weld overlap — that is
    # the joint, not an embedded flange.
    hook_ok = form.frame["hook_top_v"] <= plate.z_bottom + 0.7 + 0.1
    ok = frac > 0.5 and hook_ok
    return _finding(
        "topology.flange_above_cradle",
        ok,
        f"flange slab fill {frac:.2f}, hook top at {form.frame['hook_top_v']:.1f}",
        measured=frac,
    )


@register_probe("topology.screw_holes_open")
def screw_holes_open(geometry: Geometry, form: PartForm) -> Finding:
    blocked = []
    for hole in form.holes:
        x, y, z_top = hole.at
        probe = channel_probe(
            [(x, y, z_top + 1.0), (x, y, z_top - hole.through - 1.0)], d=3.0
        )
        if solid_fraction(geometry.workplane, probe) > 0.2:
            blocked.append(hole.at)
    return _finding(
        "topology.screw_holes_open",
        not blocked,
        "all screw holes pass through" if not blocked else f"blocked holes: {blocked}",
    )


@register_probe("topology.countersinks_present")
def countersinks_present(geometry: Geometry, form: PartForm) -> Finding:
    head_r = form.frame.get("screw_head_r", 3.5)
    missing = []
    for hole in form.holes:
        if not hole.countersink:
            continue
        x, y, z_top = hole.at
        if hole.countersink_face == "bottom":
            z_lo, z_hi = z_top - hole.through + 0.05, z_top - hole.through + 0.4
        else:
            z_lo, z_hi = z_top - 0.4, z_top - 0.05
        band = box_probe(x - head_r, y - head_r, z_lo, x + head_r, y + head_r, z_hi)
        if solid_fraction(geometry.workplane, band) > 0.9:
            missing.append(hole.at)
    return _finding(
        "topology.countersinks_present",
        not missing,
        "countersinks present" if not missing else f"no countersink at: {missing}",
    )


@register_probe("topology.tool_void_open")
def tool_void_open(geometry: Geometry, form: PartForm) -> Finding:
    """The wall tool mount's saddle: the tool-body cylinder along the tool
    axis (X) AND the mouth window (between the prong tips, out past the
    ring) must both be real voids — a blocked saddle or a grown-shut mouth
    is a paperweight, not a holder."""
    f = form.frame
    if "tool_probe_d" not in f:
        return _finding("topology.tool_void_open", False,
                        "frame declares no tool probe sizes")
    y, z = f.get("saddle_cu", 0.0), f["saddle_cz"]
    axis = channel_probe(
        [(-2.0, y, z), (form.width + 2.0, y, z)], d=f["tool_probe_d"]
    )
    frac_axis = solid_fraction(geometry.workplane, axis)
    half = f["mouth_probe_d"] / 2.0
    mouth = box_probe(
        1.0, y - half, f["mouth_tip_v"] + 0.5,
        max(form.width - 1.0, 2.0), y + half, z + f["r_outer"] + 2.0,
    )
    frac_mouth = solid_fraction(geometry.workplane, mouth)
    ok = frac_axis < 0.05 and frac_mouth < 0.05
    return _finding(
        "topology.tool_void_open",
        ok,
        f"tool axis solid fraction {frac_axis:.3f}, "
        f"mouth window solid fraction {frac_mouth:.3f}",
        measured=max(frac_axis, frac_mouth),
        limit=0.05,
    )


@register_probe("topology.revolve_cavity_open")
def revolve_cavity_open(geometry: Geometry, form: PartForm) -> Finding:
    """The revolved cavity + cable exit must be void along the axis, end to
    end (below the base through above the rim)."""
    f = form.frame
    exit_r = f.get("exit_r")
    if exit_r is None:
        return _finding("topology.revolve_cavity_open", False, "frame declares no exit")
    probe = channel_probe(
        [(0.0, 0.0, -2.0), (0.0, 0.0, f["height"] + 2.0)], d=1.6 * exit_r
    )
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.revolve_cavity_open",
        frac < 0.05,
        f"axis probe solid fraction {frac:.3f}",
        measured=frac,
        limit=0.05,
    )


@register_probe("topology.channel_continuous")
def channel_continuous(geometry: Geometry, form: PartForm) -> Finding:
    """The wiring channel must be void along its declared L-path (frame
    keys channel_x / channel_entry_u / channel_z / channel_exit_u)."""
    f = form.frame
    needed = ("channel_x", "channel_entry_u", "channel_z", "channel_exit_u")
    if any(k not in f for k in needed):
        return _finding(
            "topology.channel_continuous", False, "frame declares no channel path"
        )
    d = form.params.get("channel_d", 6.0)
    x, entry_u, z_c, exit_u = (f[k] for k in needed)
    top_z = f.get("flange_t", 5.0) + 2.0
    path = [(x, entry_u, top_z), (x, entry_u, z_c), (x, exit_u + 2.0, z_c)]
    probe = channel_probe(path, d=0.8 * d)
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.channel_continuous",
        frac < 0.05,
        f"L-path solid fraction {frac:.3f}",
        measured=frac,
        limit=0.05,
    )


@register_probe("topology.bay_open")
def bay_open(geometry: Geometry, form: PartForm) -> Finding:
    """The J-hook entry window between lip tip and plate underside must be
    void on the compiled solid."""
    f = form.frame
    if "lip_tip_v" not in f:
        return _finding("topology.bay_open", False, "frame declares no bay")
    zone = box_probe(
        form.width * 0.25, f["bay_center_u"] - f["r_in"] * 0.5, f["lip_tip_v"] + 0.5,
        form.width * 0.75, f["bay_center_u"] + f["r_in"] * 0.5, -0.5,
    )
    frac = solid_fraction(geometry.workplane, zone)
    return _finding(
        "topology.bay_open",
        frac < 0.1,
        f"entry window solid fraction {frac:.3f}",
        measured=frac,
        limit=0.1,
    )


@register_probe("topology.tunnel_open")
def tunnel_open(geometry: Geometry, form: PartForm) -> Finding:
    """The tie tunnel must be void along the extrusion axis (omega frame:
    tunnel centered at y=0, z in [0, tunnel_h])."""
    f = form.frame
    th, tw = f.get("tunnel_h"), f.get("tunnel_w")
    if th is None or tw is None:
        return _finding("topology.tunnel_open", False, "frame declares no tunnel")
    probe = channel_probe(
        [(-2.0, 0.0, th / 2.0), (form.width + 2.0, 0.0, th / 2.0)],
        d=0.8 * min(tw, th),
    )
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.tunnel_open",
        frac < 0.05,
        f"tunnel probe solid fraction {frac:.3f}",
        measured=frac,
        limit=0.05,
    )


@register_probe("topology.slots_open")
def slots_open(geometry: Geometry, form: PartForm) -> Finding:
    """Per comb slot: the cable channel along the width axis is void, and
    the throat is void from above (comb frame: x = u, y = width, z = v)."""
    f = form.frame
    count = int(f.get("slot_count", 0))
    if count == 0:
        return _finding("topology.slots_open", False, "frame declares no slots")
    cable_d = form.params.get("cable_d", f["cavity_r"])
    blocked = []
    for i in range(count):
        cx, cv = f[f"slot_cx_{i}"], f["cavity_cv"]
        run = channel_probe(
            [(cx, -2.0, cv), (cx, form.width + 2.0, cv)], d=cable_d * 0.8
        )
        run_frac = solid_fraction(geometry.workplane, run)
        tw = f["throat_w"]
        throat = box_probe(
            cx - tw * 0.25, form.width * 0.25, f["cavity_cv"] + f["cavity_r"] * 0.5,
            cx + tw * 0.25, form.width * 0.75, f["total_h"] + 2.0,
        )
        throat_frac = solid_fraction(geometry.workplane, throat)
        if run_frac > 0.05 or throat_frac > 0.35:
            blocked.append(f"slot {i} (run {run_frac:.2f}, throat {throat_frac:.2f})")
    return _finding(
        "topology.slots_open",
        not blocked,
        "all slots open" if not blocked else "blocked: " + "; ".join(blocked),
    )


@register_probe("topology.bores_open")
def bores_open(geometry: Geometry, form: PartForm) -> Finding:
    if not form.bores:
        return Finding(
            check="topology.bores_open",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no bores declared",
        )
    blocked = []
    for bore in form.bores:
        probe = channel_probe(bore.path(), d=bore.d * 0.8)
        frac = solid_fraction(geometry.workplane, probe)
        if frac > 0.05:
            blocked.append(f"{bore.name} (fill {frac:.2f})")
    return _finding(
        "topology.bores_open",
        not blocked,
        "all bores void" if not blocked else "blocked bores: " + ", ".join(blocked),
    )


@register_probe("topology.cutout_present")
def cutout_present(geometry: Geometry, form: PartForm) -> Finding:
    if not form.cutboxes:
        return Finding(
            check="topology.cutout_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no box cuts declared",
        )
    solid_ones = []
    for cut in form.cutboxes:
        b = cut.box
        # Probe a shrunken core of the cut so boundary fuzz doesn't count.
        mx, my, mz = (b.x1 - b.x0) * 0.2, (b.y1 - b.y0) * 0.2, (b.z1 - b.z0) * 0.2
        probe = box_probe(
            b.x0 + mx, b.y0 + my, b.z0 + mz, b.x1 - mx, b.y1 - my, b.z1 - mz
        )
        frac = solid_fraction(geometry.workplane, probe)
        if frac > 0.2:
            solid_ones.append(f"{cut.name} (fill {frac:.2f})")
    return _finding(
        "topology.cutout_present",
        not solid_ones,
        "all box cuts removed material"
        if not solid_ones
        else "cuts missing: " + ", ".join(solid_ones),
    )


@register_probe("topology.hex_field_present")
def hex_field_present(geometry: Geometry, form: PartForm) -> Finding:
    if not form.fields:
        return Finding(
            check="topology.hex_field_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no field declared (nothing to verify)",
        )
    import math

    empty = []
    # A declared field that produced ZERO cells is a failed field, not a
    # vacuous pass — every cell got vetoed by keepouts and the requested
    # feature simply does not exist on the part.
    for field in form.fields:
        if not field.centers and not field.polygons:
            empty.append(f"{field.pattern} (zero cells survived the keepouts)")
    fields = [f for f in form.fields if f.centers or f.polygons]
    # EVERY cell is probed (VF-4.1): a user's printed cassette arrived with
    # 1-3 random solid cells — a single-sample probe statistically never
    # lands on them. All per-cell probe boxes fuse into ONE compound, so
    # the whole-field verdict still costs a single boolean; the per-cell
    # pass then names the exact uncut cells (only runs when the fast
    # whole-field intersect says something is solid).
    import cadquery as cq

    for field in fields:
        cells: list[tuple[float, float, float]] = []  # (cu, cv, r)
        if field.centers:
            r = field.cell / math.sqrt(3.0) * 0.4
            cells = [(cu, cv, r) for cu, cv in field.centers]
        else:
            for poly in field.polygons:
                cu = sum(p[0] for p in poly) / len(poly)
                cv = sum(p[1] for p in poly) / len(poly)
                # Probe must fit INSIDE the cell — bound by the narrow bbox
                # dimension (a long slot is narrower than its area hints).
                bb_w = max(p[0] for p in poly) - min(p[0] for p in poly)
                bb_h = max(p[1] for p in poly) - min(p[1] for p in poly)
                cells.append((cu, cv, 0.3 * max(0.5, min(bb_w, bb_h))))

        def _cell_probe(cu: float, cv: float, r: float):
            # World-space probe box at the cell's mid-depth — works for
            # both horizontal and oriented (tilted-face) fields.
            wx, wy, wz = field.local_to_world(cu, cv, field.depth * 0.45)
            half = max(0.6, min(r, field.depth * 0.4))
            return box_probe(
                wx - r, wy - half, wz - half, wx + r, wy + half, wz + half)

        probes = [_cell_probe(cu, cv, r) for cu, cv, r in cells]
        compound = cq.Workplane(obj=cq.Compound.makeCompound(
            [s for p in probes for s in p.solids().vals()]))
        frac = solid_fraction(geometry.workplane, compound)
        # any single solid cell contributes ~1/N to the compound fraction
        if frac > 0.3 / max(1, len(cells)):
            uncut = []
            for i, probe in enumerate(probes):
                if solid_fraction(geometry.workplane, probe) > 0.3:
                    uncut.append(i)
            if uncut:
                empty.append(
                    f"{field.pattern}: {len(uncut)}/{len(cells)} cell(s) "
                    f"SOLID (indices {uncut[:6]}{'…' if len(uncut) > 6 else ''})")
            elif frac > 0.3:
                empty.append(f"{field.pattern} (fill {frac:.2f})")
    return _finding(
        "topology.hex_field_present",
        not empty,
        f"all fields cut real material (every cell probed)"
        if not empty else "uncut: " + ", ".join(empty),
    )


@register_probe("topology.ribs_present")
def ribs_present(geometry: Geometry, form: PartForm) -> Finding:
    if not form.ribs:
        return Finding(
            check="topology.ribs_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no ribs declared",
        )
    import math

    missing = []
    for rib in form.ribs:
        b = rib.box
        mx, my = (b.x1 - b.x0) * 0.2, (b.y1 - b.y0) * 0.2
        core = box_probe(
            b.x0 + mx, b.y0 + my, b.z0 + 0.3, b.x1 - mx, b.y1 - my, b.z1 - 0.3
        )
        # A rib may legitimately host declared Z-bores (a boss's pilot):
        # discount their area from the expected fill instead of failing.
        area = (b.x1 - b.x0 - 2 * mx) * (b.y1 - b.y0 - 2 * my)
        bored = sum(
            math.pi * (bore.d / 2.0) ** 2
            for bore in form.bores
            if bore.axis == "Z"
            and b.x0 <= bore.center[0] <= b.x1
            and b.y0 <= bore.center[1] <= b.y1
            and bore.span[1] > b.z0 and bore.span[0] < b.z1
        )
        expected = max(0.2, 1.0 - bored / max(area, 1e-9))
        frac = solid_fraction(geometry.workplane, core)
        if frac < expected * 0.85:
            missing.append(f"{rib.name} (fill {frac:.2f} < {expected * 0.85:.2f})")
    return _finding(
        "topology.ribs_present",
        not missing,
        "all ribs welded" if not missing else "missing ribs: " + ", ".join(missing),
    )


@register_probe("topology.bar_follows_arc")
def bar_follows_arc(geometry: Geometry, form: PartForm) -> Finding:
    """The swept bar must be solid along the WHOLE declared arc — sampled
    on the same three-point arc the compiler swept, so a sweep that
    silently failed (or drifted) cannot pass."""
    import math

    f = form.frame
    needed = ("sweep_span", "sweep_rise", "bar_d")
    if any(k not in f for k in needed):
        return _finding("topology.bar_follows_arc", False, "no sweep frame keys")
    span, rise, bar_d = (f[k] for k in needed)
    half = span / 2.0
    cz = (rise * rise - half * half) / (2.0 * rise)
    radius = rise - cz
    a0 = math.atan2(0.0 - cz, 0.0 - half)
    a1 = math.atan2(0.0 - cz, span - half)
    # walk the upper arc from end to end through the apex (pi/2)
    apex = math.pi / 2.0
    pts = []
    n = 10
    for i in range(n + 1):
        t = i / n
        # two symmetric halves via the apex to avoid wrap ambiguity
        ang = a0 + (apex - a0) * min(1.0, t * 2.0) if t <= 0.5 else (
            apex + (a1 - apex) * (t - 0.5) * 2.0
        )
        pts.append((half + radius * math.cos(ang), 0.0, cz + radius * math.sin(ang)))
    probe = channel_probe(pts, d=bar_d * 0.5)
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.bar_follows_arc",
        frac > 0.95,
        f"bar fill along the declared arc {frac:.3f}",
        measured=frac,
        limit=0.95,
    )


@register_probe("topology.pins_present")
def pins_present(geometry: Geometry, form: PartForm) -> Finding:
    """Every declared pin must be real material along its length."""
    if not form.pins:
        return _finding("topology.pins_present", True, "no pins declared")
    missing = []
    for pin in form.pins:
        sx, sy, sz = pin.start_point()
        ex, ey, ez = pin.end_point()
        # inset the probe 0.4 from each end along the axis
        t0, t1 = 0.4 / pin.length, 1.0 - 0.3 / pin.length
        a = (sx + (ex - sx) * t0, sy + (ey - sy) * t0, sz + (ez - sz) * t0)
        b = (sx + (ex - sx) * t1, sy + (ey - sy) * t1, sz + (ez - sz) * t1)
        probe = channel_probe([a, b], d=pin.d * 0.7)
        frac = solid_fraction(geometry.workplane, probe)
        if frac < 0.9:
            missing.append(f"{pin.name} (fill {frac:.2f})")
    return _finding(
        "topology.pins_present",
        not missing,
        "all pins welded" if not missing else "missing pins: " + ", ".join(missing),
    )


@register_probe("topology.arm_reaches_tip")
def arm_reaches_tip(geometry: Geometry, form: PartForm) -> Finding:
    """Every lofted arm must be solid at its TIP — a loft that welded at
    the root but never reached its declared end is a stub, not an arm."""
    if not form.lofts:
        return _finding("topology.arm_reaches_tip", True, "no lofted arms")
    problems = []
    for loft in form.lofts:
        cx, cy = loft.base_center
        tl, tw = loft.tip
        z_tip = loft.z0 + loft.length
        probe = box_probe(
            cx - tl * 0.3, cy - tw * 0.3, z_tip - 3.0,
            cx + tl * 0.3, cy + tw * 0.3, z_tip - 0.3,
        )
        frac = solid_fraction(geometry.workplane, probe)
        if frac < 0.6:
            problems.append(f"{loft.name} (tip fill {frac:.2f})")
    return _finding(
        "topology.arm_reaches_tip",
        not problems,
        "all arms solid to the tip" if not problems
        else "stub arms: " + ", ".join(problems),
    )


@register_probe("topology.seat_lips_present")
def seat_lips_present(geometry: Geometry, form: PartForm) -> Finding:
    """Every bearing seat's retaining lip ring must be real material —
    probed at four points around the ring the outer race will sit on."""
    seats = [k[: -len("_lip_r")] for k in form.frame if k.endswith("_lip_r")]
    if not seats:
        return _finding("topology.seat_lips_present", True, "no bearing seats")
    problems = []
    for name in seats:
        f = form.frame
        cx, cy, r = f[f"{name}_cx"], f[f"{name}_cy"], f[f"{name}_lip_r"]
        z0, z1 = f[f"{name}_lip_z0"] + 0.2, f[f"{name}_lip_z1"] - 0.2
        if z1 - z0 < 0.3:
            problems.append(f"{name}: lip too thin to probe")
            continue
        for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r)):
            probe = box_probe(cx + dx - 0.5, cy + dy - 0.5, z0,
                              cx + dx + 0.5, cy + dy + 0.5, z1)
            if solid_fraction(geometry.workplane, probe) < 0.9:
                problems.append(f"{name}: lip broken at ({dx:+.1f},{dy:+.1f})")
                break
    return _finding(
        "topology.seat_lips_present",
        not problems,
        "all bearing lips solid" if not problems else "; ".join(problems),
    )


@register_probe("topology.pockets_present")
def pockets_present(geometry: Geometry, form: PartForm) -> Finding:
    """Blind pockets (bores with a zero-overshoot end): void along the
    pocket, but the skin PAST the blind end must still be solid."""
    pockets = [b for b in form.bores if 0.0 in b.overshoot]
    if not pockets:
        return Finding(
            check="topology.pockets_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no blind pockets declared",
        )
    problems = []
    for pocket in pockets:
        probe = channel_probe(pocket.path(), d=pocket.d * 0.8)
        frac = solid_fraction(geometry.workplane, probe)
        if frac > 0.1:
            problems.append(f"{pocket.name} not cut (fill {frac:.2f})")
            continue
        # skin check: 0.4mm past the blind end must be material
        x, y, z = pocket.center
        if pocket.axis == "Z":
            blind_hi = pocket.overshoot[1] == 0.0
            z_probe = pocket.span[1] + 0.3 if blind_hi else pocket.span[0] - 0.3
            skin = box_probe(
                x - pocket.d * 0.2, y - pocket.d * 0.2, z_probe - 0.15,
                x + pocket.d * 0.2, y + pocket.d * 0.2, z_probe + 0.15,
            )
            if solid_fraction(geometry.workplane, skin) < 0.7:
                problems.append(f"{pocket.name} pierced through its skin")
    return _finding(
        "topology.pockets_present",
        not problems,
        "all pockets cut, skins intact" if not problems else "; ".join(problems),
    )


@register_probe("topology.rail_present")
def rail_present(geometry: Geometry, form: PartForm) -> Finding:
    """The dovetail rail core must be solid material along the body — a
    rail the compiler dropped (or a cut that severed it) is a missing
    mounting interface, not a style defect. Probes the rail's inner core
    only (frame keys rail_root_w / rail_v0 / rail_v1; part frame: x =
    extrusion axis, y = profile u, z = profile v)."""
    f = form.frame
    if "rail_v0" not in f or "rail_root_w" not in f:
        return Finding(
            check="topology.rail_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no rail declared",
        )
    half_u = 0.3 * f["rail_root_w"]
    zone = box_probe(
        form.width * 0.25, -half_u, f["rail_v0"] + 0.2,
        form.width * 0.75, half_u, f["rail_v1"] - 0.2,
    )
    frac = solid_fraction(geometry.workplane, zone)
    return _finding(
        "topology.rail_present",
        frac > 0.9,
        f"rail core solid fraction {frac:.3f}",
        measured=frac,
        limit=0.9,
    )


@register_probe("topology.exoskeleton_ribs_materialized")
def exoskeleton_ribs_materialized(geometry: Geometry, form: PartForm) -> Finding:
    """Bio-3: every rib graph edge must be REAL material on the compiled
    part. A small cube probe sits in the PROUD half of each capsule —
    centered 0.5*r outside the panel plane at the edge midpoint (fully
    inside the tube by construction), plus probes in 2-3 node spheres.
    An IR that was never welded (or a weld OCC dropped) fails here."""
    ir = form.exoskeleton
    if ir is None:
        return Finding(
            check="topology.exoskeleton_ribs_materialized",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no exoskeleton declared",
        )
    graph = ir.graph
    if not graph.edges:
        return _finding(
            "topology.exoskeleton_ribs_materialized", False,
            "exoskeleton declared but its graph has no edges",
        )
    radii = graph.edge_radius or tuple(ir.min_rib_d / 2.0 for _ in graph.edges)
    missing: list[str] = []
    worst = 1.0
    for (i, j), r in zip(graph.edges, radii):
        na, nb = graph.nodes[i], graph.nodes[j]
        mid = ((na[0] + nb[0]) / 2.0, (na[1] + nb[1]) / 2.0,
               (na[2] + nb[2]) / 2.0)
        # proud half: n is INTO the material, so -0.5*r is 0.5*r above the
        # surface; a cube of half-size 0.25*r there lies inside the tube.
        cx, cy, cz = ir.local_to_world(mid[0], mid[1], mid[2] - 0.5 * r)
        h = max(0.2, 0.25 * r)
        probe = box_probe(cx - h, cy - h, cz - h, cx + h, cy + h, cz + h)
        frac = solid_fraction(geometry.workplane, probe)
        worst = min(worst, frac)
        if frac < 0.5:
            missing.append(f"edge ({i},{j}) fill {frac:.2f}")
    # node blends: the roots plus a mid node must be spherical material
    node_idxs = list(graph.root_nodes[:2])
    mid_idx = len(graph.nodes) // 2
    if mid_idx not in node_idxs:
        node_idxs.append(mid_idx)
    blends = graph.node_blend_radius
    for idx in node_idxs:
        r = blends[idx] if idx < len(blends) else ir.min_rib_d / 2.0
        if r < 0.4:
            continue
        node = graph.nodes[idx]
        cx, cy, cz = ir.local_to_world(node[0], node[1], node[2] - 0.4 * r)
        h = max(0.2, 0.25 * r)
        probe = box_probe(cx - h, cy - h, cz - h, cx + h, cy + h, cz + h)
        frac = solid_fraction(geometry.workplane, probe)
        worst = min(worst, frac)
        if frac < 0.5:
            missing.append(f"node {idx} fill {frac:.2f}")
    return _finding(
        "topology.exoskeleton_ribs_materialized",
        not missing,
        f"all {len(graph.edges)} rib edges + {len(node_idxs)} node blends "
        "are solid material"
        if not missing else "ribs missing on the solid: " + ", ".join(missing[:6]),
        measured=worst,
        limit=0.5,
    )


@register_probe("topology.organic_windows_open")
def organic_windows_open(geometry: Geometry, form: PartForm) -> Finding:
    """Bio-3: every organic window polygon must have removed material —
    probed at the polygon centroid at mid-depth (through-cut semantics;
    probe sized by the NARROW bbox dimension, the hex_field_present
    lesson). A declared organic field with zero polygons is a failed
    field, not a vacuous pass."""
    organic = [f for f in form.fields if f.pattern == "organic"]
    if not organic:
        return Finding(
            check="topology.organic_windows_open",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no organic windows declared",
        )
    import math

    def _centroid_clearance(poly, cu, cv):
        """Min distance from the centroid to the polygon boundary — the
        probe must fit INSIDE the cell, and a clipped slender cell is much
        narrower at its centroid than its bbox hints."""
        best = math.inf
        for p, q in zip(poly, list(poly[1:]) + [poly[0]]):
            dx, dy = q[0] - p[0], q[1] - p[1]
            l2 = dx * dx + dy * dy
            if l2 < 1e-18:
                continue
            t = max(0.0, min(1.0, ((cu - p[0]) * dx + (cv - p[1]) * dy) / l2))
            best = min(best, math.hypot(cu - (p[0] + t * dx), cv - (p[1] + t * dy)))
        return best

    problems: list[str] = []
    worst = 0.0
    total = 0
    for f in organic:
        if not f.polygons:
            problems.append("organic field has zero window polygons")
            continue
        for k, poly in enumerate(f.polygons):
            total += 1
            cu = sum(p[0] for p in poly) / len(poly)
            cv = sum(p[1] for p in poly) / len(poly)
            # in-plane half-extent: a box of half-diagonal <= the centroid
            # clearance stays inside the (convex) cell by construction
            h = max(0.3, 0.65 * _centroid_clearance(poly, cu, cv))
            wx, wy, wz = f.local_to_world(cu, cv, f.depth * 0.45)
            zh = max(0.5, f.depth * 0.4)
            probe = box_probe(
                wx - h, wy - h, wz - zh, wx + h, wy + h, wz + zh
            )
            frac = solid_fraction(geometry.workplane, probe)
            worst = max(worst, frac)
            if frac > 0.1:
                problems.append(f"window {k} still solid (fill {frac:.2f})")
    return _finding(
        "topology.organic_windows_open",
        not problems,
        f"all {total} organic windows are open voids"
        if not problems else "; ".join(problems[:6]),
        measured=worst,
        limit=0.1,
    )


@register_probe("topology.payload_void_open")
def payload_void_open(geometry: Geometry, form: PartForm) -> Finding:
    """Wearable cuff (wave P2): the payload cylinder along X must be void,
    and the upward mouth window must be pierced through the clip wall —
    the flashlight really drops in from above."""
    f = form.frame
    if "payload_cv" not in f:
        # socket-variant cuffs carry no integrated clip — the ADAPTER's
        # build runs this probe for real (its frame has the keys)
        return _finding("topology.payload_void_open", True,
                        "no integrated payload clip on this form")
    p_cv, r_pi, r_po = f["payload_cv"], f["payload_r_inner"], f["payload_r_outer"]
    gap = f["payload_mouth_gap"]
    probe = channel_probe(
        [(-2.0, 0.0, p_cv), (form.width + 2.0, 0.0, p_cv)],
        d=2.0 * r_pi - 0.4,
    )
    frac_cyl = solid_fraction(geometry.workplane, probe)
    window = box_probe(
        form.width * 0.25, -gap * 0.3, p_cv + r_pi * 0.6,
        form.width * 0.75, gap * 0.3, p_cv + r_po + 1.0,
    )
    frac_win = solid_fraction(geometry.workplane, window)
    ok = frac_cyl < 0.05 and frac_win < 0.25
    return _finding(
        "topology.payload_void_open",
        ok,
        f"payload cylinder solid fraction {frac_cyl:.3f}, mouth window "
        f"{frac_win:.3f}",
        measured=max(frac_cyl, frac_win),
        limit=0.25,
    )


# -- vertical farm water probes (docs/VERTICAL_FARM_PACK.md) ------------------


@register_probe("topology.water_channel_open")
def water_channel_open(geometry: Geometry, form: PartForm) -> Finding:
    """The transient water path, verified on the solid: a probe swept just
    above the sloped floor along the sampled centerline must be void."""
    if not form.channels:
        return _finding("topology.water_channel_open", False,
                        "no water channel on this form")
    ch = form.channels[0]
    d = min(ch.width * 0.4, 6.0)
    # lift the swept cylinder so its underside clears the sloped floor
    probe = channel_probe(ch.centerline(lift=d / 2.0 + 0.8), d=d)
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.water_channel_open",
        frac < 0.05,
        f"water path solid fraction {frac:.3f} along the sampled centerline",
        measured=frac,
        limit=0.05,
    )


@register_probe("topology.water_channel_floor_solid")
def water_channel_floor_solid(geometry: Geometry, form: PartForm) -> Finding:
    """The same centerline mirrored below the floor must be solid — the
    channel never leaks into the body or a hidden cavity."""
    if not form.channels:
        return _finding("topology.water_channel_floor_solid", False,
                        "no water channel on this form")
    ch = form.channels[0]
    probe = channel_probe(ch.centerline(lift=-1.2), d=2.0)
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.water_channel_floor_solid",
        frac > 0.95,
        f"floor solid fraction {frac:.3f} just below the channel",
        measured=frac,
        limit=0.95,
    )


@register_probe("topology.contact_window_present")
def contact_window_present(geometry: Geometry, form: PartForm) -> Finding:
    """The cassette's lowered contact slab is deliberately MESHED: the
    probe must find real material in its box (the slab exists) but far
    from solid (the mesh pierces it — water passes, coco is held). A solid
    slab is a dam; a missing slab never touches pulse water."""
    slabs = [r for r in form.ribs if "window" in r.name]
    if not slabs:
        return _finding("topology.contact_window_present", False,
                        "no contact window slab declared on this form")
    b = slabs[0].box
    mx, my = (b.x1 - b.x0) * 0.15, (b.y1 - b.y0) * 0.15
    probe = box_probe(b.x0 + mx, b.y0 + my, b.z0 + 0.2,
                      b.x1 - mx, b.y1 - my, min(b.z1, 0.0) - 0.05)
    frac = solid_fraction(geometry.workplane, probe)
    ok = 0.15 <= frac <= 0.92
    return _finding(
        "topology.contact_window_present",
        ok,
        f"contact slab solid fraction {frac:.2f} — "
        + ("meshed material, as designed" if ok
           else "missing" if frac < 0.15 else "SOLID (a dam, not a window)"),
        measured=frac,
        limit=0.92,
    )


@register_probe("topology.fluid_path_open")
def fluid_path_open(geometry: Geometry, form: PartForm) -> Finding:
    """The fluid adapter's whole water path, probed on the solid: every
    hose bore is void end-to-end and (on the collector) the tray run is
    void above its sloped floor. A blocked path is a plug, not a port."""
    probes: list[tuple[str, object]] = []
    for bore in form.bores:
        if "hose" in bore.name or "drain" in bore.name:
            probes.append((bore.name, channel_probe(bore.path(), d=bore.d * 0.7)))
    for ch in form.channels:
        d = min(ch.width * 0.4, 6.0)
        probes.append((ch.name, channel_probe(ch.centerline(lift=d / 2.0 + 0.8), d=d)))
    if not probes:
        return _finding("topology.fluid_path_open", False,
                        "no fluid path declared on this form")
    blocked = []
    for name, probe in probes:
        frac = solid_fraction(geometry.workplane, probe)
        if frac > 0.05:
            blocked.append(f"{name} solid fraction {frac:.2f}")
    return _finding(
        "topology.fluid_path_open",
        not blocked,
        f"{len(probes)} fluid path leg(s) void on the solid"
        if not blocked else "; ".join(blocked),
        measured=None if not blocked else 0.05,
    )
