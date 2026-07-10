"""VF-3 fluid adapter checks — inlet cap (chute), collector endcap,
plus the VF-4 profile reference proxy check.
"""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .part import PartForm
from .regions import Box3
from .checks_common import make_finding
from .checks_water_common import (
    _boxes_overlap)

_finding = make_finding



# -- VF-3 fluid adapters (inlet cap / collector endcap) -----------------------

#: Push-in tube grip: bore = tube OD + this band (looser slips, tighter
#: won't insert on FDM).
HOSE_GRIP_BAND = (0.2, 0.8)
#: The catch tray drains at a gentler band than the growing rail — it only
#: has to empty, not to feed substrate.
TRAY_SLOPE_BAND = (0.8, 3.0)
#: The drain bore must sit AT the tray floor (its underside within this).
DRAIN_FLOOR_TOL = 1.0
#: Collector U-frame side wall — thick enough to carry the cantilever, not
#: a thin molded skin column (VF-4.2).
COLLECTOR_WALL_MIN = 3.5
#: The side walls must MERGE with the hanging arm over a real overlap, not
#: a thin weld line that carries the whole cantilever on a glue seam.
COLLECTOR_ARM_WELD_MIN = 3.0


def check_hose_bore_ok(form: PartForm) -> Finding:
    """VF-9.2: parts with a stepped socket (`hose_socket_depth` in the frame,
    the inlet cap) seat the tube on a STOP SHOULDER — the socket must be BLIND
    at the bottom (a tube that can be pushed clean through is the defect), with
    a narrower coaxial drip orifice continuing through the stop. Parts with a
    plain hose port (the collector's push-in drain) keep the old rule: grip
    band + open through (cleanable)."""
    check = "form.hose_bore_ok"
    tube_od = form.frame.get("hose_tube_od")
    if tube_od is None:
        return _finding(check, False,
                        "no hose_tube_od frame key — the tube spec is unbound")
    stepped = "hose_socket_depth" in form.frame
    problems: list[str] = []
    if stepped:
        socket = next((b for b in form.bores if "hose_socket" in b.name), None)
        orifice = next((b for b in form.bores if "hose_drop" in b.name), None)
        if socket is None or orifice is None:
            return _finding(check, False,
                            "stepped hose port needs BOTH a hose_socket and a "
                            "hose_drop orifice bore")
        grip = socket.d - tube_od
        if not (HOSE_GRIP_BAND[0] - 1e-6 <= grip <= HOSE_GRIP_BAND[1] + 1e-6):
            problems.append(
                f"socket grip {grip:.2f} outside "
                f"{HOSE_GRIP_BAND[0]}..{HOSE_GRIP_BAND[1]} over the {tube_od:g} tube")
        if socket.overshoot[0] > 0.0:
            problems.append(
                "socket opens THROUGH at the bottom — no stop shoulder, the "
                "tube can be pushed clean through the cap")
        if socket.overshoot[1] <= 0.0:
            problems.append("socket is closed at the top — the tube cannot enter")
        depth = max(socket.span) - min(socket.span)
        if not (8.0 - 1e-6 <= depth <= 14.0 + 1e-6):
            problems.append(f"socket depth {depth:.1f} outside 8..14 — not a "
                            "real push-in grip")
        if not (4.0 - 1e-6 <= orifice.d <= tube_od - 2.0 + 1e-6):
            problems.append(
                f"orifice {orifice.d:g} outside 4..{tube_od - 2.0:g} — the stop "
                "must be real (narrower than the tube) yet not clog")
        if (abs(orifice.center[0] - socket.center[0]) > 0.1
                or abs(orifice.center[1] - socket.center[1]) > 0.1):
            problems.append("orifice is not coaxial with the socket — the water "
                            "path bends inside solid plastic")
        if abs(max(orifice.span) - min(socket.span)) > 0.1:
            problems.append("orifice does not meet the socket bottom — the "
                            "water path is interrupted at the stop")
        return _finding(
            check, not problems,
            f"tube seats on the stop shoulder at z={min(socket.span):g}; the "
            f"Ø{orifice.d:g} drip orifice continues the path"
            if not problems else "; ".join(problems),
            measured=socket.d, limit=tube_od + HOSE_GRIP_BAND[1],
        )
    bores = [b for b in form.bores if "hose" in b.name]
    if not bores:
        return _finding(check, False, "no hose bore on the part")
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
        check, not problems,
        f"{len(bores)} hose bore(s) grip the {tube_od:g} tube and open through"
        if not problems else "; ".join(problems),
        measured=bores[0].d, limit=tube_od + HOSE_GRIP_BAND[1],
    )


def check_spout_drop_path_ok(form: PartForm) -> Finding:
    """VF-9.2 chute semantics: the cap's water path is socket -> orifice ->
    chamber -> an OPEN U-trough (floor + two walls) whose tip edge drips into
    the rail channel. The trough must exist (floor + both walls), descend below
    the body into the channel, fit inside the rail channel width, and the tip
    must be the spout datum — the geometry itself explains where the water
    goes."""
    check = "form.spout_drop_path_ok"
    f = form.frame
    keys = ("spout_w", "rail_channel_w", "channel_floor_z_outlet",
            "saddle_floor_z", "chute_tip_y")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding(check, False,
                        f"no spout frame keys: {', '.join(missing)}")
    problems: list[str] = []
    floor = next((r for r in form.ribs if "nose_floor" in r.name), None)
    walls = [r for r in form.ribs if "nose_wall" in r.name]
    if floor is None:
        problems.append("no chute floor rib on the part")
    if len(walls) < 2:
        problems.append(f"chute has {len(walls)} wall rib(s) — a U-trough "
                        "needs both")
    z_exit = f["channel_floor_z_outlet"]
    if z_exit > -0.5:
        problems.append(
            f"chute tip exits at z={z_exit:g} — it must descend below the "
            "body to reach into the rail channel")
    if floor is not None:
        if abs(floor.box.z1 - z_exit) > 0.1:
            problems.append(
                f"chute floor top {floor.box.z1:g} is not the declared exit "
                f"plane {z_exit:g}")
        if floor.box.y0 > f["chute_tip_y"] + 0.1:
            problems.append(
                f"chute floor stops at y={floor.box.y0:g} short of the tip "
                f"{f['chute_tip_y']:g}")
    # The trough dips into the channel, so the budget is the channel width.
    budget = f["rail_channel_w"] - 2.0
    if f["spout_w"] > budget:
        problems.append(
            f"chute {f['spout_w']:g} wide does not fit inside the "
            f"{f['rail_channel_w']:g} rail channel it dips into")
    drops = [b for b in form.bores if "hose_drop" in b.name and b.axis == "Z"]
    if not drops:
        problems.append("no vertical drip orifice — water must fall from the "
                        "socket into the chute")
    spout = form.datums.get("spout")
    if spout is not None and abs(spout["at"][1] - f["chute_tip_y"]) > 0.1:
        problems.append(
            f"spout datum y={spout['at'][1]:g} is not the chute tip "
            f"{f['chute_tip_y']:g} — the datum must mark the real drip point")
    return _finding(
        check, not problems,
        f"open chute carries the drip to y={f['chute_tip_y']:g} and drops it "
        f"from z={z_exit:g} into the channel — gravity does the rest"
        if not problems else "; ".join(problems),
        measured=f["spout_w"], limit=budget,
    )


def check_cap_water_path_visible(form: PartForm) -> Finding:
    """VF-9.2 (user rule): the inlet cap must NOT contain a closed horizontal
    water tunnel — the eye must be able to follow the water. Legal path:
    vertical socket+orifice, a SHORT covered chamber (the drop shaft), then an
    OPEN-TOP chute all the way to the tip. n/a on parts without a chute."""
    from .recipe_ops_water import CAP_COVERED_RUN_MAX

    check = "form.cap_water_path_visible"
    f = form.frame
    if "chute_tip_y" not in f:
        return _finding(check, True, "no chute on this part — n/a")
    problems: list[str] = []
    chamber = next((c for c in form.cutboxes if "chamber" in c.name), None)
    sky = next((c for c in form.cutboxes if "chute_sky" in c.name), None)
    if chamber is None:
        problems.append("no chamber cut — the orifice has nowhere to drop")
    else:
        covered = chamber.box.y1 - chamber.box.y0
        if covered > CAP_COVERED_RUN_MAX + 1e-6:
            problems.append(
                f"covered chamber run {covered:.1f} > {CAP_COVERED_RUN_MAX:g} "
                "— a closed horizontal water tunnel, not a small drop shaft")
    if sky is None:
        problems.append("no sky opening over the chute — the water path is "
                        "hidden under the roof")
    else:
        b = sky.box
        if b.z1 < f.get("channel_top_z", 0.0) - 0.05:
            problems.append(
                f"sky opening stops at z={b.z1:g} below the cap top — the "
                "chute is still roofed")
        if chamber is not None and b.y1 < chamber.box.y0 - 0.1:
            problems.append("sky opening does not adjoin the chamber — a "
                            "covered gap hides the path")
    # a horizontal bore inside the wet path would be a closed side tunnel
    spout = form.region("spout_path")
    if spout is not None:
        for bore in form.bores:
            if bore.axis == "Z":
                continue
            x, y, z = bore.center
            r = bore.d / 2.0
            lo, hi = bore.span
            bbox = (Box3(x - r, lo, z - r, x + r, hi, z + r)
                    if bore.axis == "Y"
                    else Box3(lo, y - r, z - r, hi, y + r, z + r))
            if _boxes_overlap(bbox, spout.box):
                problems.append(
                    f"horizontal bore {bore.name!r} runs inside the water "
                    "path — a closed tunnel")
    return _finding(
        check, not problems,
        "the water path is visible: vertical socket, a short drop shaft, then "
        "an open-top chute to the drip tip"
        if not problems else "; ".join(problems),
        limit=CAP_COVERED_RUN_MAX,
    )


def check_collector_tray_drains(form: PartForm) -> Finding:
    """VF-4.2: the tray falls to its sump low point, and a VERTICAL drain
    bore descends from that low point through the solid base and out the
    bottom — the tube pushes in from below. (The old horizontal-drain
    branch is gone; the collector was its only client.)"""
    if not form.channels:
        return _finding("form.collector_tray_drains", False,
                        "no tray channel on the part")
    ch = form.channels[0]
    f = form.frame
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
        if bore.axis != "Z":
            problems.append(
                f"drain axis {bore.axis} — the VF-4.2 collector drains "
                "VERTICALLY out the bottom")
        else:
            # the bore MOUTH (its top) must reach the tray floor low point,
            # and it must sit at that low point in Y (the deep end)
            top = max(bore.span) + bore.overshoot[1]
            low = f.get("tray_floor_low_z")
            if low is not None and top < low - DRAIN_FLOOR_TOL:
                problems.append(
                    f"drain top z={top:.2f} below the tray low floor {low:.2f} "
                    "— water above it never reaches the drain")
            low_y = f.get("drain_low_y")
            if low_y is not None and abs(bore.center[1] - low_y) > bore.d / 2.0 + 1.0:
                problems.append(
                    "drain is not at the tray low point — water pools before it")
            if bore.overshoot[0] <= 0.0:
                problems.append(
                    f"{bore.name!r} is blind below — the drain must exit the bottom")
        if bore.d < f.get("hose_tube_od", 0.0):
            problems.append("drain narrower than the tube")
    return _finding(
        "form.collector_tray_drains", not problems,
        f"tray falls {ch.slope_deg:.2f} deg into a vertical drain at the "
        "sump low point — empties out the bottom"
        if not problems else "; ".join(problems),
        measured=ch.slope_deg, limit=TRAY_SLOPE_BAND[1],
    )


def check_collector_structure_sturdy(form: PartForm) -> Finding:
    """VF-4.2: the cantilevered tray hangs off the rail on TWO full side
    walls, not thin columns — closes the min_wall blind spot (it measures
    the `wall` param, never the actual rib sections). The walls are thick
    enough, rooted at the tray bottom, run the full length and weld into
    the arm."""
    check = "form.collector_structure_sturdy"
    f = form.frame
    keys = ("wall_x0", "wall_t", "wall_z0", "wall_z1", "arm_z0", "tray_bottom_z")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding(check, False, f"no structure frame keys: {', '.join(missing)}")
    walls = [r for r in form.ribs if "cheek" in r.name]
    problems: list[str] = []
    if len(walls) != 2:
        problems.append(f"{len(walls)} side wall(s) — the U-frame needs both flanks")
    if f["wall_t"] < COLLECTOR_WALL_MIN:
        problems.append(
            f"side wall {f['wall_t']:.1f} thick < {COLLECTOR_WALL_MIN:g} — "
            "a thin column, not a wall")
    for w in walls:
        if w.box.z0 > f["tray_bottom_z"] + 2.0 + 1e-6:
            problems.append(
                f"wall {w.name!r} starts at z={w.box.z0:.1f}, not rooted at the "
                f"tray bottom {f['tray_bottom_z']:.1f} — a column on the rim")
        if w.box.z1 < f["arm_z0"] + COLLECTOR_ARM_WELD_MIN - 1e-6:
            problems.append(
                f"wall {w.name!r} overlaps the arm only "
                f"{max(0.0, w.box.z1 - f['arm_z0']):.1f} (needs >= "
                f"{COLLECTOR_ARM_WELD_MIN:g}) — a glue seam, not a merged wall")
        span = w.box.y1 - w.box.y0
        if span < abs(f.get("drain_low_y", 0.0)) * 0.5:
            problems.append(f"wall {w.name!r} does not run the tray length")
    if len(walls) == 2:  # symmetry about the centerline
        c0 = walls[0].box.x0 + walls[0].box.x1
        c1 = walls[1].box.x0 + walls[1].box.x1
        if abs(c0 + c1) > 0.4:
            problems.append("side walls are not symmetric about the centerline")
    return _finding(
        check, not problems,
        f"U-frame: two {f['wall_t']:.1f}-thick side walls from the tray "
        "bottom into the arm — the tray hangs on walls, not columns"
        if not problems else "; ".join(problems),
        measured=f["wall_t"], limit=COLLECTOR_WALL_MIN,
    )


register_probe("form.hose_bore_ok")(
    lambda form, ctx: check_hose_bore_ok(form))
register_probe("form.cap_water_path_visible")(
    lambda form, ctx: check_cap_water_path_visible(form))
register_probe("form.spout_drop_path_ok")(
    lambda form, ctx: check_spout_drop_path_ok(form))



# registrations for the collector checks defined above
register_probe("form.collector_structure_sturdy")(
    lambda form, ctx: check_collector_structure_sturdy(form))
register_probe("form.collector_tray_drains")(
    lambda form, ctx: check_collector_tray_drains(form))

# -- VF-4 profile reference proxy ---------------------------------------------



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
    # VF correction: the reference geometry must be LITERALLY a standard
    # straight profile — a sloped or beheaded model is the old surrogate
    if abs(f["profile_slope_deg"]) > 1e-6:
        problems.append(
            f"model slope {f['profile_slope_deg']:g} deg — the corrected "
            "carrier is a STANDARD STRAIGHT profile; the row slope belongs "
            "to mount_context")
    if form.channels:
        problems.append("slope cut on the profile body — a straight "
                        "extrusion has nothing to behead")
    n = int(f["station_count"])
    zs = []
    for k in range(1, n + 1):
        if f"station_{k}_z" not in f:
            problems.append(f"station_{k} not published")
        else:
            zs.append(f[f"station_{k}_z"])
    if zs and (max(zs) - min(zs)) > 0.05:
        problems.append("stations sit at different heights on a straight top")
    return _finding(
        "form.profile_ref_geometry_ok", not problems,
        f"standard straight profile, {f['profile_len']:g} cut to length, "
        f"{n} level stations — the mount supplies the slope"
        if not problems else "; ".join(problems),
        measured=f["profile_slope_deg"], limit=0.0,
    )


register_probe("form.profile_ref_geometry_ok")(
    lambda form, ctx: check_profile_ref_geometry_ok(form))
