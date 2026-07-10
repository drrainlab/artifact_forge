"""Vertical-farm water rail ops — rail body, lap outlet lip, lap inlet
receiver (VF-9 floored lip-seat).
"""
from __future__ import annotations

from typing import Any
from ..product.archetype import RegionRole
from .profiles_plate import rounded_rect_loop
from .regions import Box3, Region
from .section import SectionProfile
from .part import ChannelCutFeature, CutBoxFeature, RibFeature
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .recipe_ops_water_common import FLOOR_MARGIN_MIN, CORRIDOR_MARGIN, FALL_ENTRY, DRIP_INSET


# -- water_rail_body (base) ---------------------------------------------------


def _water_rail_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The Base Water Rail (tilted flush row canon): a level plan-view body
    carrying a recessed cassette seat and a CONSTANT-DEPTH open U-channel
    cut from the SEAT FLOOR. The rail itself is horizontal end to end — the
    drainage slope comes from MOUNTING the whole row on a straight aluminum
    profile at 1.0–2.0 deg (mount_context), never from the geometry. Flow
    axis Y: inlet at the back (+Y), outlet at the front (-Y). Corridor
    notches open the channel to the sky through both seat walls, so the
    whole run is brush-reachable.

    Lightweight open skeleton (param-gated, reversible): the rail is a dry
    frame around a protected water core, not a slab — large smooth windows
    cut THROUGH the under-seat slab (open bottom AND top: no bridges by
    construction), leaving the perimeter ring, the channel spine, the
    profile bands and the lw_rib grid. The cassette covers every opening
    and rests on the ring + ribs. The profile carries the row; plastic
    pays only for water, cassette and positioning. Never honeycomb — big
    cleanable openings only."""
    if state.section is not None:
        raise RecipeError("water_rail_body must be the (single) base op")
    l, w, h = p["module_l"], p["module_w"], p["body_h"]
    ch_w, ch_d = p["channel_w"], p["channel_d"]
    bottom_r = p["channel_bottom_r"]
    cassette_l, cassette_w = p["cassette_l"], p["cassette_w"]
    seat_depth, clearance = p["seat_depth"], p["seat_clearance"]
    pitch = p["module_pitch"]
    face_gap = p.get("face_gap", 0.4)

    seat_floor = h - seat_depth
    floor_margin = seat_floor - ch_d
    if floor_margin < FLOOR_MARGIN_MIN:
        raise RecipeError(
            f"channel floor would leave only {floor_margin:.1f} beneath it "
            f"(needs >= {FLOOR_MARGIN_MIN:g}) — raise body_h or shrink seat_depth/channel_d")
    if not (0.3 - 1e-9 <= face_gap <= 0.6 + 1e-9):
        raise RecipeError(
            f"face_gap {face_gap:g} outside the controlled flush band 0.3..0.6")
    seat_l = cassette_l + 2.0 * clearance
    seat_w = cassette_w + 2.0 * clearance
    if seat_l + 16.0 > l or seat_w + 16.0 > w:
        raise RecipeError("cassette seat leaves no rail wall — shrink the cassette")

    u0, v0, u1, v1 = -l / 2.0, -w / 2.0, l / 2.0, w / 2.0
    state.section = SectionProfile(
        name="recipe", outer=rounded_rect_loop(u0, v0, u1, v1, p["corner_r"]),
        plane="XY", width_axis="Z",
    )
    state.width = h
    name = op_id or "rail"
    floor_z = seat_floor - ch_d

    state.channels.append(ChannelCutFeature(
        name=f"{name}_water", center_x=0.0,
        y0=v1, y1=v0, z_top=seat_floor,
        width=ch_w, depth_start=ch_d, depth_end=ch_d, bottom_r=bottom_r,
    ))
    state.cutboxes.append(CutBoxFeature(
        name=f"{name}_seat",
        box=Box3(-seat_l / 2.0, -seat_w / 2.0, seat_floor,
                 seat_l / 2.0, seat_w / 2.0, h + 1.0),
    ))
    corridor_half = ch_w / 2.0 + CORRIDOR_MARGIN
    state.cutboxes.append(CutBoxFeature(
        name=f"{name}_corridor_out",
        box=Box3(-corridor_half, v0 - 0.5, seat_floor, corridor_half, -seat_w / 2.0 + 1.0, h + 1.0),
    ))
    state.cutboxes.append(CutBoxFeature(
        name=f"{name}_corridor_in",
        box=Box3(-corridor_half, seat_w / 2.0 - 1.0, seat_floor, corridor_half, v1 + 0.5, h + 1.0),
    ))

    state.regions.extend([
        Region("water_channel", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-ch_w / 2.0, v0, floor_z - 0.5,
                    ch_w / 2.0, v1, seat_floor)),
        Region("cassette_seat_walls", RegionRole.INTERFACE_KEEPOUT,
               Box3(-seat_l / 2.0 - 4.0, -seat_w / 2.0 - 4.0, seat_floor,
                    seat_l / 2.0 + 4.0, seat_w / 2.0 + 4.0, h)),
        Region("dry_zone_back", RegionRole.MOUNTING_SURFACE,
               Box3(corridor_half + 4.0, seat_w / 2.0 + 1.0, 0.0, u1 - 4.0, v1, h)),
    ])

    # -- under-cassette volume: skeleton (VF-4.1) | root_chamber (VF-5) -----
    # skeleton = open through-windows, -45% plastic, but overflow drips
    #   straight through (uncontained; see overflow_containment report).
    # root_chamber = SOLID blind bottom (contains overflow) with open-top
    #   root troughs cut into it. The troughs are LEVEL const-depth grooves
    #   running front-back — the MOUNT drains them forward, exactly like the
    #   main channel — so roots grow in and water leaves without any
    #   geometry slope. A separate, legalized subsystem
    #   (passive_root_drainage_return), never the pulse path.
    under = p.get("under_cassette", "skeleton")
    lw = bool(p.get("lightweight", True)) and under == "skeleton"
    lw_rib = p.get("lw_rib", 2.0)
    lw_windows = 0
    lw_span_max = 0.0
    root_troughs = 0
    profile_size = 20.0 if p.get("profile", "2020") == "2020" else 30.0
    slot_half = (profile_size + 2.0 * 0.5) / 2.0  # worst-case clearance
    x_in = ch_w / 2.0 + 4.0                        # channel + 2 clear + 2 wall
    x_out = u1 - p.get("profile_inset", 24.0) - slot_half - 2.4
    y_lim = min(w / 2.0 - 12.0, seat_w / 2.0 - 4.0)
    if lw and x_out - x_in >= 24.0 and y_lim >= 40.0:
        # windows must hide fully UNDER the cassette seat (>= 4 inside its
        # footprint): a through cut past the seat edge would gnaw the seat
        # wall base — and would poke out from under the cassette
        n_cols, n_rows = 2, 5
        col_w = (x_out - x_in - (n_cols - 1) * lw_rib) / n_cols
        row_l = (2.0 * y_lim - (n_rows - 1) * lw_rib) / n_rows
        lw_span_max = max(col_w, row_l)
        for side in (1.0, -1.0):
            for ci in range(n_cols):
                cx0 = x_in + ci * (col_w + lw_rib)
                for ri in range(n_rows):
                    ry0 = -y_lim + ri * (row_l + lw_rib)
                    state.cutboxes.append(CutBoxFeature(
                        name=f"{name}_lwin_{'e' if side > 0 else 'w'}{ci}{ri}",
                        box=Box3(min(side * cx0, side * (cx0 + col_w)), ry0, -1.0,
                                 max(side * cx0, side * (cx0 + col_w)), ry0 + row_l,
                                 seat_floor + 0.5),
                    ))
                    lw_windows += 1
    elif under == "root_chamber" and x_out - x_in >= 24.0:
        # open-top root troughs: LEVEL const-depth grooves cut from the seat
        # floor down, running the full length (exit both faces so the mount
        # drains them forward and they chain module->module to the
        # collector). The solid below (z0..trough_floor) is the blind
        # containment bottom.
        trough_w = p.get("trough_w", 26.0)
        trough_rib = p.get("trough_rib", 6.0)
        trough_d = p.get("trough_depth", 12.0)
        trough_floor = seat_floor - trough_d
        n_t = max(1, int((x_out - x_in + trough_rib) // (trough_w + trough_rib)))
        used = n_t * trough_w + (n_t - 1) * trough_rib
        x0 = x_in + (x_out - x_in - used) / 2.0  # centre the troughs in the band
        for side in (1.0, -1.0):
            for ti in range(n_t):
                cx = side * (x0 + ti * (trough_w + trough_rib) + trough_w / 2.0)
                state.channels.append(ChannelCutFeature(
                    name=f"{name}_root_trough_{'e' if side > 0 else 'w'}{ti}",
                    center_x=cx, y0=v1, y1=v0, z_top=seat_floor,
                    width=trough_w, depth_start=trough_d, depth_end=trough_d,
                    bottom_r=1.5,
                ))
                state.regions.append(Region(
                    f"root_trough_{'e' if side > 0 else 'w'}{ti}",
                    RegionRole.TRANSIENT_WATER_PATH,
                    Box3(cx - trough_w / 2.0, v0, trough_floor - 0.5,
                         cx + trough_w / 2.0, v1, seat_floor)))
                root_troughs += 1
        state.frame.update(
            root_trough_count=root_troughs, root_trough_w=trough_w,
            root_trough_floor_z=trough_floor, root_blind_bottom_z=trough_floor,
            root_trough_rib=trough_rib,
            root_trough_x_max=x0 + used,  # outermost trough edge
        )

    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=p["corner_r"],
        rail_x0=u0, rail_x1=u1, rail_y0=v0, rail_y1=v1, body_h=h,
        channel_center_x=0.0, channel_w=ch_w, channel_bottom_r=bottom_r,
        channel_top_z=seat_floor,
        channel_y_inlet=v1, channel_y_outlet=v0,
        channel_floor_z_inlet=floor_z,
        channel_floor_z_outlet=floor_z,
        channel_slope_deg=0.0, channel_floor_margin=floor_margin,
        corridor_w=2.0 * corridor_half,
        seat_u0=-seat_l / 2.0, seat_v0=-seat_w / 2.0,
        seat_u1=seat_l / 2.0, seat_v1=seat_w / 2.0,
        seat_floor_z=seat_floor, seat_depth=seat_depth, seat_clearance=clearance,
        module_pitch=pitch,
        face_gap=face_gap, flush_pitch=w + face_gap,
        lw_enabled=lw, lw_window_count=lw_windows,
        lw_rib=lw_rib, lw_span_max=lw_span_max,
    )
    state.datums["cassette_seat"] = {"at": [0.0, 0.0, seat_floor], "rotate": [0.0, 0.0, 0.0]}
    state.datums["module_origin"] = {"at": [0.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]}
    state.datums["line_east"] = {"at": [u1, 0.0, h / 2.0], "rotate": [0.0, 0.0, 0.0]}
    state.datums["line_west"] = {"at": [u0, 0.0, h / 2.0], "rotate": [0.0, 0.0, 0.0]}
    # Flush fluid datums: inlet/outlet sit ON the channel floor plane,
    # face_gap/2 OUTSIDE each face — mating outlet-on-inlet lands the
    # neighbour at dZ = 0 and dY = module_w + face_gap (the flush pitch).
    # The water crosses over the lap lip; nothing falls between modules.
    state.datums["inlet"] = {
        "at": [0.0, v1 + face_gap / 2.0, floor_z],
        "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["outlet"] = {
        "at": [0.0, v0 - face_gap / 2.0, floor_z],
        "rotate": [0.0, 0.0, 0.0],
    }
    # The feed datum keeps the ONLY fall in the corrected row: the inlet
    # cap's chute tip targets this point, FALL_ENTRY above the floor and
    # DRIP_INSET inboard of the face (VF-9.2 — the drip lands safely INSIDE
    # the channel run, paired with the cap's spout datum so the pose is
    # unchanged).
    state.frame.update(feed_y=v1 - DRIP_INSET)
    state.datums["feed"] = {
        "at": [0.0, v1 - DRIP_INSET, floor_z + FALL_ENTRY],
        "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="water_rail_body",
    kind="base",
    params={
        "module_l": ("length", None), "module_w": ("length", None),
        "body_h": ("length", 30.0),
        "channel_w": ("length", 16.0), "channel_d": ("length", 5.0),
        "channel_bottom_r": ("length", 1.2),
        "cassette_l": ("length", None), "cassette_w": ("length", None),
        "seat_depth": ("length", 14.0), "seat_clearance": ("length", 0.75),
        "module_pitch": ("length", 250.0), "corner_r": ("length", 4.0),
        "face_gap": ("length", 0.4),
        "lightweight": ("bool", True),
        "lw_rib": ("length", 2.0),
        "under_cassette": ("choice", "skeleton"),
        "trough_w": ("length", 26.0), "trough_rib": ("length", 6.0),
        "trough_depth": ("length", 12.0),
        "profile": ("choice", "2020"), "profile_inset": ("length", 24.0),
    },
    validators=(
        "form.water_channel_constant_depth_ok", "form.water_channel_dims_ok",
        "form.drainage_requires_mount", "form.lightweight_windows_dry_ok",
        "form.cassette_support_span_ok", "form.root_chamber_ok",
        "form.no_standing_water_ir", "form.cassette_seat_fit_ok",
        "topology.water_channel_open", "topology.water_channel_floor_solid",
        "topology.single_connected_solid", "topology.cutout_present",
    ),
    apply=_water_rail_body,
    description="level rail body + recessed cassette seat + CONSTANT-DEPTH open "
                "U-channel (flow -Y; drainage slope comes from the mount, never "
                "the rail) + optional lightweight dry-shell windows",
))


# -- lap_outlet_lip / lap_inlet_receiver (features) ----------------------------
#
# The flush handover pair. Physics at dZ = 0: any lip THICKNESS placed on
# the water path either dams the flow (1.4 mm head at 1.5 deg backs up a
# ~53 mm pool) or hides a wet cavity. The only geometry that obeys every
# rule: the lip CONTINUES the channel floor plane (its top IS the floor
# level) and the receiver is a THROUGH, open-bottom cutout in the first
# millimetres of the downstream floor — the lip lands in the opening and
# the floor plane resumes after a deliberate 0.5–2.5 slot. The stream
# crosses on top of the lip; stray drops in the slot fall through OPEN AIR
# (visible, cleanable, no sump possible). The seam is never the primary
# water path, and modules separate by a straight vertical lift.

#: Extra lip width past the channel — the receiver walls guide, water stays on.
LAP_LIP_W_MARGIN = 2.0
#: Vertical play above the lip inside the receiver side slots.
LAP_TOP_CLEAR = 0.2


def _lap_outlet_lip(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The floor-plane lip at the outlet (-Y) face. On the last module of a
    row the same lip is the drip edge the collector catches — its 4 mm
    protrusion IS the air gap from the wall, so droplets detach."""
    state.require_base("lap_outlet_lip")
    f = state.frame
    if "channel_floor_z_outlet" not in f:
        raise RecipeError("lap_outlet_lip needs a water_rail_body base")
    lip_len, lip_t = p.get("lip_len", 4.0), p.get("lip_t", 1.4)
    if not (3.0 <= lip_len <= 6.0):
        raise RecipeError(f"lip_len {lip_len:g} outside the lap band 3..6")
    floor = f["channel_floor_z_outlet"]
    face = f["rail_y0"]
    lip_w = f["channel_w"] + LAP_LIP_W_MARGIN
    name = op_id or "lap_out"
    tip_y = face - lip_len
    lip = Box3(-lip_w / 2.0, tip_y, floor - lip_t,
               lip_w / 2.0, face + 0.6, floor)
    state.ribs.append(RibFeature(name=f"{name}_lap_lip", box=lip))
    state.regions.append(Region(
        "lap_lip", RegionRole.TRANSIENT_WATER_PATH,
        Box3(-lip_w / 2.0, tip_y - 0.5, floor - lip_t - 0.5,
             lip_w / 2.0, face + 2.0, f["channel_top_z"])))
    state.frame.update(
        lap_lip_len=lip_len, lap_lip_w=lip_w, lap_lip_t=lip_t,
        lap_lip_top_z=floor, lap_lip_tip_y=tip_y,
    )
    # Drip target for the collector: the UNDERSIDE of the lip tip.
    state.datums["drain_edge"] = {
        "at": [0.0, tip_y, floor - lip_t], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="lap_outlet_lip",
    kind="feature",
    params={"lip_len": ("length", 4.0), "lip_t": ("length", 1.4)},
    validators=(
        "form.lap_joint_geometry_ok", "form.lap_slot_leak_path_controlled",
        "form.no_secondary_water_channel", "topology.ribs_present",
    ),
    apply=_lap_outlet_lip,
    description="floor-plane lap lip past the outlet face — the flush "
                "handover giver, and the drip edge on the last module",
))


def _lap_inlet_receiver(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The FLOORED lip-seat at the inlet (+Y) face (VF-9): a top-open pocket
    recessed exactly `lip_t + clearance` below the channel floor, with a SOLID
    bottom — NOT a through hole under the water path. The neighbour's outlet lip
    drops into it so its top lands flush with this channel's floor (continuous
    water surface, no dam), and the shallow pocket drains under the mount tilt.
    A cap drip lands in the same pocket and flows on. Universal: every rail gets
    the same inlet — cap-fed or lap-fed."""
    state.require_base("lap_inlet_receiver")
    f = state.frame
    if "channel_floor_z_inlet" not in f:
        raise RecipeError("lap_inlet_receiver needs a water_rail_body base")
    pocket_len = p.get("pocket_len", 6.0)
    side_clear = p.get("side_clearance", 0.4)
    if not (0.3 <= side_clear <= 0.5):
        raise RecipeError(f"side_clearance {side_clear:g} outside 0.3..0.5")
    lip_t = p.get("lip_t", 1.4)
    lip_clr = p.get("lip_clearance", 0.3)
    floor = f["channel_floor_z_inlet"]
    face = f["rail_y1"]
    pocket_w = f["channel_w"] + LAP_LIP_W_MARGIN + 2.0 * side_clear
    pocket_floor = floor - (lip_t + lip_clr)   # shallow lip-seat, SOLID below
    name = op_id or "lap_in"
    pocket = Box3(-pocket_w / 2.0, face - pocket_len, pocket_floor,
                  pocket_w / 2.0, face + 0.5, floor + LAP_TOP_CLEAR)
    state.cutboxes.append(CutBoxFeature(name=f"{name}_lap_receiver", box=pocket))
    state.regions.append(Region(
        "lap_receiver", RegionRole.TRANSIENT_WATER_PATH,
        Box3(-pocket_w / 2.0, face - pocket_len - 0.5, pocket_floor,
             pocket_w / 2.0, face + 0.5, f["channel_top_z"])))
    state.frame.update(lap_pocket_len=pocket_len, lap_pocket_w=pocket_w,
                       lap_side_clearance=side_clear,
                       lap_pocket_floor_z=pocket_floor,
                       lap_pocket_depth=lip_t + lip_clr)


_register(RecipeOpDecl(
    name="lap_inlet_receiver",
    kind="feature",
    params={"pocket_len": ("length", 6.0), "side_clearance": ("length", 0.4),
            "lip_t": ("length", 1.4), "lip_clearance": ("length", 0.3)},
    validators=(
        "form.lap_joint_geometry_ok", "form.lap_slot_leak_path_controlled",
        "form.lap_receiver_has_floor", "form.lap_receiver_residual_volume_ok",
        "form.rail_universal_inlet_accepts_cap_and_lap",
        "form.no_standing_water_ir", "topology.cutout_present",
    ),
    apply=_lap_inlet_receiver,
    description="floored top-open lip-seat in the inlet floor (VF-9) — the "
                "flush handover receiver: the neighbour's lip nests flush, no "
                "through hole under the water path, shallow + cleanable",
))


