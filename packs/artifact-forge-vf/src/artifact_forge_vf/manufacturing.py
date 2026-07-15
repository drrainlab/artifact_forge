"""Vertical-farm manufacturing probes — wet-zone printability and
washability rules probed on the compiled solid."""
from __future__ import annotations

import math

from artifact_forge_ng.cad.geometry import Geometry
from artifact_forge_ng.cad.probes import box_probe, channel_probe, solid_fraction
from artifact_forge_ng.core.findings import Finding, Level, Status
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.validators.probes import register_probe
from artifact_forge_ng.validators.manufacturing import _finding

BRUSH_D = 8.0
BRUSH_MIN_CHANNEL_W = 10.0
CREVICE_MIN_OPENING = 2.0
CAP_ROOF_OVERHANG_MAX = 5.0  # mm — a printable one-sided ledge, not a cantilever


@register_probe("manufacturing.brush_access_to_water_channel")
def brush_access_to_water_channel(geometry: Geometry, form: PartForm) -> Finding:
    if not form.channels:
        return _finding(
            "manufacturing.brush_access_to_water_channel", Status.PASS,
            "not applicable — no water channel on this part",
        )
    from artifact_forge_ng.cad.probes import channel_probe, solid_fraction

    ch = form.channels[0]
    if ch.width < BRUSH_MIN_CHANNEL_W:
        return _finding(
            "manufacturing.brush_access_to_water_channel", Status.FAIL,
            f"channel {ch.width:g} narrower than a {BRUSH_MIN_CHANNEL_W:g} brush",
            measured=ch.width, limit=BRUSH_MIN_CHANNEL_W,
        )
    top = form.frame.get("channel_top_z", ch.z_top)
    worst = 0.0
    for x, y, floor_z in ch.centerline(lift=1.0):
        probe = channel_probe([(x, y, floor_z), (x, y, top + 14.0)], d=BRUSH_D)
        worst = max(worst, solid_fraction(geometry.workplane, probe))
    ok = worst < 0.05
    return _finding(
        "manufacturing.brush_access_to_water_channel",
        Status.PASS if ok else Status.FAIL,
        f"vertical brush path worst solid fraction {worst:.3f} along the run"
        + ("" if ok else " — something roofs the channel"),
        measured=worst, limit=0.05,
    )


#: The flush water path where a downward through-hole is a leak (VF-9). The
#: collector drain is a BORE (not a cutbox) and lives outside these regions, so
#: it is the sanctioned exception by construction.
FLUSH_WET_REGION_NAMES = ("water_channel", "lap_receiver", "lap_lip")

@register_probe("manufacturing.no_through_holes_in_wet_lap_zone")
def no_through_holes_in_wet_lap_zone(geometry: Geometry, form: PartForm) -> Finding:
    """VF-9 invariant: NO cutbox with an open bottom may sit under the active
    flush water path (the channel + lap seam) — that is a leak straight down.
    The only sanctioned downward exit is the collector drain (a bore, outside
    these regions). n/a on parts with no flush water path."""
    from artifact_forge_ng.product.archetype import RegionRole
    check = "manufacturing.no_through_holes_in_wet_lap_zone"
    wet = [r for r in form.regions
           if r.role is RegionRole.TRANSIENT_WATER_PATH
           and r.name in FLUSH_WET_REGION_NAMES]
    if not wet:
        return _finding(check, Status.PASS, "not applicable — no flush water path")

    def _overlaps(b, w) -> bool:
        return (b.x0 <= w.x1 and w.x0 <= b.x1 and b.y0 <= w.y1
                and w.y0 <= b.y1 and b.z0 <= w.z1 and w.z0 <= b.z1)

    offenders = []
    for cut in form.cutboxes:
        b = cut.box
        if b.z0 > 0.05:
            continue  # closed bottom — no downward path
        if "drain" in cut.name:
            continue  # the sanctioned collector drain
        if any(_overlaps(b, w.box) for w in wet):
            offenders.append(
                f"cut {cut.name!r} is open-bottom (z0={b.z0:g}) under the water path")
    ok = not offenders
    return _finding(
        check, Status.PASS if ok else Status.FAIL,
        "no through hole under the active water path — nothing leaks straight down"
        if ok else "; ".join(offenders),
    )

@register_probe("manufacturing.no_hidden_wet_crevices")
def no_hidden_wet_crevices(geometry: Geometry, form: PartForm) -> Finding:
    from artifact_forge_ng.product.archetype import RegionRole

    wet = [r for r in form.regions if r.role is RegionRole.TRANSIENT_WATER_PATH]
    if not wet:
        return _finding(
            "manufacturing.no_hidden_wet_crevices", Status.PASS,
            "not applicable — no wet regions on this part",
        )

    def _overlaps(b, w) -> bool:
        return (b.x0 <= w.x1 and w.x0 <= b.x1 and b.y0 <= w.y1
                and w.y0 <= b.y1 and b.z0 <= w.z1 and w.z0 <= b.z1)

    offenders: list[str] = []
    for cut in form.cutboxes:
        b = cut.box
        if not any(_overlaps(b, w.box) for w in wet):
            continue
        # VF-9: the floored lap lip-seat is a WIDE, open-top, shallow step (its
        # narrowest dim is the vertical depth, not a crevice mouth) — a brush
        # reaches it from above and the neighbour's lip lifts straight out. Not
        # a hidden crevice as long as the lateral footprint is brush-wide.
        if ("lap_receiver" in cut.name
                and (b.x1 - b.x0) >= CREVICE_MIN_OPENING
                and (b.y1 - b.y0) >= CREVICE_MIN_OPENING):
            continue
        narrowest = min(b.x1 - b.x0, b.y1 - b.y0, b.z1 - b.z0)
        if narrowest < CREVICE_MIN_OPENING:
            offenders.append(
                f"cut {cut.name!r} opens only {narrowest:.2f} in the wet path")
    for bore in form.bores:
        x, y, z = bore.center
        r = bore.d / 2.0
        from artifact_forge_ng.form.regions import Box3

        lo, hi = bore.span
        if bore.axis == "Z":
            bbox = Box3(x - r, y - r, lo, x + r, y + r, hi)
        elif bore.axis == "Y":
            bbox = Box3(x - r, lo, z - r, x + r, hi, z + r)
        else:
            bbox = Box3(lo, y - r, z - r, hi, y + r, z + r)
        if bore.d < CREVICE_MIN_OPENING and any(_overlaps(bbox, w.box) for w in wet):
            offenders.append(f"bore {bore.name!r} d={bore.d:g} in the wet path")
    ok = not offenders
    return _finding(
        "manufacturing.no_hidden_wet_crevices",
        Status.PASS if ok else Status.FAIL,
        "every wet-path opening admits a brush"
        if ok else "; ".join(offenders),
        measured=None if ok else CREVICE_MIN_OPENING,
        suggestion="" if ok else "widen the opening past 2 mm or move it out of the wet path",
    )

@register_probe("manufacturing.no_unwashable_snap_pockets")
def no_unwashable_snap_pockets(geometry: Geometry, form: PartForm) -> Finding:
    windows = [c for c in form.cutboxes if "snap_window" in c.name]
    if not windows:
        return _finding(
            "manufacturing.no_unwashable_snap_pockets", Status.PASS,
            "not applicable — no snap windows on this part",
        )
    from artifact_forge_ng.cad.probes import box_probe, solid_fraction

    blocked: list[str] = []
    for win in windows:
        b = win.box
        probe = box_probe(
            b.x0 + 0.2, b.y0 + 0.2, b.z0 + 0.2,
            b.x1 - 0.2, b.y1 - 0.2, b.z1 - 0.2,
        )
        frac = solid_fraction(geometry.workplane, probe)
        if frac > 0.05:
            blocked.append(f"{win.name!r} solid fraction {frac:.2f}")
    ok = not blocked
    return _finding(
        "manufacturing.no_unwashable_snap_pockets",
        Status.PASS if ok else Status.FAIL,
        f"{len(windows)} snap window(s) verified void through the wall"
        if ok else "; ".join(blocked),
    )


# -- VF-4.1 printability: bottom pockets and horizontal bores -------------------

#: FDM bridging bands for a flat ceiling over a bottom-entered pocket,
#: printing as-modeled (bottom down): short bridges print clean, medium
#: ones sag cosmetically, long ones need support.
CEILING_BRIDGE_OK = 25.0
CEILING_BRIDGE_FAIL = 35.0
#: A horizontal circular bore prints acceptably up to this diameter; above
#: it the round ceiling sags — use a teardrop roof or a vertical bore.

@register_probe("manufacturing.supportless_lightweight_windows_ok")
def supportless_lightweight_windows_ok(geometry: Geometry, form: PartForm) -> Finding:
    """No blind bottom pocket may hide a support-critical flat ceiling
    (VF-4.1). Every cutbox entered from BELOW whose footprint could bridge
    is probed ON THE SOLID just above its ceiling: void above (a through
    opening into another cavity — the open-skeleton case) passes; material
    above is a real bridge, graded by span. n/a fast-path: parts without
    bottom-entered pockets never touch the geometry."""
    check = "manufacturing.supportless_lightweight_windows_ok"
    if form.print_orientation != "as_modeled":
        return _finding(check, Status.PASS,
                        "n/a — sideprint part; ceilings print vertical")
    top = form.width or 0.0
    candidates = [
        c for c in form.cutboxes
        if c.box.z0 <= 0.05 and c.box.z1 < top - 0.05
        and min(c.box.x1 - c.box.x0, c.box.y1 - c.box.y0) > CEILING_BRIDGE_OK
    ]
    if not candidates:
        return _finding(check, Status.PASS,
                        "no bottom-entered pockets that could bridge — n/a")
    from artifact_forge_ng.cad.probes import box_probe, solid_fraction

    problems: list[str] = []
    worst = 0.0
    for cut in candidates:
        b = cut.box
        probe = box_probe(b.x0 + 0.3, b.y0 + 0.3, b.z1 + 0.2,
                          b.x1 - 0.3, b.y1 - 0.3, b.z1 + 1.2)
        if solid_fraction(geometry.workplane, probe) <= 0.5:
            continue  # through into another cavity — no ceiling, no bridge
        span = min(b.x1 - b.x0, b.y1 - b.y0)
        worst = max(worst, span)
        if span > CEILING_BRIDGE_FAIL:
            problems.append(
                f"pocket {cut.name!r} bridges a {span:.0f} flat ceiling "
                f"(> {CEILING_BRIDGE_FAIL:g}) — make it through, vaulted or a "
                "rib skeleton")
    if problems:
        return _finding(check, Status.FAIL, "; ".join(problems),
                        measured=worst, limit=CEILING_BRIDGE_FAIL,
                        suggestion="through-open the pocket or vault its roof")
    if worst > 0.0:
        return _finding(
            check, Status.WARN,
            f"flat ceiling bridges up to {worst:.0f} over bottom pockets — "
            "prints, expect sag", measured=worst, limit=CEILING_BRIDGE_FAIL)
    return _finding(check, Status.PASS,
                    "every wide bottom pocket is through-open — no ceiling "
                    "bridges, supportless by construction")

@register_probe("manufacturing.cap_supportless_verified")
def cap_supportless_verified(geometry: Geometry, form: PartForm) -> Finding:
    """VF-9 Part B: closes the VF-7c blind spot (manufacturing.overhang never
    modelled the inlet cap's saddle-slot roof, so the old flat cantilever passed
    only because it flipped for print). The cap must print support-free
    AS-MODELED: the rest-ledge roof over the open saddle slot must be a SHORT
    one-sided overhang (<= CAP_ROOF_OVERHANG_MAX), not a deep floating
    cantilever, and a nose column must reach the bed to anchor the roof over the
    channel. n/a on parts without a cap saddle slot + hose bore."""
    check = "manufacturing.cap_supportless_verified"
    slots = [c for c in form.cutboxes if "saddle_slot" in c.name]
    has_hose = any("hose" in b.name for b in form.bores)
    if not slots or not has_hose:
        return _finding(check, Status.PASS, "not an inlet cap — n/a")
    slot = slots[0].box
    overhang = slot.y1 - slot.y0  # inboard reach of the rest ledge over open air
    nose = [r for r in form.ribs if "nose" in r.name and r.box.z0 <= 0.05]
    problems: list[str] = []
    if overhang > CAP_ROOF_OVERHANG_MAX + 1e-6:
        problems.append(
            f"saddle-slot roof overhangs {overhang:.1f} inboard over open air "
            f"(> {CAP_ROOF_OVERHANG_MAX:g}) — a floating cantilever; shorten "
            "hook_reach or anchor the inboard side")
    if not nose:
        problems.append(
            "no nose column reaches the bed to anchor the roof over the channel")
    ok = not problems
    return _finding(
        check, Status.PASS if ok else Status.FAIL,
        f"support-free L-hook: {overhang:.1f}mm rest ledge, the nose column "
        "anchors the roof — nothing floats as-modeled"
        if ok else "; ".join(problems),
        measured=overhang, limit=CAP_ROOF_OVERHANG_MAX)
