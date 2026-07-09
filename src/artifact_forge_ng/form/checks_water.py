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
#: MOUNT_SLOPE_BAND is the operational band the mounted row must sit at —
#: the rail itself is level (constant depth); the mount supplies the fall.
MOUNT_SLOPE_BAND = (1.0, 2.0)  # degrees, mount_context
CONST_DEPTH_TOL = 0.05  # channel floor level end to end
CHANNEL_D_BAND = (4.0, 8.0)
CHANNEL_W_BAND = (12.0, 20.0)
BOTTOM_R_BAND = (0.8, 2.0)
FLOOR_MARGIN_MIN = 2.0  # material below the deepest floor point
SEAT_CLEARANCE_BAND = (0.5, 1.0)
TG_SIDE_CLEARANCE_BAND = (0.3, 0.5)  # tongue/groove per-side
TG_BOTTOM_MARGIN = 0.3  # tongue never bottoms in the groove
# -- lap-flow handover bands (VF correction) ----------------------------------
LAP_LIP_LEN_BAND = (3.0, 6.0)  # lip protrusion past the face
LAP_LIP_T_BAND = (1.2, 1.6)
LAP_SIDE_CLEAR_BAND = (0.3, 0.5)  # lip in the receiver, per side
LAP_SLOT_BAND = (0.5, 2.5)  # deliberate open slot at the lip tip
FACE_GAP_BAND = (0.3, 0.6)  # controlled flush face gap
LAP_LATERAL_CLEAR_MIN = 40.0  # slot drips stay this far from dry hardware
MAGNET_WET_WALL_MIN = 1.2  # plastic between a magnet pocket and any water
MAGNET_FIT_BAND = (0.1, 0.3)  # diametral press-fit — pushes in, stays put
LW_RIB_MIN = 1.8
CASSETTE_COVER = 4.0  # every skeleton opening hides this far under the seat
CASSETTE_SPAN_MAX = 45.0  # worst unsupported span under the cassette floor


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


def _pocket_drained_by_through_bore(box, bores) -> bool:
    """A floored pocket does NOT pool if a vertical open-bottom bore passes
    through its footprint down to (or below) the pocket floor: the floor has
    a drain hole in it, so water leaves through the underside. This is the
    strainer-seat recess sitting directly over the collector's vertical drain
    (VF-8) — the recess floor carries the drain bore straight to the bottom."""
    for bore in bores:
        if bore.axis != "Z" or bore.overshoot[0] <= 0.0:
            continue  # only a downward-open (through-to-underside) Z bore drains
        if bore.span[0] > box.z0 + 0.05:
            continue  # the bore does not reach down to the pocket floor
        bx, by = bore.center[0], bore.center[1]
        if (box.x0 - 0.05 <= bx <= box.x1 + 0.05
                and box.y0 - 0.05 <= by <= box.y1 + 0.05):
            return True
    return False


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


def check_cassette_support_span_ok(form: PartForm) -> Finding:
    """The cassette must not sag over the open skeleton (VF-4.1): every
    window hides FULLY under the cassette seat footprint (>= CASSETTE_COVER
    margin inside — the cassette covers each opening), the support grid
    survives around them (perimeter ring + channel spine + ribs), and the
    worst unsupported span under the cassette floor stays in band.
    Trivially green with lightweight off."""
    f = form.frame
    wins = [c for c in form.cutboxes if "_lwin_" in c.name]
    troughs = [c for c in form.channels if "root_trough" in c.name]
    if troughs:
        # root chamber: the cassette spans the open-top troughs; each must
        # be no wider than the support span, with a rib between them
        problems: list[str] = []
        tw = f.get("root_trough_w", 0.0)
        if tw > CASSETTE_SPAN_MAX:
            problems.append(
                f"root trough {tw:g} wide > {CASSETTE_SPAN_MAX:g} — the cassette "
                "sags between the ribs")
        if f.get("root_trough_rib", 0.0) < LW_RIB_MIN:
            problems.append("root trough ribs too thin to carry the cassette")
        return _finding(
            "form.cassette_support_span_ok", not problems,
            f"{len(troughs)} root troughs, {tw:g} wide on {f.get('root_trough_rib',0):g} "
            "ribs — the cassette spans them stiffly"
            if not problems else "; ".join(problems),
            measured=tw, limit=CASSETTE_SPAN_MAX)
    if not f.get("lw_enabled", False) or not wins:
        return _finding("form.cassette_support_span_ok", True,
                        "solid slab under the cassette — full support")
    keys = ("seat_u0", "seat_v0", "seat_u1", "seat_v1", "channel_w", "lw_rib")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.cassette_support_span_ok", False,
                        f"no frame keys: {', '.join(missing)}")
    problems: list[str] = []
    worst = 0.0
    for win in wins:
        b = win.box
        # band edges are LEGAL: window layouts computed from the same seat
        # numbers land EXACTLY on the margin line — never fail float dust
        eps = 0.01
        if (b.x0 < f["seat_u0"] + CASSETTE_COVER - eps
                or b.x1 > f["seat_u1"] - CASSETTE_COVER + eps
                or b.y0 < f["seat_v0"] + CASSETTE_COVER - eps
                or b.y1 > f["seat_v1"] - CASSETTE_COVER + eps):
            problems.append(
                f"window {win.name!r} pokes out from under the cassette seat "
                f"(needs >= {CASSETTE_COVER:g} inside the footprint)")
        span = min(b.x1 - b.x0, b.y1 - b.y0)
        worst = max(worst, span)
        if span > CASSETTE_SPAN_MAX:
            problems.append(
                f"window {win.name!r} leaves a {span:.1f} unsupported span "
                f"under the cassette (max {CASSETTE_SPAN_MAX:g})")
    # the support grid: no two windows may merge (rib survives between them)
    for i in range(len(wins)):
        for j in range(i + 1, len(wins)):
            a, b = wins[i].box, wins[j].box
            gap_x = max(a.x0, b.x0) - min(a.x1, b.x1)
            gap_y = max(a.y0, b.y0) - min(a.y1, b.y1)
            if max(gap_x, gap_y) < f["lw_rib"] - 0.2:
                problems.append(
                    f"windows {wins[i].name!r}/{wins[j].name!r} merge — the "
                    "support rib between them is gone")
    # the channel spine: openings never cross the channel band (the spine
    # under the cassette's contact window is always solid)
    ch_half = f["channel_w"] / 2.0
    for win in wins:
        if win.box.x0 < ch_half and win.box.x1 > -ch_half:
            problems.append(f"window {win.name!r} eats the channel spine")
    return _finding(
        "form.cassette_support_span_ok", not problems,
        f"{len(wins)} openings fully under the cassette; worst unsupported "
        f"span {worst:.1f} <= {CASSETTE_SPAN_MAX:g} on the ring + spine + rib "
        "grid (the 2 mm cassette floor with its mesh spans this stiffly; "
        "channel-zone reinforcement arrives with VF-5 cassettes)"
        if not problems else "; ".join(problems),
        measured=worst, limit=CASSETTE_SPAN_MAX,
    )


def check_no_secondary_water_channel(form: PartForm) -> Finding:
    if form.channels:
        problems: list[str] = []
        # The rail owns exactly ONE transient pulse channel. Root-drainage
        # troughs (VF-5 root chamber) are a DIFFERENT, legalized subsystem
        # (passive_root_drainage_return) — level, mount-drained, named
        # *_root_trough_* — and do not count as a second pulse channel.
        pulse = [c for c in form.channels if "root_trough" not in c.name]
        if len(pulse) != 1:
            problems.append(f"{len(pulse)} pulse water channels declared — the rail owns exactly one")
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
def check_root_chamber_ok(form: PartForm) -> Finding:
    """VF-5 root chamber: the open-top troughs form a valid, cleanable,
    self-draining root zone. Level const-depth (the MOUNT drains them, no
    geometry slope), running the FULL length so they exit both faces (a
    guaranteed forward exit under the mount, and they chain module-to-
    module to the collector), a solid blind bottom below for containment,
    and clear of the pulse channel spine. n/a-PASS when not a root
    chamber."""
    check = "form.root_chamber_ok"
    troughs = [c for c in form.channels if "root_trough" in c.name]
    if not troughs:
        return _finding(check, True, "no root chamber on this part — n/a")
    f = form.frame
    problems: list[str] = []
    y0, y1 = f.get("rail_y0"), f.get("rail_y1")
    ch_half = f.get("channel_w", 0.0) / 2.0
    floor_z = f.get("root_trough_floor_z")
    for c in troughs:
        if abs(c.depth_end - c.depth_start) > CONST_DEPTH_TOL:
            problems.append(
                f"{c.name!r} is not level — the mount drains the troughs, "
                "geometry slope is the old cascade")
        # full length: spans both faces so it drains forward under the mount
        lo, hi = min(c.y0, c.y1), max(c.y0, c.y1)
        if y0 is not None and (lo > y0 + 0.01 or hi < y1 - 0.01):
            problems.append(
                f"{c.name!r} does not span both faces — no guaranteed forward "
                "exit / module-to-module chaining")
        # clear of the pulse channel spine
        if abs(c.center_x) - c.width / 2.0 < ch_half + 2.0:
            problems.append(f"{c.name!r} eats into the channel spine")
    # blind containment bottom below the troughs
    if floor_z is None:
        problems.append("no root_trough_floor_z — blind bottom unproven")
    elif floor_z < FLOOR_MARGIN_MIN:
        problems.append(
            f"only {floor_z:g} solid below the troughs (needs >= "
            f"{FLOOR_MARGIN_MIN:g}) — the containment bottom is too thin")
    return _finding(
        check, not problems,
        f"{len(troughs)} level open-top root troughs over a {floor_z:g} blind "
        "bottom — roots grow in, the mount drains them forward, brush-open "
        "after the cassette lifts"
        if not problems else "; ".join(problems),
        measured=floor_z, limit=FLOOR_MARGIN_MIN,
    )


register_probe("form.root_chamber_ok")(
    lambda form, ctx: check_root_chamber_ok(form))
register_probe("form.cassette_support_span_ok")(
    lambda form, ctx: check_cassette_support_span_ok(form))
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
#: Collector U-frame side wall — thick enough to carry the cantilever, not
#: a thin molded skin column (VF-4.2).
COLLECTOR_WALL_MIN = 3.5
#: The side walls must MERGE with the hanging arm over a real overlap, not
#: a thin weld line that carries the whole cantilever on a glue seam.
COLLECTOR_ARM_WELD_MIN = 3.0


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
    spout = [r for r in form.ribs if "spout" in r.name or "nose" in r.name]
    if not spout:
        problems.append("no spout/nose rib on the part")
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
register_probe("form.spout_drop_path_ok")(
    lambda form, ctx: check_spout_drop_path_ok(form))

# -- VF-4.1: the collector is an END RECEIVER, not a part standing nearby ----

RECEIVER_CAPTURE_BAND = (6.0, 8.0)
RECEIVER_SIDE_MARGIN = 1.4  # mouth over lip, per side
RECEIVER_APRON_BAND = (2.4, 3.5)  # a low curb over the handover plane
RECEIVER_TIP_MARGIN = 2.0  # lip tip to the apron wall
RECEIVER_LIFT_WINDOW = 15.0  # clear vertical exit over the captured lip


def _receiver_keys(form: PartForm):
    keys = ("receiver_mouth_w", "receiver_capture_depth", "receiver_apron_z",
            "receiver_cheek_x0", "receiver_lip_overhang", "receiver_lip_w",
            "handover_dz")
    missing = [k for k in keys if k not in form.frame]
    return missing


def check_collector_receiver_matches_final_lap(form: PartForm) -> Finding:
    """The mouth is built FOR the final lap lip: wide enough to envelope
    it, deep enough to capture the tip with margin to the apron, the apron
    high enough that runoff drops cannot escape."""
    check = "form.collector_receiver_matches_final_lap"
    missing = _receiver_keys(form)
    if missing:
        return _finding(check, False, f"no receiver frame keys: {', '.join(missing)}")
    f = form.frame
    problems: list[str] = []
    if f["receiver_mouth_w"] < f["receiver_lip_w"] + 2.0 * RECEIVER_SIDE_MARGIN:
        problems.append(
            f"mouth {f['receiver_mouth_w']:g} does not envelope the "
            f"{f['receiver_lip_w']:g} lip with {RECEIVER_SIDE_MARGIN:g}/side")
    cd = f["receiver_capture_depth"]
    if not (RECEIVER_CAPTURE_BAND[0] - 1e-9 <= cd <= RECEIVER_CAPTURE_BAND[1] + 1e-9):
        problems.append(
            f"capture depth {cd:g} outside "
            f"{RECEIVER_CAPTURE_BAND[0]}..{RECEIVER_CAPTURE_BAND[1]}")
    if cd - f["receiver_lip_overhang"] < RECEIVER_TIP_MARGIN - 1e-9:
        problems.append(
            f"lip tip lands {cd - f['receiver_lip_overhang']:g} from the apron "
            f"(needs >= {RECEIVER_TIP_MARGIN:g})")
    if f["receiver_apron_z"] < RECEIVER_APRON_BAND[0] - 1e-9:
        problems.append(
            f"apron top {f['receiver_apron_z']:g} above the handover plane is "
            f"below {RECEIVER_APRON_BAND[0]:g} — runoff drops can escape the mouth")
    cheeks = [r for r in form.ribs if "cheek" in r.name]
    if len(cheeks) != 2:
        problems.append(f"{len(cheeks)} cheek rib(s) — the wet zone needs both flanks")
    elif abs(abs(cheeks[0].box.x0 + cheeks[0].box.x1)
             - abs(cheeks[1].box.x0 + cheeks[1].box.x1)) > 0.2:
        problems.append("cheeks are not symmetric about the lip centerline")
    return _finding(
        check, not problems,
        f"end receiver: mouth {f['receiver_mouth_w']:g} over the "
        f"{f['receiver_lip_w']:g} lip, capture {cd:g} with "
        f"{cd - f['receiver_lip_overhang']:g} tip margin, apron at "
        f"{f['receiver_apron_z']:g}"
        if not problems else "; ".join(problems),
        measured=cd, limit=RECEIVER_CAPTURE_BAND[1],
    )


def check_receiver_open_top_cleanable(form: PartForm) -> Finding:
    """Capture is worthless if it breeds biofilm: the capture zone is open
    to the sky (a brush and an eye enter from above), the apron is a low
    curb — never a wall walling off a blind slot — and the zone flows
    straight into the open tray (a falling drop's path IS the brush path)."""
    check = "form.receiver_open_top_cleanable"
    missing = _receiver_keys(form)
    if missing:
        return _finding(check, False, f"no receiver frame keys: {', '.join(missing)}")
    f = form.frame
    dz = f["handover_dz"]
    cheek_x0 = f["receiver_cheek_x0"]
    cd = f["receiver_capture_depth"]
    problems: list[str] = []
    # (a) open top: within the lift window no collector material hangs
    # over the capture footprint between the cheeks
    footprint = Box3(-cheek_x0 + 0.05, -cd, dz + 1.6,
                     cheek_x0 - 0.05, -0.05, dz + RECEIVER_LIFT_WINDOW)
    for feat in list(form.ribs) + list(form.plates):
        fb = getattr(feat, "box", None)
        if fb is None:
            b = feat  # PlateFeature has explicit coords
            fb = Box3(b.x0, b.y0, b.z_bottom, b.x1, b.y1, b.z_bottom + b.thickness)
        if _boxes_overlap(fb, footprint):
            problems.append(
                f"{feat.name!r} roofs the capture zone — no ceiling over the "
                "mouth, ever")
    # (b) the apron is a curb, not a wall
    if f["receiver_apron_z"] > RECEIVER_APRON_BAND[1] + 1e-9:
        problems.append(
            f"apron {f['receiver_apron_z']:g} over the handover plane rises "
            f"past {RECEIVER_APRON_BAND[1]:g} — a deep narrow slot collects "
            "coco and biofilm a brush cannot reach")
    # (c) continuity: nothing blocks the tray void between the capture
    # zone and the drain end below the rim
    if form.channels:
        tray = form.channels[0]
        void = Box3(-tray.width / 2.0 + 0.05, tray.y1 + 0.1, dz - 2.0,
                    tray.width / 2.0 - 0.05, tray.y0 - 0.1,
                    f["receiver_apron_z"] + dz - 0.1)
        for feat in form.ribs:
            if _boxes_overlap(feat.box, void):
                problems.append(
                    f"{feat.name!r} walls the receiver off from the open tray")
    side = (f["receiver_mouth_w"] - f["receiver_lip_w"]) / 2.0
    return _finding(
        check, not problems,
        f"open-top receiver: {side:.1f}/side around the lip, curb apron "
        f"{f['receiver_apron_z']:g}, capture zone continuous with the "
        f"{form.channels[0].width if form.channels else 0:g}-wide open tray "
        "(brush >= d8 enters wherever a drop falls)"
        if not problems else "; ".join(problems),
        measured=side,
    )


def check_collector_drain_bore_supportless(form: PartForm) -> Finding:
    """The drain prints without support: vertical, or teardrop-roofed on a
    horizontal run."""
    check = "form.collector_drain_bore_supportless"
    drains = [b for b in form.bores if "drain" in b.name]
    if not drains:
        return _finding(check, False, "no drain bore on the collector")
    problems = [
        f"drain {b.name!r} d{b.d:g} is a horizontal circle — it sags on FDM"
        for b in drains
        if b.axis in ("X", "Y") and b.roof != "teardrop"
    ]
    return _finding(
        check, not problems,
        "drain prints supportless (vertical or teardrop-roofed)"
        if not problems else "; ".join(problems),
        suggestion="" if not problems else 'BoreFeature(roof="teardrop")',
    )


register_probe("form.collector_receiver_matches_final_lap")(
    lambda form, ctx: check_collector_receiver_matches_final_lap(form))
register_probe("form.receiver_open_top_cleanable")(
    lambda form, ctx: check_receiver_open_top_cleanable(form))
register_probe("form.collector_drain_bore_supportless")(
    lambda form, ctx: check_collector_drain_bore_supportless(form))
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
