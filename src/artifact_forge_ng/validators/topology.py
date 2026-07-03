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
    for field in fields:
        if field.centers:
            r = field.cell / math.sqrt(3.0) * 0.4
            cu, cv = field.centers[len(field.centers) // 2]
        else:
            poly = field.polygons[len(field.polygons) // 2]
            cu = sum(p[0] for p in poly) / len(poly)
            cv = sum(p[1] for p in poly) / len(poly)
            # Probe must fit INSIDE the cell — bound by the narrow bbox
            # dimension (a long slot is much narrower than its area hints).
            bb_w = max(p[0] for p in poly) - min(p[0] for p in poly)
            bb_h = max(p[1] for p in poly) - min(p[1] for p in poly)
            r = 0.3 * max(0.5, min(bb_w, bb_h))
        # World-space probe box at the cell's mid-depth — works for both
        # horizontal and oriented (tilted-face) fields.
        wx, wy, wz = field.local_to_world(cu, cv, field.depth * 0.45)
        half = max(0.6, min(r, field.depth * 0.4))
        probe = box_probe(
            wx - r, wy - half, wz - half, wx + r, wy + half, wz + half
        )
        frac = solid_fraction(geometry.workplane, probe)
        if frac > 0.3:
            empty.append(f"{field.pattern} (fill {frac:.2f})")
    return _finding(
        "topology.hex_field_present",
        not empty,
        "all fields cut real material" if not empty else "uncut: " + ", ".join(empty),
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
