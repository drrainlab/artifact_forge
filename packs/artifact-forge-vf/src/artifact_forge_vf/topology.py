"""Water-path topology probes — water channels, cassette contact windows,
fluid paths (vertical-farm domain).
"""
from __future__ import annotations

from artifact_forge_ng.cad.geometry import Geometry
from artifact_forge_ng.core.findings import Finding, Level, Status
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.validators.probes import register_probe
from artifact_forge_ng.validators.topology_common import _finding, box_probe, channel_probe, solid_fraction


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
    """The fluid adapter's whole water path, probed on the solid. VF-9.2: a
    part with a STEPPED tube socket (the inlet cap, `hose_socket_depth` in the
    frame) is probed as ONE composite polyline — down the socket, through the
    orifice, down the chamber and along the open chute past the tip — never
    demanding void below the socket's intentional stop shoulder at the socket
    diameter, and catching a plugged chamber/chute that per-bore probes miss.
    Plain hose/drain ports keep the end-to-end bore probe; the collector's
    tray run is probed above its sloped floor."""
    probes: list[tuple[str, object]] = []
    f = form.frame
    if "hose_socket_depth" in f:
        d = f.get("drip_orifice_d", 5.0) * 0.7
        lift = d / 2.0 + 0.6
        y_sock = f.get("hose_socket_y", 0.0)
        z_top = f.get("channel_top_z", 22.0) + 0.5
        z_run = f["channel_floor_z_outlet"] + lift
        tip_y = f.get("chute_tip_y", 0.0)
        path = [(0.0, y_sock, z_top), (0.0, y_sock, z_run),
                (0.0, tip_y - 1.0, z_run)]
        probes.append(("cap_water_path", channel_probe(path, d=d)))
    else:
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
