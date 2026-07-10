"""Water-rail channel, lap handover, drainage, magnet/dock dryness and
screen/sump checks (VF core water path).
"""
from __future__ import annotations

from artifact_forge_ng.core.findings import Finding, Level, Status
from artifact_forge_ng.validators.probes import register_probe
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.regions import Box3
from artifact_forge_ng.form.checks_common import make_finding
from .common import (
    _boxes_overlap, _wet_regions, _blind_bore_drained_below, _pocket_drained_by_through_bore, MOUNT_SLOPE_BAND, CONST_DEPTH_TOL, CHANNEL_D_BAND, CHANNEL_W_BAND, BOTTOM_R_BAND, FLOOR_MARGIN_MIN, LAP_LIP_LEN_BAND, LAP_LIP_T_BAND, LAP_SIDE_CLEAR_BAND, LAP_SLOT_BAND, FACE_GAP_BAND, LAP_LATERAL_CLEAR_MIN, MAGNET_WET_WALL_MIN, MAGNET_FIT_BAND, LW_RIB_MIN)

_finding = make_finding


def check_water_channel_constant_depth_ok(form: PartForm) -> Finding:
    """The corrected rail contract: the channel floor is LEVEL end to end.
    The drainage slope belongs to the mount (mount_context), never to the
    geometry — a sloped floor here would re-create the cascade steps."""
    if not form.channels:
        return _finding("form.water_channel_constant_depth_ok", False,
                        "no water channel declared on this part")
    ch = form.channels[0]
    problems: list[str] = []
    if abs(ch.depth_end - ch.depth_start) > CONST_DEPTH_TOL:
        problems.append(
            f"channel depth varies {ch.depth_start:g} -> {ch.depth_end:g} — "
            "the rail must stay level; the mount supplies the slope")
    if not (CHANNEL_D_BAND[0] <= ch.depth_start <= CHANNEL_D_BAND[1]):
        problems.append(
            f"depth {ch.depth_start:g} outside {CHANNEL_D_BAND[0]}..{CHANNEL_D_BAND[1]}")
    declared = form.frame.get("channel_slope_deg")
    if declared is not None and abs(declared) > 1e-6:
        problems.append(
            f"frame declares channel_slope_deg={declared:g} — must be 0 on a flush rail")
    fi = form.frame.get("channel_floor_z_inlet")
    fo = form.frame.get("channel_floor_z_outlet")
    if fi is None or fo is None:
        problems.append("no channel_floor_z_inlet/outlet frame keys")
    elif abs(fi - fo) > CONST_DEPTH_TOL:
        problems.append(f"frame floor keys differ ({fi:g} vs {fo:g})")
    return _finding(
        "form.water_channel_constant_depth_ok", not problems,
        f"level channel floor, {ch.depth_start:g} deep end to end — "
        "slope is the mount's job"
        if not problems else "; ".join(problems),
        measured=abs(ch.depth_end - ch.depth_start), limit=CONST_DEPTH_TOL,
        suggestion="" if not problems else "set depth_start == depth_end and slope 0",
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
        if _blind_bore_drained_below(bore, form.bores):
            continue  # VF-9.2: a stepped tube socket — the coaxial orifice
            # adjoining its blind bottom drains it (the stop is intentional)
        if any(_boxes_overlap(bbox, w.box) for w in wet):
            offenders.append(f"blind bore {bore.name!r} in the wet path")
    for cut in form.cutboxes:
        b = cut.box
        if b.z0 <= 0.05:
            continue  # open to the underside — cannot pool
        if top is not None and b.z0 >= top - 0.05:
            continue  # floor at/above the channel entry plane — a dry step
        if _pocket_drained_by_through_bore(b, form.bores):
            continue  # a vertical open-bottom bore in its footprint drains it
        if "lap_receiver" in cut.name and (b.z1 - b.z0) <= 2.2:
            continue  # VF-9: a SHALLOW floored lip-seat — the neighbour's lip
            # fills it and it drains forward under the mount tilt, not a sump
        if any(_boxes_overlap(b, w.box) for w in wet):
            offenders.append(f"pocket {cut.name!r} floors at z={b.z0:g} inside the wet path")
    return _finding(
        "form.no_standing_water_ir", not offenders,
        "no blind pocket can hold water in the wet path"
        if not offenders else "; ".join(offenders),
        suggestion="" if not offenders else "open the pocket to the underside or move it out of the wet path",
    )


def check_lap_joint_geometry_ok(form: PartForm) -> Finding:
    """The flush handover pair on one rail (VF-9): an outlet lip that CONTINUES
    the channel floor plane (top at floor level — higher is a dam, lower a step)
    and an inlet FLOORED lip-seat the neighbour's lip nests into (its top lands
    flush with the floor), with a deliberate slot left open only at the tip. The
    receiver is a shallow CLOSED-bottom pocket — never a through hole under the
    water path."""
    f = form.frame
    keys = ("lap_lip_len", "lap_lip_w", "lap_lip_t", "lap_lip_top_z",
            "lap_pocket_len", "lap_pocket_w", "lap_pocket_floor_z", "face_gap",
            "channel_floor_z_inlet", "channel_floor_z_outlet")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.lap_joint_geometry_ok", False,
                        f"no lap frame keys: {', '.join(missing)}")
    problems: list[str] = []
    # -- OUTLET LIP (continues the floor) --
    lip = next((r for r in form.ribs if "lap_lip" in r.name), None)
    if lip is None:
        problems.append("no lap lip rib on the part")
    else:
        if abs(lip.box.z1 - f["channel_floor_z_outlet"]) > CONST_DEPTH_TOL:
            problems.append(
                f"lip top {lip.box.z1:g} is not the channel floor "
                f"{f['channel_floor_z_outlet']:g} — a dam or a step, never flush")
        if abs((lip.box.z1 - lip.box.z0) - f["lap_lip_t"]) > 0.05:
            problems.append("lip rib thickness disagrees with lap_lip_t")
    if not (LAP_LIP_LEN_BAND[0] <= f["lap_lip_len"] <= LAP_LIP_LEN_BAND[1]):
        problems.append(
            f"lip protrusion {f['lap_lip_len']:g} outside "
            f"{LAP_LIP_LEN_BAND[0]}..{LAP_LIP_LEN_BAND[1]}")
    if not (LAP_LIP_T_BAND[0] <= f["lap_lip_t"] <= LAP_LIP_T_BAND[1]):
        problems.append(f"lip thickness {f['lap_lip_t']:g} outside "
                        f"{LAP_LIP_T_BAND[0]}..{LAP_LIP_T_BAND[1]}")
    if not (FACE_GAP_BAND[0] <= f["face_gap"] <= FACE_GAP_BAND[1]):
        problems.append(f"face gap {f['face_gap']:g} outside "
                        f"{FACE_GAP_BAND[0]}..{FACE_GAP_BAND[1]}")
    # -- INLET FLOORED lip-seat (closed bottom, lip nests flush) --
    pocket = next((c for c in form.cutboxes if "lap_receiver" in c.name), None)
    if pocket is None:
        problems.append("no lap receiver cut on the part")
    else:
        b = pocket.box
        if b.z0 <= 0.05:
            problems.append(
                f"receiver is open-bottom (z0={b.z0:g}) — it must be FLOORED "
                "(a closed lip-seat, no through hole under the water path)")
        if abs(b.z0 - f["lap_pocket_floor_z"]) > 0.05:
            problems.append("receiver floor disagrees with lap_pocket_floor_z")
        if b.z1 < f["channel_floor_z_inlet"] - CONST_DEPTH_TOL:
            problems.append("receiver stops short of the floor plane — the lip cannot land")
        side = (f["lap_pocket_w"] - f["lap_lip_w"]) / 2.0
        if not (LAP_SIDE_CLEAR_BAND[0] <= side <= LAP_SIDE_CLEAR_BAND[1]):
            problems.append(
                f"per-side lip clearance {side:.2f} outside "
                f"{LAP_SIDE_CLEAR_BAND[0]}..{LAP_SIDE_CLEAR_BAND[1]}")
    slot = f["lap_pocket_len"] - (f["lap_lip_len"] - f["face_gap"])
    if not (LAP_SLOT_BAND[0] <= slot <= LAP_SLOT_BAND[1]):
        problems.append(
            f"tip slot {slot:.2f} outside {LAP_SLOT_BAND[0]}..{LAP_SLOT_BAND[1]} — "
            "the seam must stay deliberately open, and only just")
    return _finding(
        "form.lap_joint_geometry_ok", not problems,
        f"lip continues the floor plane {f['lap_lip_len']:g} past the face; the "
        f"receiver is a floored lip-seat with a {slot:.1f} tip slot"
        if not problems else "; ".join(problems),
        measured=slot, limit=LAP_SLOT_BAND[1],
    )


def check_lap_slot_leak_path_controlled(form: PartForm) -> Finding:
    """The deliberate seam slot must leak into KNOWN air: straight down
    the FLOORED lip-seat has no open bottom (no downward leak); the only opening
    is the top tip-slot at the seam, whose stray drops must stay laterally far
    from the profile slots, magnet pockets and dry zones. The nominal stream
    crosses ON TOP of the nested lip."""
    f = form.frame
    if "lap_pocket_w" not in f:
        return _finding("form.lap_slot_leak_path_controlled", False,
                        "no lap receiver on the part — nothing to control")
    problems: list[str] = []
    pocket = next((c for c in form.cutboxes if "lap_receiver" in c.name), None)
    if pocket is None:
        problems.append("no lap receiver cut on the part")
    else:
        b = pocket.box
        if b.z0 <= 0.05:
            problems.append(
                f"receiver is open-bottom (z0={b.z0:g}) — it must be FLOORED so "
                "nothing leaks straight down at the seam")
        half = f["lap_pocket_w"] / 2.0
        slot_x = half
        px = f.get("profile_slot_x")
        if px is not None:
            clear = (px - f.get("profile_slot_w", 0.0) / 2.0) - slot_x
            if clear < LAP_LATERAL_CLEAR_MIN:
                problems.append(
                    f"profile slot only {clear:.0f} from the leak slot "
                    f"(needs >= {LAP_LATERAL_CLEAR_MIN:g}) — drips could reach aluminum")
        mx = f.get("magnet_x_offset")
        if mx is not None and f.get("magnet_count", 0):
            clear = (mx - f.get("magnet_pocket_d", 0.0) / 2.0) - slot_x
            if clear < LAP_LATERAL_CLEAR_MIN:
                problems.append(
                    f"magnet pockets only {clear:.0f} from the leak slot "
                    f"(needs >= {LAP_LATERAL_CLEAR_MIN:g})")
        dry = form.region("dry_zone_back")
        if dry is not None and _boxes_overlap(
                Box3(-half, b.y0, -5.0, half, b.y1, 0.0), dry.box):
            problems.append("the dry back zone extends under the leak slot")
    return _finding(
        "form.lap_slot_leak_path_controlled", not problems,
        "floored lip-seat — no downward leak; the top tip-slot's stray drops "
        "stay clear of aluminum, magnets and dry zones (non-gasketed, cleanable)"
        if not problems else "; ".join(problems),
        limit=LAP_LATERAL_CLEAR_MIN,
    )


LAP_RECEIVER_MAX_DEPTH = 2.0   # mm — a lip-SEAT, not a reservoir


def check_lap_receiver_has_floor(form: PartForm) -> Finding:
    """VF-9: the inlet lap receiver is a top-open pocket with a SOLID bottom (a
    floored lip-seat), not a through hole under the water path. n/a with no
    receiver."""
    check = "form.lap_receiver_has_floor"
    pocket = next((c for c in form.cutboxes if "lap_receiver" in c.name), None)
    if pocket is None or "lap_pocket_floor_z" not in form.frame:
        return _finding(check, True, "no lap receiver — n/a")
    z0 = pocket.box.z0
    ok = z0 > 0.05
    return _finding(
        check, ok,
        f"lap receiver is floored (pocket floor z={z0:.1f}) — closed below, no "
        "through hole under the water path"
        if ok else
        f"lap receiver is open-bottom (z0={z0:g}) — a through hole under the water path",
        measured=z0)


def check_lap_receiver_residual_volume_ok(form: PartForm) -> Finding:
    """VF-9: the lap receiver is a SHALLOW lip-SEAT, not a small reservoir —
    depth <= 2 mm, open-top and cleanable — so that without the neighbour's lip it
    does not hold a deep wet pocket. Reports `lap_receiver_residual_volume_mm3`.
    n/a with no receiver."""
    check = "form.lap_receiver_residual_volume_ok"
    f = form.frame
    depth = f.get("lap_pocket_depth")
    if depth is None:
        return _finding(check, True, "no lap receiver — n/a")
    pw = f.get("lap_pocket_w", 0.0)
    slot = f.get("lap_pocket_len", 0.0) - (f.get("lap_lip_len", 0.0) - f.get("face_gap", 0.0))
    residual = pw * max(0.0, slot) * depth   # lap_receiver_residual_volume_mm3
    ok = depth <= LAP_RECEIVER_MAX_DEPTH + 1e-6
    return _finding(
        check, ok,
        f"shallow lip-seat: depth {depth:.1f} mm, residual ~{residual:.0f} mm3 "
        "when the neighbour's lip is out — drains, not a reservoir"
        if ok else
        f"pocket depth {depth:.1f} > {LAP_RECEIVER_MAX_DEPTH:g} mm — too deep, a "
        "reservoir not a lip seat",
        measured=depth, limit=LAP_RECEIVER_MAX_DEPTH)


def check_rail_universal_inlet_accepts_cap_and_lap(form: PartForm) -> Finding:
    """VF-9: the rail inlet is UNIVERSAL — one floored lip-seat that both catches
    an inlet-cap drip AND seats a neighbour's lap lip (no special capped variant).
    n/a on parts without a lap receiver."""
    check = "form.rail_universal_inlet_accepts_cap_and_lap"
    pocket = next((c for c in form.cutboxes if "lap_receiver" in c.name), None)
    if pocket is None or "lap_pocket_floor_z" not in form.frame:
        return _finding(check, True, "not a flush rail inlet — n/a")
    ok = pocket.box.z0 > 0.05   # floored → catches a drip AND seats a lip
    return _finding(
        check, ok,
        "universal inlet — one floored lip-seat catches a cap drip and seats a "
        "neighbour's lap lip"
        if ok else "inlet is not a floored universal seat")


def check_drainage_requires_mount(form: PartForm) -> Finding:
    """Honesty note, PASS-with-note (grade-neutral): a constant-depth
    channel drains ONLY when the whole row is mounted at the operational
    slope. Horizontal the part is buildable but not operational. The FAIL
    for a missing/out-of-band mount lives at assembly level
    (assembly.row_drains_under_mount), never here."""
    if not form.channels:
        return _finding("form.drainage_requires_mount", False,
                        "no water channel declared on this part")
    ch = form.channels[0]
    level = abs(ch.depth_end - ch.depth_start) <= CONST_DEPTH_TOL
    if not level:
        return _finding(
            "form.drainage_requires_mount", False,
            "channel is not constant-depth — this note only applies to flush rails")
    return Finding(
        check="form.drainage_requires_mount", status=Status.PASS, level=Level.FORM,
        message=(
            f"INFO: level channel — drains only under the mounted row slope "
            f"{MOUNT_SLOPE_BAND[0]:g}..{MOUNT_SLOPE_BAND[1]:g} deg "
            "(buildable horizontal, operational mounted; see mount_context)"),
        critical=False,
    )


def check_magnet_pockets_outside_water_zone(form: PartForm) -> Finding:
    """Every magnet pocket lives in dry body: no pocket volume may touch a
    wet region. Trivially green with magnets disabled."""
    pockets = [b for b in form.bores if "magnet" in b.name]
    if not pockets:
        return _finding("form.magnet_pockets_outside_water_zone", True,
                        "no magnet pockets — nothing near the water")
    wet = _wet_regions(form)
    problems: list[str] = []
    for b in pockets:
        x, y, z = b.center
        r = b.d / 2.0
        lo, hi = min(b.span), max(b.span)
        bbox = Box3(x - r, lo, z - r, x + r, hi, z + r)  # axis Y pockets
        for w in wet:
            if _boxes_overlap(bbox, w.box):
                problems.append(f"magnet pocket {b.name!r} touches wet region {w.name!r}")
    return _finding(
        "form.magnet_pockets_outside_water_zone", not problems,
        f"{len(pockets)} magnet pocket(s) fully in dry body"
        if not problems else "; ".join(problems),
    )


def check_magnet_pockets_do_not_break_wall(form: PartForm) -> Finding:
    """Sealed pockets: blind (never pierce the face they enter from), and
    >= MAGNET_WET_WALL_MIN plastic between the pocket and any wet zone —
    no magnet face is ever exposed to water."""
    pockets = [b for b in form.bores if "magnet" in b.name]
    if not pockets:
        return _finding("form.magnet_pockets_do_not_break_wall", True,
                        "no magnet pockets — no wall to break")
    f = form.frame
    y0, y1 = f.get("rail_y0"), f.get("rail_y1")
    problems: list[str] = []
    wet = _wet_regions(form)
    fit = f.get("magnet_fit_clearance")
    if fit is not None and not (MAGNET_FIT_BAND[0] - 1e-9 <= fit
                                <= MAGNET_FIT_BAND[1] + 1e-9):
        problems.append(
            f"diametral fit {fit:g} outside the press band "
            f"{MAGNET_FIT_BAND[0]}..{MAGNET_FIT_BAND[1]} — a slip fit falls "
            "out, an interference fit cracks the face")
    for b in pockets:
        blind = b.overshoot[0] <= 0.0 or b.overshoot[1] <= 0.0
        if not blind:
            problems.append(f"magnet pocket {b.name!r} is a through bore")
        # magnets live in the MATING +-Y faces (the rail-to-rail joint) —
        # a pocket entered from any other face aligns nothing
        if b.axis != "Y":
            problems.append(
                f"magnet pocket {b.name!r} enters a non-mating face "
                f"(axis {b.axis}) — alignment magnets live in the +-Y "
                "rail-to-rail faces")
        if y0 is not None and y1 is not None:
            lo, hi = min(b.span), max(b.span)
            inside = min(hi - y0, y1 - lo)  # depth measured from the entry face
            body = (y1 - y0) - inside
            if body < MAGNET_WET_WALL_MIN:
                problems.append(
                    f"pocket {b.name!r} leaves only {body:g} body behind it")
        x, y, z = b.center
        r = b.d / 2.0
        lo, hi = min(b.span), max(b.span)
        grown = Box3(x - r - MAGNET_WET_WALL_MIN, lo - MAGNET_WET_WALL_MIN,
                     z - r - MAGNET_WET_WALL_MIN,
                     x + r + MAGNET_WET_WALL_MIN, hi + MAGNET_WET_WALL_MIN,
                     z + r + MAGNET_WET_WALL_MIN)
        for w in wet:
            if _boxes_overlap(grown, w.box):
                problems.append(
                    f"pocket {b.name!r} leaves < {MAGNET_WET_WALL_MIN:g} plastic "
                    f"to wet region {w.name!r}")
    return _finding(
        "form.magnet_pockets_do_not_break_wall", not problems,
        f"{len(pockets)} sealed pocket(s): blind, >= {MAGNET_WET_WALL_MIN:g} "
        "plastic to every wet zone"
        if not problems else "; ".join(problems),
        limit=MAGNET_WET_WALL_MIN,
    )


def check_dock_pockets_dry(form: PartForm) -> Finding:
    """Endcap dock magnets: blind pockets that dock the collector or the inlet
    cap onto a rail END. Two styles — TOP (Z pockets into the wall top, VF-6
    collector) and FACE (Y pockets into the +/-Y end face, VF-9 support-free
    cap hook). Each must be blind (a plastic floor to the far face), enter along
    the dock axis (Z for top, Y for face), sit >= MAGNET_WET_WALL_MIN from every
    wet region, and press-fit. Same part on both sides runs this check; n/a-PASS
    with no dock pockets."""
    check = "form.dock_pockets_dry"
    pockets = [b for b in form.bores if "dock" in b.name]
    if not pockets:
        return _finding(check, True, "no dock pockets — nothing to seat")
    face_style = form.frame.get("dock_style_face", 0.0) >= 0.5
    dock_axis = "Y" if face_style else "Z"
    wet = _wet_regions(form)
    problems: list[str] = []
    fit = form.frame.get("dock_fit_clearance")
    if fit is not None and not (MAGNET_FIT_BAND[0] - 1e-9 <= fit
                                <= MAGNET_FIT_BAND[1] + 1e-9):
        problems.append(
            f"dock fit {fit:g} outside the press band "
            f"{MAGNET_FIT_BAND[0]}..{MAGNET_FIT_BAND[1]}")
    for b in pockets:
        if b.overshoot[0] > 0.0 and b.overshoot[1] > 0.0:
            problems.append(f"dock pocket {b.name!r} is a through bore")
        if b.axis != dock_axis:
            problems.append(
                f"dock pocket {b.name!r} enters along {b.axis} — a "
                f"{'face' if face_style else 'top'} dock seats along {dock_axis}")
        x, y, z = b.center
        r = b.d / 2.0
        lo, hi = min(b.span), max(b.span)
        m = MAGNET_WET_WALL_MIN
        if b.axis == "Z":
            grown = Box3(x - r - m, y - r - m, lo - m, x + r + m, y + r + m, hi + m)
        elif b.axis == "Y":
            grown = Box3(x - r - m, lo - m, z - r - m, x + r + m, hi + m, z + r + m)
        else:  # X
            grown = Box3(lo - m, y - r - m, z - r - m, hi + m, y + r + m, z + r + m)
        for w in wet:
            if _boxes_overlap(grown, w.box):
                problems.append(
                    f"dock pocket {b.name!r} leaves < {MAGNET_WET_WALL_MIN:g} "
                    f"plastic to wet region {w.name!r}")
    return _finding(
        check, not problems,
        f"{len(pockets)} dock pocket(s): blind, along {dock_axis}, >= "
        f"{MAGNET_WET_WALL_MIN:g} plastic to every wet zone"
        if not problems else "; ".join(problems),
        limit=MAGNET_WET_WALL_MIN,
    )


#: A drain-screen basket must not choke the flow: total open area (bottom mesh
#: + wall slots) at least ~4x the standard Ø9.4 drain bore (~69 mm2). And it
#: must hold a real debris reservoir so it isn't full after one watering.
SCREEN_MIN_OPEN_AREA = 300.0   # mm2
SCREEN_MIN_DEBRIS_ML = 3.0     # ml


def check_screen_open_area_ratio_ok(form: PartForm) -> Finding:
    """VF-8: the strainer's total open area (bottom mesh + wall slots) must be
    generous vs the drain bore, or the basket itself becomes the plug. n/a-PASS
    on parts that are not a drain screen."""
    check = "form.screen_open_area_ratio_ok"
    area = form.frame.get("screen_open_area_mm2")
    if area is None:
        return _finding(check, True, "not a drain screen — n/a")
    ok = area >= SCREEN_MIN_OPEN_AREA - 1e-6
    mesh = form.frame.get("screen_mesh_area_mm2", 0.0)
    slot = form.frame.get("screen_slot_area_mm2", 0.0)
    return _finding(
        check, ok,
        f"open area {area:.0f} mm2 (mesh {mesh:.0f} + slots {slot:.0f}) "
        f">= {SCREEN_MIN_OPEN_AREA:g} — flow is not choked"
        if ok else
        f"open area {area:.0f} mm2 < {SCREEN_MIN_OPEN_AREA:g} — the screen would "
        "choke the drain; widen the mesh or add wall slots",
        measured=area, limit=SCREEN_MIN_OPEN_AREA,
    )


def check_screen_debris_capacity_ok(form: PartForm) -> Finding:
    """VF-8: the basket must hold a real debris reservoir above the mesh so it
    is not full after a single watering. n/a-PASS when not a drain screen."""
    check = "form.screen_debris_capacity_ok"
    vol = form.frame.get("screen_debris_volume_ml")
    if vol is None:
        return _finding(check, True, "not a drain screen — n/a")
    ok = vol >= SCREEN_MIN_DEBRIS_ML - 1e-6
    return _finding(
        check, ok,
        f"debris reservoir {vol:.1f} ml >= {SCREEN_MIN_DEBRIS_ML:g}"
        if ok else
        f"debris reservoir {vol:.1f} ml < {SCREEN_MIN_DEBRIS_ML:g} — too shallow, "
        "deepen the basket or widen its footprint",
        measured=vol, limit=SCREEN_MIN_DEBRIS_ML,
    )


def check_collector_sump_is_lowest_point(form: PartForm) -> Finding:
    """VF-8: the strainer sump WELL floor is the collector's absolute low
    point (a real well below the tray floor) and the vertical drain descends
    from it, so all water reaches the drain. n/a with no strainer sump."""
    check = "form.collector_sump_is_lowest_point"
    sump = form.frame.get("screen_sump_floor_z")
    if sump is None:
        return _finding(check, True, "no strainer sump — n/a")
    tray = form.frame.get("screen_funnel_top_z")
    drain_ok = any(b.axis == "Z" and b.overshoot[0] > 0.0
                   and b.span[0] <= sump + 0.05 for b in form.bores)
    ok = tray is not None and sump < tray - 1.0 and drain_ok
    return _finding(
        check, ok,
        f"sump floor z={sump:.1f} sits {tray - sump:.1f} below the tray floor "
        "with the drain descending from it — the absolute low point"
        if ok else
        f"sump floor z={sump:.1f} is not a drained low point below the tray",
        measured=sump,
    )


def check_tray_floor_slopes_to_sump(form: PartForm) -> Finding:
    """VF-8: the tray floor slopes to the sump from every side — a converging
    funnel cut (wider opening than mouth, mouth over the drain). n/a with no
    strainer sump."""
    check = "form.tray_floor_slopes_to_sump"
    if form.frame.get("screen_sump_floor_z") is None:
        return _finding(check, True, "no strainer sump — n/a")
    if not form.funnel_cuts:
        return _finding(check, False, "strainer sump has no funnel feed")
    f = form.funnel_cuts[0]
    dy = form.frame.get("screen_seat_drain_y")
    x_slope = f.top[0] > f.bottom[0] + 1.0
    y_reaches = f.top[1] >= f.bottom[1] - 1e-6
    over_drain = dy is None or (
        f.bottom_center[1] - f.bottom[1] / 2.0 - 0.6 <= dy
        <= f.bottom_center[1] + f.bottom[1] / 2.0 + 0.6)
    ok = f.z_top > f.z_bottom and x_slope and y_reaches and over_drain
    return _finding(
        check, ok,
        f"funnel opening {f.top[0]:.0f}x{f.top[1]:.0f} converges to the "
        f"{f.bottom[0]:.0f}x{f.bottom[1]:.0f} mouth over the drain — floor slopes "
        "in from every side"
        if ok else "funnel does not converge to the drain from every side",
    )


def check_basket_not_transverse_flow_barrier(form: PartForm) -> Finding:
    """VF-8: the basket seats in a SUNKEN well fed by a funnel wider than the
    well mouth — water falls INTO it from every side rather than being walled
    off across the tray. Measured on the collector: funnel opening wider than
    the mouth, well recessed below the tray floor. n/a with no strainer sump."""
    check = "form.basket_not_transverse_flow_barrier"
    sump = form.frame.get("screen_sump_floor_z")
    if sump is None:
        return _finding(check, True, "no strainer sump — n/a")
    if not form.funnel_cuts:
        return _finding(check, False, "no funnel — a flat basket would wall the tray")
    f = form.funnel_cuts[0]
    tray = form.frame.get("screen_funnel_top_z")
    wider = f.top[0] >= f.bottom[0] + 4.0
    recessed = tray is not None and sump < tray - 1.0
    ok = wider and recessed
    return _finding(
        check, ok,
        f"basket sits in a well recessed {tray - sump:.1f} below the tray, fed "
        f"by a funnel {f.top[0]:.0f} wide vs the {f.bottom[0]:.0f} mouth — water "
        "falls in, not blocked"
        if ok else "basket would wall the tray flow, not sit in a fed well",
    )


def check_no_standing_water_before_screen(form: PartForm) -> Finding:
    """VF-8: nothing upstream of the sump holds water — the funnel descends
    monotonically to the drain and the sump is the collector low point, so the
    whole floor path reaches the screen. Complements no_standing_water_ir
    (which forbids blind pockets). n/a with no strainer sump."""
    check = "form.no_standing_water_before_screen"
    sump = form.frame.get("screen_sump_floor_z")
    if sump is None:
        return _finding(check, True, "no strainer sump — n/a")
    tray = form.frame.get("screen_funnel_top_z")
    dy = form.frame.get("screen_seat_drain_y")
    has_funnel = bool(form.funnel_cuts)
    over_drain = has_funnel and (dy is None or (
        form.funnel_cuts[0].bottom_center[1] - form.funnel_cuts[0].bottom[1] / 2.0 - 0.6
        <= dy <=
        form.funnel_cuts[0].bottom_center[1] + form.funnel_cuts[0].bottom[1] / 2.0 + 0.6))
    ok = has_funnel and over_drain and tray is not None and sump < tray - 1.0
    return _finding(
        check, ok,
        "the funnel descends monotonically to the drain at the sump low point — "
        "no water stands upstream of the screen"
        if ok else "the floor upstream of the sump could pool — no converging funnel",
    )


def check_lightweight_windows_dry_ok(form: PartForm) -> Finding:
    """The open-skeleton windows (VF-4.1): THROUGH the under-seat slab —
    open bottom (cannot hold water) AND open top (no flat ceiling, no
    bridges by construction) — and clear of every functional zone:
    channel, lap ends, profile-slot bands, wet regions. Trivially green
    with lightweight off."""
    f = form.frame
    wins = [c for c in form.cutboxes if "_lwin_" in c.name]
    if not f.get("lw_enabled", False) or not wins:
        return _finding("form.lightweight_windows_dry_ok", True,
                        "lightweight shell off — solid slab, nothing to prove")
    problems: list[str] = []
    seat_floor = f.get("seat_floor_z")
    ch_half = f.get("channel_w", 0.0) / 2.0
    px = f.get("profile_slot_x")
    pw = f.get("profile_slot_w", 0.0)
    y1 = f.get("rail_y1", 0.0)
    wet = _wet_regions(form)
    for win in wins:
        b = win.box
        if b.z0 > -0.5:
            problems.append(f"window {win.name!r} is not open-bottom")
        if seat_floor is not None and b.z1 < seat_floor - 0.05:
            problems.append(
                f"window {win.name!r} stops at z={b.z1:g} under the seat floor "
                f"{seat_floor:g} — a blind pocket with a bridged flat ceiling, "
                "not a through skeleton opening")
        if min(abs(b.x0), abs(b.x1)) < ch_half + 2.0 and b.x0 * b.x1 < 0:
            problems.append(f"window {win.name!r} crosses the channel band")
        elif min(abs(b.x0), abs(b.x1)) < ch_half + 2.0:
            problems.append(f"window {win.name!r} is closer than 2 to the channel wall")
        if px is not None and max(abs(b.x0), abs(b.x1)) > px - pw / 2.0 - 2.0:
            problems.append(f"window {win.name!r} enters the profile-slot band")
        if max(abs(b.y0), abs(b.y1)) > y1 - 10.0:
            problems.append(f"window {win.name!r} reaches into the lap/face end zone")
        for w in wet:
            if _boxes_overlap(b, w.box):
                problems.append(f"window {win.name!r} touches wet region {w.name!r}")
    # ribs: adjacent windows must not merge (their material gap >= LW_RIB_MIN)
    rib = f.get("lw_rib", 0.0)
    if rib < LW_RIB_MIN:
        problems.append(f"declared rib {rib:g} < {LW_RIB_MIN:g}")
    return _finding(
        "form.lightweight_windows_dry_ok", not problems,
        f"{len(wins)} through skeleton openings, ribs {rib:g} — no bridges "
        "by construction; the cassette covers, the profile carries"
        if not problems else "; ".join(problems),
        measured=f.get("lw_span_max", 0.0),
    )



register_probe("form.water_channel_constant_depth_ok")(
    lambda form, ctx: check_water_channel_constant_depth_ok(form))
register_probe("form.water_channel_dims_ok")(
    lambda form, ctx: check_water_channel_dims_ok(form))
register_probe("form.no_standing_water_ir")(
    lambda form, ctx: check_no_standing_water_ir(form))
register_probe("form.lap_joint_geometry_ok")(
    lambda form, ctx: check_lap_joint_geometry_ok(form))
register_probe("form.lap_slot_leak_path_controlled")(
    lambda form, ctx: check_lap_slot_leak_path_controlled(form))
register_probe("form.lap_receiver_has_floor")(
    lambda form, ctx: check_lap_receiver_has_floor(form))
register_probe("form.lap_receiver_residual_volume_ok")(
    lambda form, ctx: check_lap_receiver_residual_volume_ok(form))
register_probe("form.rail_universal_inlet_accepts_cap_and_lap")(
    lambda form, ctx: check_rail_universal_inlet_accepts_cap_and_lap(form))
register_probe("form.drainage_requires_mount")(
    lambda form, ctx: check_drainage_requires_mount(form))
register_probe("form.magnet_pockets_outside_water_zone")(
    lambda form, ctx: check_magnet_pockets_outside_water_zone(form))
register_probe("form.magnet_pockets_do_not_break_wall")(
    lambda form, ctx: check_magnet_pockets_do_not_break_wall(form))
register_probe("form.dock_pockets_dry")(
    lambda form, ctx: check_dock_pockets_dry(form))
register_probe("form.screen_open_area_ratio_ok")(
    lambda form, ctx: check_screen_open_area_ratio_ok(form))
register_probe("form.screen_debris_capacity_ok")(
    lambda form, ctx: check_screen_debris_capacity_ok(form))
register_probe("form.collector_sump_is_lowest_point")(
    lambda form, ctx: check_collector_sump_is_lowest_point(form))
register_probe("form.tray_floor_slopes_to_sump")(
    lambda form, ctx: check_tray_floor_slopes_to_sump(form))
register_probe("form.basket_not_transverse_flow_barrier")(
    lambda form, ctx: check_basket_not_transverse_flow_barrier(form))
register_probe("form.no_standing_water_before_screen")(
    lambda form, ctx: check_no_standing_water_before_screen(form))
register_probe("form.lightweight_windows_dry_ok")(
    lambda form, ctx: check_lightweight_windows_dry_ok(form))
