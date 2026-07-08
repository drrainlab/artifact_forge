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
LW_COVER_MIN = 2.4  # lightweight window roof under the seat floor
LW_RIB_MIN = 1.8
LW_SPAN_WARN = 45.0  # bridge span over a window ceiling worth flagging


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


def check_lap_joint_geometry_ok(form: PartForm) -> Finding:
    """The flush handover pair on one rail: a lip that CONTINUES the
    channel floor plane (top at floor level — anything higher is a dam,
    anything lower a step) and a THROUGH open-bottom receiver the
    neighbour's identical lip lands in, with a deliberate slot left open
    at the tip."""
    f = form.frame
    keys = ("lap_lip_len", "lap_lip_w", "lap_lip_t", "lap_lip_top_z",
            "lap_pocket_len", "lap_pocket_w", "face_gap",
            "channel_floor_z_inlet", "channel_floor_z_outlet")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.lap_joint_geometry_ok", False,
                        f"no lap frame keys: {', '.join(missing)}")
    problems: list[str] = []
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
    pocket = next((c for c in form.cutboxes if "lap_receiver" in c.name), None)
    if pocket is None:
        problems.append("no lap receiver cut on the part")
    else:
        b = pocket.box
        if b.z0 > -0.5:
            problems.append(
                f"receiver floors at z={b.z0:g} — it must cut THROUGH the body "
                "(an open bottom is the whole no-sump guarantee)")
        if b.z1 < f["channel_floor_z_inlet"] - CONST_DEPTH_TOL:
            problems.append("receiver stops short of the floor plane — the lip cannot land")
        side = (f["lap_pocket_w"] - f["lap_lip_w"]) / 2.0
        if not (LAP_SIDE_CLEAR_BAND[0] <= side <= LAP_SIDE_CLEAR_BAND[1]):
            problems.append(
                f"per-side lip clearance {side:.2f} outside "
                f"{LAP_SIDE_CLEAR_BAND[0]}..{LAP_SIDE_CLEAR_BAND[1]}")
    overlap = f["lap_lip_len"] - f["face_gap"]
    slot = f["lap_pocket_len"] - overlap
    if not (LAP_SLOT_BAND[0] <= slot <= LAP_SLOT_BAND[1]):
        problems.append(
            f"tip slot {slot:.2f} outside {LAP_SLOT_BAND[0]}..{LAP_SLOT_BAND[1]} — "
            "the seam must stay deliberately open, and only just")
    if not (FACE_GAP_BAND[0] <= f["face_gap"] <= FACE_GAP_BAND[1]):
        problems.append(f"face gap {f['face_gap']:g} outside "
                        f"{FACE_GAP_BAND[0]}..{FACE_GAP_BAND[1]}")
    return _finding(
        "form.lap_joint_geometry_ok", not problems,
        f"lip continues the floor plane {f['lap_lip_len']:g} past the face; "
        f"the receiver is through with a {slot:.1f} open slot at the tip"
        if not problems else "; ".join(problems),
        measured=slot, limit=LAP_SLOT_BAND[1],
    )


def check_lap_slot_leak_path_controlled(form: PartForm) -> Finding:
    """The deliberate seam slot must leak into KNOWN air: straight down
    through the open-bottom receiver, laterally far from the profile slots,
    magnet pockets and dry zones. The nominal stream crosses ON TOP of the
    lip; this check pins down where the stray drops go."""
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
        if b.z0 > -0.5:
            problems.append("receiver is not open-bottom — drips would pool, not fall")
        # nothing of the rail may sit under the slot footprint
        for cut in form.cutboxes:
            if cut is pocket:
                continue
            if cut.box.z1 <= 0.0 and _boxes_overlap(cut.box, b):
                problems.append(f"feature {cut.name!r} sits under the slot footprint")
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
        "seam drips fall through open air between the profiles — clear of "
        "aluminum, magnets and dry zones (leak: controlled, visible, cleanable)"
        if not problems else "; ".join(problems),
        limit=LAP_LATERAL_CLEAR_MIN,
    )


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
    for b in pockets:
        blind = b.overshoot[0] <= 0.0 or b.overshoot[1] <= 0.0
        if not blind:
            problems.append(f"magnet pocket {b.name!r} is a through bore")
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


def check_lightweight_windows_dry_ok(form: PartForm) -> Finding:
    """The dry-shell windows: open-bottom (cannot hold water), a solid roof
    >= LW_COVER_MIN under the seat floor, ribs left between them, and clear
    of every functional zone — channel, lap ends, profile-slot bands,
    magnet pockets, wet regions. Trivially green with lightweight off."""
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
        if seat_floor is not None and b.z1 > seat_floor - LW_COVER_MIN + 0.01:
            problems.append(
                f"window {win.name!r} roof leaves < {LW_COVER_MIN:g} under the seat floor")
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
    span = f.get("lw_span_max", 0.0)
    note = ""
    if span > LW_SPAN_WARN:
        note = f" (note: {span:.0f} bridge over a window ceiling — expect sag on FDM)"
    return _finding(
        "form.lightweight_windows_dry_ok", not problems,
        f"{len(wins)} open-bottom dry windows, roof >= {LW_COVER_MIN:g}, "
        f"ribs {rib:g} — the profile carries, the plastic positions" + note
        if not problems else "; ".join(problems),
        measured=span,
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
register_probe("form.drainage_requires_mount")(
    lambda form, ctx: check_drainage_requires_mount(form))
register_probe("form.magnet_pockets_outside_water_zone")(
    lambda form, ctx: check_magnet_pockets_outside_water_zone(form))
register_probe("form.magnet_pockets_do_not_break_wall")(
    lambda form, ctx: check_magnet_pockets_do_not_break_wall(form))
register_probe("form.lightweight_windows_dry_ok")(
    lambda form, ctx: check_lightweight_windows_dry_ok(form))
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
