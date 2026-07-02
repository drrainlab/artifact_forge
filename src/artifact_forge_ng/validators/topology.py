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
    hook_ok = form.frame["hook_top_v"] <= plate.z_bottom + 0.1
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


@register_probe("topology.hex_field_present")
def hex_field_present(geometry: Geometry, form: PartForm) -> Finding:
    fields = [f for f in form.fields if f.centers]
    if not fields:
        return Finding(
            check="topology.hex_field_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no field declared (nothing to verify)",
        )
    import math

    field = fields[0]
    r = field.cell / math.sqrt(3.0) * 0.4
    cu, cv = field.centers[len(field.centers) // 2]
    probe = box_probe(
        cu - r, cv - r, field.plane_z - field.depth, cu + r, cv + r, field.plane_z
    )
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.hex_field_present",
        frac < 0.3,
        f"sampled hex cell solid fraction {frac:.2f}",
        measured=frac,
        limit=0.3,
    )
