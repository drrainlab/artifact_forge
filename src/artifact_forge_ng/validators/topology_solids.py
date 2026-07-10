"""Solid/cavity/void topology probes — connectivity, mouths, lips, bays,
tunnels, voids on the compiled geometry.
"""
from __future__ import annotations

from ..cad.geometry import Geometry
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from .probes import register_probe
from .topology_common import _finding, box_probe, channel_probe, solid_fraction


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
