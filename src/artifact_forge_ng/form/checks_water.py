"""IR checks for the vertical farm water rail — the transient water
contract measured on the Form IR: the channel slopes monotonically to a
guaranteed exit, nothing in the wet path can hold standing water, the
overflow lip stays sharp over a real air gap, the cassette seat matches the
shared envelope, and the module's dry interfaces (tongue/groove, aluminum
profile slots) stay out of the water. Self-registers on import.

Frame-key contract (published by the water rail ops, read here and by the
assembly joints — the machine-checked half of the Cassette Interface
Standard): channel_* (center_x, w, bottom_r, top_z, y_inlet, y_outlet,
floor_z_inlet, floor_z_outlet, slope_deg, floor_margin), lip_* / air_gap,
seat_* (u0, v0, u1, v1, floor_z, depth, clearance), tongue_* / groove_* /
edge_clearance, profile_* and module_pitch.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..product.archetype import RegionRole
from ..validators.probes import register_probe
from .part import PartForm
from .regions import Box3

#: The transient-pulse hydraulics bands (docs/VERTICAL_FARM_PACK.md).
SLOPE_BAND = (1.0, 1.5)  # degrees
CHANNEL_W_BAND = (12.0, 20.0)
BOTTOM_R_BAND = (0.8, 2.0)
FLOOR_MARGIN_MIN = 2.0  # material below the deepest floor point
AIR_GAP_MIN = 1.2
LIP_R_MAX = 0.5
LIP_MIN_T = 0.4  # the relief must leave at least this much lip material
SEAT_CLEARANCE_BAND = (0.5, 1.0)
TG_SIDE_CLEARANCE_BAND = (0.3, 0.5)  # tongue/groove per-side
TG_BOTTOM_MARGIN = 0.3  # tongue never bottoms in the groove


def _finding(check: str, ok: bool, message: str, *, measured: float | None = None,
             limit: float | None = None, suggestion: str = "") -> Finding:
    return Finding(
        check=check, status=Status.PASS if ok else Status.FAIL, level=Level.FORM,
        message=message, critical=not ok, measured=measured, limit=limit,
        suggestion=suggestion,
    )


def _boxes_overlap(a: Box3, b: Box3) -> bool:
    return (
        a.x0 <= b.x1 and b.x0 <= a.x1
        and a.y0 <= b.y1 and b.y0 <= a.y1
        and a.z0 <= b.z1 and b.z0 <= a.z1
    )


def _wet_regions(form: PartForm):
    return [r for r in form.regions if r.role is RegionRole.TRANSIENT_WATER_PATH]


def check_water_channel_slope_ok(form: PartForm) -> Finding:
    if not form.channels:
        return _finding("form.water_channel_slope_ok", False,
                        "no water channel declared on this part")
    ch = form.channels[0]
    slope = ch.slope_deg
    deepens = ch.depth_end > ch.depth_start + 1e-6
    declared = form.frame.get("channel_slope_deg")
    consistent = declared is None or abs(declared - slope) <= 0.02
    # band edges are LEGAL: the tan/atan round-trip through the channel
    # depths loses ~1e-15 — never fail a boundary value on float dust
    in_band = SLOPE_BAND[0] - 1e-6 <= slope <= SLOPE_BAND[1] + 1e-6
    ok = in_band and deepens and consistent
    problems: list[str] = []
    if not deepens:
        problems.append("floor does not fall toward the outlet")
    if not in_band:
        problems.append(f"slope {slope:.2f} deg outside {SLOPE_BAND[0]}..{SLOPE_BAND[1]}")
    if not consistent:
        problems.append(f"frame declares {declared:g} deg but the IR measures {slope:.2f}")
    return _finding(
        "form.water_channel_slope_ok", ok,
        f"channel falls {slope:.2f} deg toward the outlet, monotonic by construction"
        if ok else "; ".join(problems),
        measured=slope, limit=SLOPE_BAND[1],
        suggestion="" if ok else "set slope_deg in 1.0..1.5 with the outlet the deep end",
    )


def check_water_channel_dims_ok(form: PartForm) -> Finding:
    if not form.channels:
        return _finding("form.water_channel_dims_ok", False,
                        "no water channel declared on this part")
    ch = form.channels[0]
    f = form.frame
    problems: list[str] = []
    if not (CHANNEL_W_BAND[0] <= ch.width <= CHANNEL_W_BAND[1]):
        problems.append(f"width {ch.width:g} outside {CHANNEL_W_BAND[0]}..{CHANNEL_W_BAND[1]}")
    if not (BOTTOM_R_BAND[0] <= ch.bottom_r <= BOTTOM_R_BAND[1]):
        problems.append(f"bottom radius {ch.bottom_r:g} outside {BOTTOM_R_BAND[0]}..{BOTTOM_R_BAND[1]}")
    body_y0, body_y1 = f.get("rail_y0"), f.get("rail_y1")
    if body_y0 is None or body_y1 is None:
        problems.append("no rail_y0/rail_y1 frame keys — cannot prove the exit")
    else:
        lo, hi = min(ch.y0, ch.y1), max(ch.y0, ch.y1)
        if lo > body_y0 + 0.01 or hi < body_y1 - 0.01:
            problems.append(
                f"channel run {lo:g}..{hi:g} does not span both faces "
                f"{body_y0:g}..{body_y1:g} — no guaranteed exit")
    margin = f.get("channel_floor_margin")
    if margin is None:
        problems.append("no channel_floor_margin frame key")
    elif margin < FLOOR_MARGIN_MIN:
        problems.append(
            f"only {margin:.1f} material under the deepest floor point "
            f"(needs >= {FLOOR_MARGIN_MIN:g})")
    return _finding(
        "form.water_channel_dims_ok", not problems,
        "channel dims in band, spans both faces, floor carried by real material"
        if not problems else "; ".join(problems),
        measured=ch.width, limit=CHANNEL_W_BAND[1],
    )


def check_no_standing_water_ir(form: PartForm) -> Finding:
    """Nothing in a wet region may hold water: no blind bore, and no box
    cut whose floor hangs between the body bottom and the channel entry
    plane (an open-bottomed relief and the seat-level corridors are fine;
    a sump pocket sunk into the channel floor is not)."""
    wet = _wet_regions(form)
    if not wet:
        return _finding("form.no_standing_water_ir", False,
                        "no transient_water_path regions declared — nothing to protect")
    top = form.frame.get("channel_top_z")
    offenders: list[str] = []
    for bore in form.bores:
        blind = bore.overshoot[0] <= 0.0 or bore.overshoot[1] <= 0.0
        if not blind:
            continue
        x, y, z = bore.center
        r = bore.d / 2.0
        lo, hi = bore.span
        if bore.axis == "Z":
            bbox = Box3(x - r, y - r, lo, x + r, y + r, hi)
        elif bore.axis == "Y":
            bbox = Box3(x - r, lo, z - r, x + r, hi, z + r)
        else:
            bbox = Box3(lo, y - r, z - r, hi, y + r, z + r)
        if any(_boxes_overlap(bbox, w.box) for w in wet):
            offenders.append(f"blind bore {bore.name!r} in the wet path")
    for cut in form.cutboxes:
        b = cut.box
        if b.z0 <= 0.05:
            continue  # open to the underside — cannot pool
        if top is not None and b.z0 >= top - 0.05:
            continue  # floor at/above the channel entry plane — a dry step
        if any(_boxes_overlap(b, w.box) for w in wet):
            offenders.append(f"pocket {cut.name!r} floors at z={b.z0:g} inside the wet path")
    return _finding(
        "form.no_standing_water_ir", not offenders,
        "no blind pocket can hold water in the wet path"
        if not offenders else "; ".join(offenders),
        suggestion="" if not offenders else "open the pocket to the underside or move it out of the wet path",
    )


def check_overflow_lip_geometry_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("lip_z", "lip_h", "air_gap", "lip_r_assumed")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.overflow_lip_geometry_ok", False,
                        f"no overflow lip frame keys: {', '.join(missing)}")
    problems: list[str] = []
    if f["air_gap"] < AIR_GAP_MIN:
        problems.append(f"air gap {f['air_gap']:g} < {AIR_GAP_MIN:g}")
    if f["lip_r_assumed"] > LIP_R_MAX:
        problems.append(f"lip radius {f['lip_r_assumed']:g} > {LIP_R_MAX:g}")
    lip_region = form.region("overflow_lip")
    receiver = form.region("drip_receiver")
    relief = None
    if receiver is not None:
        for cut in form.cutboxes:
            if _boxes_overlap(cut.box, receiver.box):
                relief = cut
                break
    if receiver is None:
        problems.append("no drip_receiver region")
    if relief is None:
        problems.append("no relief cut under the lip — water runs down the outer wall")
    else:
        b = relief.box
        if b.z0 > 0.0:
            problems.append(f"relief {relief.name!r} has a blind floor at z={b.z0:g}")
        if b.z1 > f["lip_z"] - LIP_MIN_T:
            problems.append(
                f"relief top {b.z1:g} eats the lip (must stay <= {f['lip_z'] - LIP_MIN_T:g})")
        if (b.y1 - b.y0) < f["air_gap"] - 0.01:
            problems.append(
                f"relief depth {b.y1 - b.y0:g} < declared air gap {f['air_gap']:g}")
    if lip_region is not None:
        for blend in form.blends:
            if _boxes_overlap(blend.zone, lip_region.box):
                problems.append(
                    f"blend zone r={blend.radius:g} touches the lip — the drip edge must stay sharp")
    return _finding(
        "form.overflow_lip_geometry_ok", not problems,
        f"sharp lip over a {f['air_gap']:g} air gap — droplets detach"
        if not problems else "; ".join(problems),
        measured=f["air_gap"], limit=AIR_GAP_MIN,
    )


def check_no_secondary_water_channel(form: PartForm) -> Finding:
    if form.channels:
        problems: list[str] = []
        if len(form.channels) != 1:
            problems.append(f"{len(form.channels)} water channels declared — the rail owns exactly one")
        receiver = form.region("drip_receiver")
        if receiver is not None:
            for cut in form.cutboxes:
                b = cut.box
                if b.z0 > 0.05 and _boxes_overlap(b, receiver.box):
                    problems.append(
                        f"pocket {cut.name!r} would turn the drip receiver into a second trough")
        return _finding(
            "form.no_secondary_water_channel", not problems,
            "one water path; the drip receiver stays open"
            if not problems else "; ".join(problems),
        )
    if form.fields:
        problems = []
        if len(form.fields) != 1:
            problems.append(f"{len(form.fields)} floor fields — the mesh floor is exactly one grid")
        fld = form.fields[0]
        if fld.pattern != "slots":
            problems.append(f"floor field pattern {fld.pattern!r} is not an orthogonal slot grid")
        if fld.mapping != "planar" or fld.origin is not None or abs(fld.tilt_deg) > 1e-6:
            problems.append("floor field is not flat — a shaped mesh directs flow")
        return _finding(
            "form.no_secondary_water_channel", not problems,
            "one flat orthogonal mesh — holds coco, does not channel water"
            if not problems else "; ".join(problems),
        )
    return _finding("form.no_secondary_water_channel", False,
                    "no channel and no floor field — nothing to measure")


def check_cassette_seat_fit_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("seat_u0", "seat_v0", "seat_u1", "seat_v1",
            "seat_floor_z", "seat_clearance", "channel_top_z")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.cassette_seat_fit_ok", False,
                        f"no seat frame keys: {', '.join(missing)}")
    cassette_l = form.params.get("cassette_l")
    cassette_w = form.params.get("cassette_w")
    if cassette_l is None or cassette_w is None:
        return _finding("form.cassette_seat_fit_ok", False,
                        "no cassette_l/cassette_w params — the shared envelope is unbound")
    c = f["seat_clearance"]
    problems: list[str] = []
    if not (SEAT_CLEARANCE_BAND[0] <= c <= SEAT_CLEARANCE_BAND[1]):
        problems.append(
            f"seat clearance {c:g} outside {SEAT_CLEARANCE_BAND[0]}..{SEAT_CLEARANCE_BAND[1]}")
    want_u = cassette_l + 2.0 * c
    want_v = cassette_w + 2.0 * c
    got_u = f["seat_u1"] - f["seat_u0"]
    got_v = f["seat_v1"] - f["seat_v0"]
    if abs(got_u - want_u) > 0.1:
        problems.append(f"seat X extent {got_u:.2f} != cassette {cassette_l:g} + 2x{c:g}")
    if abs(got_v - want_v) > 0.1:
        problems.append(f"seat Y extent {got_v:.2f} != cassette {cassette_w:g} + 2x{c:g}")
    if abs(f["seat_floor_z"] - f["channel_top_z"]) > 0.05:
        problems.append(
            f"seat floor {f['seat_floor_z']:g} is not the channel entry plane "
            f"{f['channel_top_z']:g} — the cassette would dam or float over the water")
    return _finding(
        "form.cassette_seat_fit_ok", not problems,
        f"seat fits the shared cassette envelope with {c:g} clearance"
        if not problems else "; ".join(problems),
        measured=c, limit=SEAT_CLEARANCE_BAND[1],
    )


def check_tongue_groove_profile_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("tongue_w", "tongue_h", "tongue_len", "groove_w", "groove_depth",
            "edge_clearance", "tongue_cy", "groove_cy", "tongue_z0", "groove_z0")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.tongue_groove_profile_ok", False,
                        f"no tongue/groove frame keys: {', '.join(missing)}")
    problems: list[str] = []
    side = (f["groove_w"] - f["tongue_w"]) / 2.0
    if not (TG_SIDE_CLEARANCE_BAND[0] <= side <= TG_SIDE_CLEARANCE_BAND[1]):
        problems.append(
            f"per-side clearance {side:.2f} outside "
            f"{TG_SIDE_CLEARANCE_BAND[0]}..{TG_SIDE_CLEARANCE_BAND[1]}")
    if abs(side - f["edge_clearance"]) > 0.02:
        problems.append(
            f"measured clearance {side:.2f} != declared {f['edge_clearance']:g}")
    if f["tongue_len"] > f["groove_depth"] - TG_BOTTOM_MARGIN:
        problems.append(
            f"tongue {f['tongue_len']:g} bottoms in the groove {f['groove_depth']:g} — "
            "the joint must only align, never carry or seal")
    if abs(f["tongue_cy"] - f["groove_cy"]) > 0.05:
        problems.append("tongue and groove are not on the same line axis")
    if abs(f["tongue_z0"] - f["groove_z0"]) > 0.05:
        problems.append("tongue and groove sit at different heights")
    has_tongue = any("tongue" in r.name for r in form.ribs)
    has_groove = any("groove" in c.name for c in form.cutboxes)
    if not has_tongue:
        problems.append("no tongue rib on the part")
    if not has_groove:
        problems.append("no groove cut on the part")
    return _finding(
        "form.tongue_groove_profile_ok", not problems,
        f"groove = tongue + 2x{side:.2f}; the tongue floats {f['groove_depth'] - f['tongue_len']:.1f} short of the bottom"
        if not problems else "; ".join(problems),
        measured=side, limit=TG_SIDE_CLEARANCE_BAND[1],
    )


def check_profile_seat_dry_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("profile_size", "profile_slot_w", "profile_slot_clearance", "profile_slot_depth")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.profile_seat_dry_ok", False,
                        f"no profile seat frame keys: {', '.join(missing)}")
    slots = [c for c in form.cutboxes if "profile" in c.name]
    if not slots:
        return _finding("form.profile_seat_dry_ok", False,
                        "no profile slot cuts on the part")
    problems: list[str] = []
    want_w = f["profile_size"] + 2.0 * f["profile_slot_clearance"]
    if abs(f["profile_slot_w"] - want_w) > 0.05:
        problems.append(
            f"slot width {f['profile_slot_w']:g} != profile {f['profile_size']:g} "
            f"+ 2x{f['profile_slot_clearance']:g}")
    wet = _wet_regions(form)
    for slot in slots:
        for w in wet:
            if _boxes_overlap(slot.box, w.box):
                problems.append(f"profile slot {slot.name!r} intersects wet region {w.name!r}")
    return _finding(
        "form.profile_seat_dry_ok", not problems,
        f"{len(slots)} profile slot(s) fully outside the water path"
        if not problems else "; ".join(problems),
        measured=f["profile_slot_w"], limit=want_w,
    )


register_probe("form.water_channel_slope_ok")(
    lambda form, ctx: check_water_channel_slope_ok(form))
register_probe("form.water_channel_dims_ok")(
    lambda form, ctx: check_water_channel_dims_ok(form))
register_probe("form.no_standing_water_ir")(
    lambda form, ctx: check_no_standing_water_ir(form))
register_probe("form.overflow_lip_geometry_ok")(
    lambda form, ctx: check_overflow_lip_geometry_ok(form))
register_probe("form.no_secondary_water_channel")(
    lambda form, ctx: check_no_secondary_water_channel(form))
register_probe("form.cassette_seat_fit_ok")(
    lambda form, ctx: check_cassette_seat_fit_ok(form))
register_probe("form.tongue_groove_profile_ok")(
    lambda form, ctx: check_tongue_groove_profile_ok(form))
register_probe("form.profile_seat_dry_ok")(
    lambda form, ctx: check_profile_seat_dry_ok(form))


# -- VF-3 fluid adapters (inlet cap / collector endcap) -----------------------

#: Push-in tube grip: bore = tube OD + this band (looser slips, tighter
#: won't insert on FDM).
HOSE_GRIP_BAND = (0.2, 0.8)
#: The catch tray drains at a gentler band than the growing rail — it only
#: has to empty, not to feed substrate.
TRAY_SLOPE_BAND = (0.8, 3.0)
#: The drain bore must sit AT the tray floor (its underside within this).
DRAIN_FLOOR_TOL = 1.0


def check_hose_bore_ok(form: PartForm) -> Finding:
    tube_od = form.frame.get("hose_tube_od")
    if tube_od is None:
        return _finding("form.hose_bore_ok", False,
                        "no hose_tube_od frame key — the tube spec is unbound")
    bores = [b for b in form.bores if "hose" in b.name]
    if not bores:
        return _finding("form.hose_bore_ok", False, "no hose bore on the part")
    problems: list[str] = []
    for bore in bores:
        grip = bore.d - tube_od
        if not (HOSE_GRIP_BAND[0] - 1e-6 <= grip <= HOSE_GRIP_BAND[1] + 1e-6):
            problems.append(
                f"{bore.name!r} grip {grip:.2f} outside "
                f"{HOSE_GRIP_BAND[0]}..{HOSE_GRIP_BAND[1]} over the "
                f"{tube_od:g} tube")
        if bore.overshoot[0] <= 0.0 or bore.overshoot[1] <= 0.0:
            problems.append(
                f"{bore.name!r} is blind — a hose port must open through "
                "(cleanable, no hidden wet pocket)")
    return _finding(
        "form.hose_bore_ok", not problems,
        f"{len(bores)} hose bore(s) grip the {tube_od:g} tube and open through"
        if not problems else "; ".join(problems),
        measured=bores[0].d, limit=tube_od + HOSE_GRIP_BAND[1],
    )


def check_spout_drop_path_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("spout_w", "rail_channel_w", "channel_floor_z_outlet", "saddle_floor_z")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.spout_drop_path_ok", False,
                        f"no spout frame keys: {', '.join(missing)}")
    problems: list[str] = []
    spout = [r for r in form.ribs if "spout" in r.name]
    if not spout:
        problems.append("no spout rib on the part")
    if f["channel_floor_z_outlet"] > -0.5:
        problems.append(
            f"spout exits at z={f['channel_floor_z_outlet']:g} — it must "
            "descend below the body to reach into the rail corridor")
    # The spout dips BELOW the rail seat floor into the channel itself
    # (exit = inlet floor + FALL_ENTRY), so the budget is the channel
    # width, not the wider corridor above it.
    budget = f["rail_channel_w"] - 2.0
    if f["spout_w"] > budget:
        problems.append(
            f"spout {f['spout_w']:g} wide does not fit inside the "
            f"{f['rail_channel_w']:g} rail channel it dips into")
    drops = [b for b in form.bores if "hose" in b.name and b.axis == "Z"]
    if not drops:
        problems.append("no vertical drop bore — the cap's water path must "
                        "fall straight (no pockets by construction)")
    else:
        bore = drops[0]
        lo = min(bore.span)
        if lo > f["channel_floor_z_outlet"] + 0.1:
            problems.append(
                f"drop bore stops at z={lo:g} above the spout exit "
                f"{f['channel_floor_z_outlet']:g} — the path is interrupted")
    return _finding(
        "form.spout_drop_path_ok", not problems,
        f"spout descends to {f['channel_floor_z_outlet']:g} with a straight "
        "vertical drop — gravity does the rest"
        if not problems else "; ".join(problems),
        measured=f["spout_w"], limit=budget,
    )


def check_collector_tray_drains(form: PartForm) -> Finding:
    if not form.channels:
        return _finding("form.collector_tray_drains", False,
                        "no tray channel on the part")
    ch = form.channels[0]
    problems: list[str] = []
    if ch.depth_end <= ch.depth_start + 1e-6:
        problems.append("tray floor does not fall toward the drain")
    if not (TRAY_SLOPE_BAND[0] <= ch.slope_deg <= TRAY_SLOPE_BAND[1]):
        problems.append(
            f"tray slope {ch.slope_deg:.2f} outside "
            f"{TRAY_SLOPE_BAND[0]}..{TRAY_SLOPE_BAND[1]}")
    drains = [b for b in form.bores if "drain" in b.name]
    if not drains:
        problems.append("no drain bore — the tray would be a reservoir")
    else:
        bore = drains[0]
        floor_at_drain = ch.floor_z_at(ch.y1)
        bottom = bore.center[2] - bore.d / 2.0
        if abs(bottom - floor_at_drain) > DRAIN_FLOOR_TOL:
            problems.append(
                f"drain underside at z={bottom:.2f} vs tray floor "
                f"{floor_at_drain:.2f} — water below the drain never leaves")
        if bore.overshoot[0] <= 0.0 or bore.overshoot[1] <= 0.0:
            problems.append(f"{bore.name!r} is blind — the drain must pierce the wall")
    return _finding(
        "form.collector_tray_drains", not problems,
        f"tray falls {ch.slope_deg:.2f} deg into a through drain at the floor"
        if not problems else "; ".join(problems),
        measured=ch.slope_deg, limit=TRAY_SLOPE_BAND[1],
    )


register_probe("form.hose_bore_ok")(
    lambda form, ctx: check_hose_bore_ok(form))
register_probe("form.spout_drop_path_ok")(
    lambda form, ctx: check_spout_drop_path_ok(form))
register_probe("form.collector_tray_drains")(
    lambda form, ctx: check_collector_tray_drains(form))


# -- VF-4 profile reference proxy ---------------------------------------------

PROFILE_SLOPE_BAND = (0.0, 3.0)


def check_profile_ref_geometry_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("profile_size", "profile_len", "profile_slope_deg",
            "profile_y_low", "profile_top_z_low", "station_pitch",
            "station_count")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.profile_ref_geometry_ok", False,
                        f"no profile frame keys: {', '.join(missing)}")
    problems: list[str] = []
    if not form.channels:
        problems.append("no slope cut — the reference proxy top is flat, "
                        "the cascade would sit on nothing")
    else:
        ch = form.channels[0]
        if ch.depth_end < ch.depth_start:
            problems.append("slope cut rises toward the collector end — "
                            "the support line must fall with the cascade")
    if not (PROFILE_SLOPE_BAND[0] <= f["profile_slope_deg"] <= PROFILE_SLOPE_BAND[1]):
        problems.append(
            f"slope {f['profile_slope_deg']:g} outside "
            f"{PROFILE_SLOPE_BAND[0]}..{PROFILE_SLOPE_BAND[1]}")
    n = int(f["station_count"])
    for k in range(1, n + 1):
        if f"station_{k}_z" not in f:
            problems.append(f"station_{k} not published")
    return _finding(
        "form.profile_ref_geometry_ok", not problems,
        f"reference proxy: {f['profile_len']:g} long, "
        f"{f['profile_slope_deg']:g} deg support line, {n} stations"
        if not problems else "; ".join(problems),
        measured=f["profile_slope_deg"], limit=PROFILE_SLOPE_BAND[1],
    )


register_probe("form.profile_ref_geometry_ok")(
    lambda form, ctx: check_profile_ref_geometry_ok(form))
