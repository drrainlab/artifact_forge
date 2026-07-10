"""Fastener and channel topology probes — screw holes, countersinks,
wiring channels, comb slots, bores.
"""
from __future__ import annotations

from ..cad.geometry import Geometry
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from .probes import register_probe
from .topology_common import _finding, box_probe, channel_probe, solid_fraction


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
