"""Vertical Farm Pack v1 recipe ops (docs/VERTICAL_FARM_PACK.md) — the
water rail, the substrate cassette and the snap retainer frame, composed
per the builder contract: geometry + semantic regions + frame keys +
mandatory validators.

The frame keys published here ARE the Cassette Interface Standard: the
rail publishes seat_*/channel_*, every cassette publishes cassette_*/
window_* plus the shell keys the snap joint reads, and the assembly joints
(removable_insert, tongue_groove, snap_joint) verify the two halves
against each other in the pose. A future sprout/rockwool cassette that
publishes the same keys mates with the same rail untouched.

Imported at the bottom of recipe_ops.py so the registry stays whole.
"""

from __future__ import annotations

import math
from typing import Any

from ..product.archetype import RegionRole
from .part import (
    BoreFeature,
    ChannelCutFeature,
    CutBoxFeature,
    FieldFeature,
    RibFeature,
)
from .profiles_plate import rounded_rect_loop
from .recipe_ops import RECIPE_OPS, RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from .section import SectionProfile

#: Material the deepest channel point must keep beneath it.
FLOOR_MARGIN_MIN = 2.0
#: Corridor over the channel through the seat walls — brush-open by design.
CORRIDOR_MARGIN = 2.0
#: How far above the channel floor the FEED datum sits: the inlet cap's
#: drip tower releases the stream this far above the first rail's floor.
#: This is the ONLY place a fall survives after the VF correction — rails
#: hand water to each other flush, over lap lips, with no step at all.
FALL_ENTRY = 2.5


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
    # cap's drip tower targets this point, FALL_ENTRY above the floor.
    state.datums["feed"] = {
        "at": [0.0, v1, floor_z + FALL_ENTRY],
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
    """The through, open-bottom lap opening at the inlet (+Y) face: the
    neighbour's lip lands here, continuing the floor plane; the tip slot
    stays deliberately open so nothing can dam and nothing hides."""
    state.require_base("lap_inlet_receiver")
    f = state.frame
    if "channel_floor_z_inlet" not in f:
        raise RecipeError("lap_inlet_receiver needs a water_rail_body base")
    pocket_len = p.get("pocket_len", 6.0)
    side_clear = p.get("side_clearance", 0.4)
    if not (0.3 <= side_clear <= 0.5):
        raise RecipeError(f"side_clearance {side_clear:g} outside 0.3..0.5")
    floor = f["channel_floor_z_inlet"]
    face = f["rail_y1"]
    pocket_w = f["channel_w"] + LAP_LIP_W_MARGIN + 2.0 * side_clear
    name = op_id or "lap_in"
    pocket = Box3(-pocket_w / 2.0, face - pocket_len, -1.0,
                  pocket_w / 2.0, face + 0.5, floor + LAP_TOP_CLEAR)
    state.cutboxes.append(CutBoxFeature(name=f"{name}_lap_receiver", box=pocket))
    state.regions.append(Region(
        "lap_receiver", RegionRole.TRANSIENT_WATER_PATH,
        Box3(-pocket_w / 2.0, face - pocket_len - 0.5, -1.0,
             pocket_w / 2.0, face + 0.5, f["channel_top_z"])))
    state.frame.update(lap_pocket_len=pocket_len, lap_pocket_w=pocket_w,
                       lap_side_clearance=side_clear)


_register(RecipeOpDecl(
    name="lap_inlet_receiver",
    kind="feature",
    params={"pocket_len": ("length", 6.0), "side_clearance": ("length", 0.4)},
    validators=(
        "form.lap_joint_geometry_ok", "form.lap_slot_leak_path_controlled",
        "form.no_standing_water_ir", "topology.cutout_present",
    ),
    apply=_lap_inlet_receiver,
    description="through open-bottom lap opening in the inlet floor — the "
                "flush handover receiver; the tip slot is a controlled, "
                "visible, cleanable leak path",
))


# -- edge_magnet_pockets (feature) ---------------------------------------------


def _edge_magnet_pockets(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Optional module-alignment magnets: SEALED dry pockets — blind bores
    into both +-Y faces, in dry body far from every wet zone, leaving a
    plastic floor to the face gap and >= 1.2 wall to any water. Magnets
    align neighbouring modules and NOTHING else: never a seal, never a
    support. No magnet face is ever exposed to water."""
    state.require_base("edge_magnet_pockets")
    f = state.frame
    if "rail_y1" not in f:
        raise RecipeError("edge_magnet_pockets needs a water_rail_body base")
    if not p.get("enabled", False):
        state.frame.update(magnet_count=0)
        return
    # press-fit (VF-4.1): the magnet pushes in from the DRY mating face
    # and stays without a plug; a drop of CA glue is the BOM recommendation
    d = p.get("magnet_d", 6.0) + p.get("fit_clearance", 0.2)
    depth = p.get("magnet_t", 2.0) + 0.4
    x_off, z_c = p.get("x_offset", 60.0), p.get("z_center", 8.0)
    name = op_id or "magnets"
    count = 0
    for face_label, face_y, sign in (("in", f["rail_y1"], 1.0), ("out", f["rail_y0"], -1.0)):
        for x_label, x in (("e", x_off), ("w", -x_off)):
            span = (face_y - depth, face_y) if sign > 0 else (face_y, face_y + depth)
            overshoot = (0.0, 1.0) if sign > 0 else (1.0, 0.0)
            state.bores.append(BoreFeature(
                name=f"{name}_pocket_{face_label}_{x_label}", axis="Y",
                center=(x, 0.0, z_c), d=d, span=span, overshoot=overshoot,
            ))
            state.regions.append(Region(
                f"module_magnet_pocket_{face_label}_{x_label}",
                RegionRole.INTERFACE_KEEPOUT,
                Box3(x - d / 2.0 - 1.0, min(span) - 1.0, z_c - d / 2.0 - 1.0,
                     x + d / 2.0 + 1.0, max(span) + 1.0, z_c + d / 2.0 + 1.0)))
            count += 1
    state.frame.update(
        magnet_count=count, magnet_pocket_d=d, magnet_pocket_depth=depth,
        magnet_x_offset=x_off, magnet_z=z_c,
        magnet_fit_clearance=d - p.get("magnet_d", 6.0),
        magnet_d_nominal=p.get("magnet_d", 6.0),
    )


_register(RecipeOpDecl(
    name="edge_magnet_pockets",
    kind="feature",
    params={
        "enabled": ("bool", False),
        "magnet_d": ("length", 6.0), "magnet_t": ("length", 2.0),
        "fit_clearance": ("length", 0.2),
        "x_offset": ("length", 60.0), "z_center": ("length", 8.0),
    },
    validators=(
        "form.magnet_pockets_outside_water_zone",
        "form.magnet_pockets_do_not_break_wall",
    ),
    apply=_edge_magnet_pockets,
    description="optional sealed dry magnet pockets in both +-Y faces — "
                "module alignment only, never a seal, never a support",
))


# -- profile_seat_slot (feature) ----------------------------------------------


def _profile_seat_slot(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Top-drop-in seating on two aluminum profile rails running along the
    flow axis under the +-X edges — far from the water by construction,
    removable by lifting."""
    state.require_base("profile_seat_slot")
    f = state.frame
    if "seat_floor_z" not in f:
        raise RecipeError("profile_seat_slot needs a water_rail_body base")
    size = 20.0 if p["profile"] == "2020" else 30.0
    clearance, depth, inset = p["clearance"], p["depth"], p["inset"]
    if depth > f["seat_floor_z"] - 2.0:
        raise RecipeError(
            f"profile slot depth {depth:g} undercuts the seat floor at "
            f"{f['seat_floor_z']:g}")
    slot_w = size + 2.0 * clearance
    name = op_id or "profile"
    for label, sign in (("e", 1.0), ("w", -1.0)):
        cx = sign * (f["rail_x1"] - inset)
        box = Box3(cx - slot_w / 2.0, f["rail_y0"] - 1.0, -1.0,
                   cx + slot_w / 2.0, f["rail_y1"] + 1.0, depth)
        state.cutboxes.append(CutBoxFeature(name=f"{name}_slot_{label}", box=box))
        state.regions.append(Region(
            f"profile_seat_{label}", RegionRole.INTERFACE_KEEPOUT, box))
    state.frame.update(
        profile_size=size, profile_slot_w=slot_w,
        profile_slot_clearance=clearance, profile_slot_depth=depth,
        profile_slot_x=f["rail_x1"] - inset,
    )
    # Seat datums (VF-4): the point where the groove CEILING rests on the
    # profile's sloped support line — at the groove's UPSTREAM (+Y) edge,
    # where a flat groove meets a falling line first. 0.5 in from the face:
    # any deeper and the rising support line would wedge into the ceiling
    # upstream of the contact (a real interference, not a modeling nit).
    edge_y = f["rail_y1"] - 0.5
    state.datums["seat_e"] = {
        "at": [f["rail_x1"] - inset, edge_y, depth], "rotate": [0.0, 0.0, 0.0]}
    state.datums["seat_w"] = {
        "at": [-(f["rail_x1"] - inset), edge_y, depth], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="profile_seat_slot",
    kind="feature",
    params={
        "profile": ("choice", "2020"), "clearance": ("length", 0.2),
        "depth": ("length", 6.0), "inset": ("length", 24.0),
    },
    validators=("form.profile_seat_dry_ok", "topology.cutout_present"),
    apply=_profile_seat_slot,
    description="bottom slots seating the module onto 2020/3030 aluminum "
                "rails, tool-free, outside the water path",
))


# -- tongue_groove_edges (feature) ----------------------------------------------


def _tongue_groove_edges(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Module-to-module line alignment: a tongue rib on the +X edge, a
    groove notch in the -X edge. Alignment only — the tongue never bottoms
    (non-load-bearing) and nothing seals."""
    state.require_base("tongue_groove_edges")
    f = state.frame
    if "rail_x1" not in f:
        raise RecipeError("tongue_groove_edges needs a water_rail_body base")
    t_w, t_h, t_len = p["tongue_w"], p["tongue_h"], p["tongue_len"]
    clearance, z0 = p["clearance"], p["z0"]
    groove_w = t_w + 2.0 * clearance
    groove_depth = t_len + p["bottom_margin"] + (f["module_pitch"] - (f["rail_x1"] - f["rail_x0"]))
    name = op_id or "edges"
    tongue = Box3(f["rail_x1"] - 0.6, -t_w / 2.0, z0,
                  f["rail_x1"] + t_len, t_w / 2.0, z0 + t_h)
    groove = Box3(f["rail_x0"] - 1.0, -groove_w / 2.0, z0 - clearance,
                  f["rail_x0"] + groove_depth, groove_w / 2.0, z0 + t_h + clearance)
    state.ribs.append(RibFeature(name=f"{name}_tongue", box=tongue))
    state.cutboxes.append(CutBoxFeature(name=f"{name}_groove", box=groove))
    state.regions.extend([
        Region("tongue_edge", RegionRole.INTERFACE_KEEPOUT, tongue),
        Region("groove_edge", RegionRole.INTERFACE_KEEPOUT, groove),
    ])
    state.frame.update(
        tongue_w=t_w, tongue_h=t_h, tongue_len=t_len,
        groove_w=groove_w, groove_depth=groove_depth,
        edge_clearance=clearance,
        tongue_cy=0.0, groove_cy=0.0, tongue_z0=z0, groove_z0=z0,
    )


_register(RecipeOpDecl(
    name="tongue_groove_edges",
    kind="feature",
    params={
        "tongue_w": ("length", 6.0), "tongue_h": ("length", 4.0),
        "tongue_len": ("length", 3.6), "clearance": ("length", 0.4),
        "z0": ("length", 4.0), "bottom_margin": ("length", 0.4),
    },
    validators=(
        "form.tongue_groove_profile_ok", "topology.ribs_present",
        "topology.cutout_present",
    ),
    apply=_tongue_groove_edges,
    description="tongue (+X) / groove (-X) line-alignment edges, "
                "non-bearing, non-sealing",
))


# -- substrate_tray_body (base) -------------------------------------------------


def _substrate_tray_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The removable cassette shell: a rounded_box_shell that ALSO
    publishes the Cassette Interface Standard frame keys (cassette_*) and
    the seat/rim datums the removable_insert and snap joints read."""
    shell = RECIPE_OPS["rounded_box_shell"]
    shell.apply(state, {
        "l": p["cassette_l"], "w": p["cassette_w"], "h": p["h"],
        "wall": p["wall"], "floor_t": p["floor_t"], "corner_r": p["corner_r"],
    }, op_id or "tray")
    f = state.frame
    state.frame.update(
        cassette_u0=f["outline_u0"], cassette_v0=f["outline_v0"],
        cassette_u1=f["outline_u1"], cassette_v1=f["outline_v1"],
        cassette_h=f["shell_h"], floor_bottom_z=0.0,
    )
    state.datums["seat"] = {"at": [0.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="substrate_tray_body",
    kind="base",
    params={
        "cassette_l": ("length", None), "cassette_w": ("length", None),
        "h": ("length", 26.0), "wall": ("length", 2.4),
        "floor_t": ("length", 2.0), "corner_r": ("length", 3.0),
    },
    validators=(
        "form.shell_walls_ok", "topology.cutout_present",
        "topology.single_connected_solid",
    ),
    apply=_substrate_tray_body,
    description="removable substrate cassette shell publishing the "
                "Cassette Interface Standard keys",
))


# -- contact_window (feature) ---------------------------------------------------


def _contact_window(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The localized lowered window: a slab welded UNDER the cassette
    floor that reaches window_drop into the channel's upper zone — pulse
    water touches the substrate through the mesh, drained water never
    does. Run BEFORE mesh_floor so the mesh knows how deep to pierce."""
    state.require_base("contact_window")
    f = state.frame
    if "floor_t" not in f:
        raise RecipeError("contact_window needs a substrate_tray_body base")
    w, length, drop = p["window_w"], p["window_l"], p["drop"]
    cx, cy = p["cx"], p["cy"]
    if (cx - w / 2.0 < f["inner_u0"] + 2.0 or cx + w / 2.0 > f["inner_u1"] - 2.0
            or cy - length / 2.0 < f["inner_v0"] + 2.0
            or cy + length / 2.0 > f["inner_v1"] - 2.0):
        raise RecipeError("contact window does not fit inside the tray floor")
    name = op_id or "window"
    slab = Box3(cx - w / 2.0, cy - length / 2.0, -drop,
                cx + w / 2.0, cy + length / 2.0, 0.6)
    state.ribs.append(RibFeature(name=f"{name}_slab", box=slab))
    state.regions.append(Region(
        "contact_window", RegionRole.TRANSIENT_WATER_PATH,
        Box3(slab.x0, slab.y0, -drop - 0.1, slab.x1, slab.y1, 0.6),
    ))
    state.frame.update(
        window_cx=cx, window_w=w, window_l=length,
        window_drop=drop, window_floor_z=-drop,
    )


_register(RecipeOpDecl(
    name="contact_window",
    kind="feature",
    params={
        # narrower than the rail channel so the slab drops INTO it —
        # contact area comes from window_l along the flow, not width
        "window_w": ("length", 12.0), "window_l": ("length", 60.0),
        "drop": ("length", 1.5), "cx": ("length", 0.0), "cy": ("length", 0.0),
    },
    validators=("form.contact_window_geometry_ok", "topology.contact_window_present"),
    apply=_contact_window,
    description="lowered substrate-contact slab under the floor — pulse "
                "water reach, never permanent flooding",
))


# -- mesh_floor (feature) --------------------------------------------------------


def _mesh_floor(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The flat orthogonal mesh: an axis-aligned grid of square through
    cells across the tray floor. Holds coco, aerates roots, directs
    nothing. Pierces the contact-window slab too (fields cut last)."""
    state.require_base("mesh_floor")
    f = state.frame
    if "floor_t" not in f:
        raise RecipeError("mesh_floor needs a substrate_tray_body base")
    cell, rib, margin = p["cell"], p["rib"], p["margin"]
    u0, v0 = f["inner_u0"] + margin, f["inner_v0"] + margin
    u1, v1 = f["inner_u1"] - margin, f["inner_v1"] - margin
    if u1 - u0 < cell or v1 - v0 < cell:
        raise RecipeError("tray floor too small for a single mesh cell")
    pitch = cell + rib
    nx = int((u1 - u0 + rib) // pitch)
    ny = int((v1 - v0 + rib) // pitch)
    x_start = (u0 + u1) / 2.0 - (nx - 1) * pitch / 2.0
    y_start = (v0 + v1) / 2.0 - (ny - 1) * pitch / 2.0
    half = cell / 2.0
    polygons = tuple(
        (
            (x_start + i * pitch - half, y_start + j * pitch - half),
            (x_start + i * pitch + half, y_start + j * pitch - half),
            (x_start + i * pitch + half, y_start + j * pitch + half),
            (x_start + i * pitch - half, y_start + j * pitch + half),
        )
        for i in range(nx) for j in range(ny)
    )
    drop = f.get("window_drop", 0.0)
    state.fields.append(FieldFeature(
        plane_z=f["floor_t"], centers=(), cell=cell,
        depth=f["floor_t"] + drop + 1.0, pattern="slots",
        polygons=polygons, min_ligament=rib,
    ))
    state.regions.append(Region(
        "mesh_canvas", RegionRole.SUBSTRATE_SUPPORT_MESH,
        Box3(u0, v0, -0.1, u1, v1, f["floor_t"]),
    ))
    state.frame.update(mesh_cell=cell, mesh_rib=rib)


_register(RecipeOpDecl(
    name="mesh_floor",
    kind="feature",
    params={
        "cell": ("length", 6.0), "rib": ("length", 1.3),
        "margin": ("length", 6.0),
    },
    validators=(
        "form.mesh_floor_orthogonal_ok", "form.cassette_no_reservoir",
        "form.min_ligament_ok", "form.no_secondary_water_channel",
        "topology.hex_field_present",
    ),
    apply=_mesh_floor,
    description="flat orthogonal through-mesh across the cassette floor",
))


# -- lift_tabs (feature) ----------------------------------------------------------


def _lift_tabs(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Two open finger notches through the +-Y rim — the cassette lifts
    out of the rail by hand, no tools, nothing to unscrew."""
    state.require_base("lift_tabs")
    f = state.frame
    if "shell_wall" not in f:
        raise RecipeError("lift_tabs needs a substrate_tray_body base")
    w, d = p["notch_w"], p["notch_d"]
    h, wall = f["shell_h"], f["shell_wall"]
    name = op_id or "lift"
    for i, (lo, hi) in enumerate((
        (f["outline_v0"] - 1.0, f["outline_v0"] + wall + 1.0),
        (f["outline_v1"] - wall - 1.0, f["outline_v1"] + 1.0),
    )):
        state.cutboxes.append(CutBoxFeature(
            name=f"{name}_notch_{i}",
            box=Box3(-w / 2.0, lo, h - d, w / 2.0, hi, h + 1.0),
        ))
    state.frame.update(lift_notch_w=w, lift_notch_d=d, lift_notch_count=2.0)


_register(RecipeOpDecl(
    name="lift_tabs",
    kind="feature",
    params={"notch_w": ("length", 18.0), "notch_d": ("length", 8.0)},
    validators=("form.lift_access_ok", "topology.cutout_present"),
    apply=_lift_tabs,
    description="finger notches through the rim for tool-free removal",
))


# -- retainer_frame_body (base) -----------------------------------------------


def _retainer_frame_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The Snap Retainer Frame: a flat rounded ring plate — a band wide
    enough to hold the coco mat down lightly, an opening big enough to
    let the greens through."""
    if state.section is not None:
        raise RecipeError("retainer_frame_body must be the (single) base op")
    l, w, t = p["l"], p["w"], p["t"]
    band = p["band_w"]
    if 2.0 * band + 20.0 >= min(l, w):
        raise RecipeError("frame band leaves no opening for the greens")
    u0, v0, u1, v1 = -l / 2.0, -w / 2.0, l / 2.0, w / 2.0
    state.section = SectionProfile(
        name="recipe", outer=rounded_rect_loop(u0, v0, u1, v1, p["corner_r"]),
        plane="XY", width_axis="Z",
    )
    state.width = t
    name = op_id or "frame"
    state.cutboxes.append(CutBoxFeature(
        name=f"{name}_opening",
        box=Box3(u0 + band, v0 + band, -1.0, u1 - band, v1 - band, t + 1.0),
    ))
    state.regions.append(Region(
        "frame_band", RegionRole.MOUNTING_SURFACE, Box3(u0, v0, 0.0, u1, v1, t)))
    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=p["corner_r"], frame_band_w=band, frame_t=t,
    )
    # The seat datum sits on the plate TOP (hook side): the assembly flips
    # the frame 180 about X onto the cassette rim, so the plate lands ABOVE
    # the rim plane and the hooks descend inside the walls.
    state.datums["seat"] = {"at": [0.0, 0.0, t], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="retainer_frame_body",
    kind="base",
    params={
        "l": ("length", None), "w": ("length", None), "t": ("length", 3.0),
        "band_w": ("length", 10.0), "corner_r": ("length", 3.0),
    },
    validators=("topology.cutout_present", "topology.single_connected_solid"),
    apply=_retainer_frame_body,
    description="flat ring plate holding the substrate down lightly",
))


# -- frame_snap_hooks (feature) -------------------------------------------------


def _frame_snap_hooks(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Four cantilever hooks rising from the frame plate at the +-X edges
    (two per side, spaced along Y), lips outward — the assembly flips the
    frame onto the cassette rim and the lips click into the cassette's
    snap windows. Light retention: strain is verified by the snap joint."""
    state.require_base("frame_snap_hooks")
    f = state.frame
    if "frame_t" not in f:
        raise RecipeError("frame_snap_hooks needs a retainer_frame_body base")
    beam_t, hook_w = p["beam_t"], p["hook_w"]
    hook_len, lip_d, lip_h = p["hook_len"], p["lip_d"], p["lip_h"]
    span, sy = p["hook_span"], p["sy"]
    t = f["frame_t"]
    name = op_id or "snap"
    i = 0
    for side in (-1.0, 1.0):
        edge = side * span / 2.0
        post_x0, post_x1 = (edge - beam_t, edge) if side > 0 else (edge, edge + beam_t)
        lip_x0, lip_x1 = (edge, edge + lip_d) if side > 0 else (edge - lip_d, edge)
        for cy in (-sy / 2.0, sy / 2.0):
            state.ribs.append(RibFeature(
                name=f"{name}_post_{i}",
                box=Box3(post_x0, cy - hook_w / 2.0, t - 0.6,
                         post_x1, cy + hook_w / 2.0, t + hook_len),
            ))
            state.ribs.append(RibFeature(
                name=f"{name}_lip_{i}",
                box=Box3(lip_x0, cy - hook_w / 2.0, t + hook_len - lip_h,
                         lip_x1, cy + hook_w / 2.0, t + hook_len),
            ))
            state.regions.append(Region(
                f"snap_root_{i}", RegionRole.HIGH_STRESS_REGION,
                Box3(post_x0 - 1.0, cy - hook_w / 2.0 - 1.0, t - 1.0,
                     post_x1 + 1.0, cy + hook_w / 2.0 + 1.0, t + 3.0),
            ))
            i += 1
    state.frame.update({
        f"{name}_beam_t": beam_t, f"{name}_hook_len": hook_len,
        f"{name}_lip_d": lip_d, f"{name}_lip_h": lip_h,
        f"{name}_hook_w": hook_w, f"{name}_span": span, f"{name}_sy": sy,
    })


_register(RecipeOpDecl(
    name="frame_snap_hooks",
    kind="feature",
    params={
        "beam_t": ("length", 1.6), "hook_w": ("length", 8.0),
        "hook_len": ("length", 9.0), "lip_d": ("length", 1.4),
        "lip_h": ("length", 3.0),
        "hook_span": ("length", None), "sy": ("length", 120.0),
    },
    validators=("topology.ribs_present",),
    apply=_frame_snap_hooks,
    description="four light cantilever hooks (two per X side), lips outward",
))


# -- VF-3 fluid adapters --------------------------------------------------------
#
# Both adapters use a LOCAL FRAME ANCHORED AT THE RAIL FACE PLANE (local
# y=0 = the rail face the adapter hangs on) and at the fluid handover
# height (the fluid datum). Everything else — saddle, spout/tongue, tray —
# is derived from that anchor, so datum-on-datum posing lands the saddle
# on the wall by construction (verified, not hoped: assembly.saddle_hang_ir).


def _inlet_cap_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The Water Inlet Cap: a drip tower, not a mini-rail. A drip line
    pushes into a vertical bore from the top; water falls straight through
    a spout that dips into the rail's inlet corridor and exits at the
    handover point. One straight vertical path — no pockets by
    construction, brush- and eye-cleanable from above. Hangs on the rail
    back wall via a downward saddle slot; the spout tongue in the corridor
    captures X and Y. Local frame: y=0 = the rail back face (+Y side of
    the wall is the cap's arm), z=0 = the cap body bottom."""
    if state.section is not None:
        raise RecipeError("inlet_cap_body must be the (single) base op")
    cap_w, cap_h = p["cap_w"], p["cap_h"]
    tube_od, grip = p["tube_od"], p["bore_clearance"]
    wall_t, fit = p["rail_wall_t"], p["saddle_fit"]
    saddle_depth = p["saddle_depth"]
    hang_drop = p["hang_drop"]
    spout_w = p["spout_w"]
    rail_channel_w = p["rail_channel_w"]
    bore_d = tube_od + grip
    z_exit = saddle_depth - hang_drop
    if z_exit > -1.0:
        raise RecipeError(
            f"spout exit z={z_exit:g} does not descend below the body — "
            "hang_drop must exceed saddle_depth")
    if spout_w > rail_channel_w - 2.0:
        raise RecipeError(
            f"spout {spout_w:g} cannot dip into the {rail_channel_w:g} rail channel")
    if bore_d > spout_w - 3.0:
        raise RecipeError(
            f"hose bore {bore_d:g} leaves no spout wall in {spout_w:g}")

    y_front = -(wall_t + fit) + 0.65  # stops short of the wall's inner sliver
    y_back = 18.0
    u0, v0, u1, v1 = -cap_w / 2.0, y_front, cap_w / 2.0, y_back
    state.section = SectionProfile(
        name="recipe", outer=rounded_rect_loop(u0, v0, u1, v1, p["corner_r"]),
        plane="XY", width_axis="Z",
    )
    state.width = cap_h
    name = op_id or "cap"

    slot = Box3(u0 - 1.0, -(wall_t + fit), -1.0, u1 + 1.0, fit, saddle_depth)
    state.cutboxes.append(CutBoxFeature(name=f"{name}_saddle_slot", box=slot))
    spout = Box3(-spout_w / 2.0, -(wall_t + 0.25), z_exit - 1.0,
                 spout_w / 2.0, 7.0, 0.6)
    state.ribs.append(RibFeature(name=f"{name}_spout", box=spout))
    state.bores.append(BoreFeature(
        name=f"{name}_hose_drop", axis="Z", center=(0.0, 0.0, 0.0),
        d=bore_d, span=(z_exit, cap_h), overshoot=(1.0, 1.0),
    ))

    state.regions.extend([
        Region("spout_path", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-spout_w / 2.0, -bore_d / 2.0 - 2.0, z_exit - 1.0,
                    spout_w / 2.0, bore_d / 2.0 + 2.0, cap_h + 0.5)),
        Region("saddle", RegionRole.INTERFACE_KEEPOUT, slot),
    ])

    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=p["corner_r"],
        hose_tube_od=tube_od, hose_bore_d=bore_d,
        spout_w=spout_w, rail_channel_w=rail_channel_w,
        channel_center_x=0.0, channel_w=bore_d, channel_top_z=cap_h,
        channel_floor_z_outlet=z_exit, channel_y_outlet=0.0,
        saddle_slot_y0=-(wall_t + fit), saddle_slot_y1=fit,
        saddle_floor_z=saddle_depth, saddle_fit=fit,
        hang_drop=hang_drop,
    )
    state.datums["spout"] = {"at": [0.0, 0.0, z_exit], "rotate": [0.0, 0.0, 0.0]}
    state.datums["tube_in"] = {"at": [0.0, 0.0, cap_h], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="inlet_cap_body",
    kind="base",
    params={
        "cap_w": ("length", 64.0), "cap_h": ("length", 22.0),
        "tube_od": ("length", 9.0), "bore_clearance": ("length", 0.4),
        "rail_wall_t": ("length", 13.25), "saddle_fit": ("length", 0.4),
        "saddle_depth": ("length", 8.0), "hang_drop": ("length", 16.5),
        "spout_w": ("length", 14.0), "rail_channel_w": ("length", 16.0),
        "corner_r": ("length", 3.0),
    },
    validators=(
        "form.hose_bore_ok", "form.spout_drop_path_ok",
        "form.no_standing_water_ir",
        "topology.fluid_path_open", "topology.single_connected_solid",
        "topology.cutout_present", "topology.ribs_present",
    ),
    apply=_inlet_cap_body,
    description="drip-tower inlet cap: vertical hose bore through a spout "
                "dipping into the rail inlet corridor; saddle-hangs on the "
                "back wall",
))


def _collector_endcap_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The Collector/Drain Endcap: a catch tray under the LAST rail's lap
    lip (VF correction: the lip continuing the channel floor plane is the
    drip edge — its protrusion IS the air gap). Droplets detach at the lip
    tip, fall into the tray mouth, run down the sloped tray floor to a
    push-in drain bore at the low end. Hangs on the rail FRONT wall: an arm
    over the wall top, side cheeks outside the drip band, a dry tongue in
    the outlet corridor for X/Y capture (riding ABOVE the exiting water).
    Local frame: y=0 = the rail front face, +y toward the rail interior;
    z=0 = the handover plane (the lip tip underside the catch datum mates —
    lip_overhang outside the face)."""
    if state.section is not None:
        raise RecipeError("collector_endcap_body must be the (single) base op")
    tray_w_inner = p["tray_w"]
    tube_od, grip = p["tube_od"], p["bore_clearance"]
    wall_t, fit = p["rail_wall_t"], p["saddle_fit"]
    hang_drop = p["hang_drop"]
    tongue_w = p["tongue_w"]
    rail_channel_w = p["rail_channel_w"]
    slope = p["tray_slope_deg"]
    bore_d = tube_od + grip
    wall = 2.4
    # Sturdy U-frame walls (VF-4.2): wider than a molded skin so the side
    # walls carry the cantilevered tray as real walls, not thin columns.
    wall_extra = p.get("wall_extra", 2.4)
    tray_w_outer = tray_w_inner + 2.0 * (wall + 1.2 + wall_extra)
    if tongue_w > rail_channel_w - 2.0:
        raise RecipeError(
            f"tongue {tongue_w:g} cannot dip into the {rail_channel_w:g} rail channel")
    lip_overhang = p.get("lip_overhang", 4.0)
    # Receiver capture (VF-4.1): how deep the mouth reaches past the rail
    # face — the captured lip tip must keep >= 2 to the outer apron wall.
    capture_depth = p.get("capture_depth", 8.0)
    if not (6.0 - 1e-9 <= capture_depth <= 8.0 + 1e-9):
        raise RecipeError(
            f"capture_depth {capture_depth:g} outside the receiver band 6..8")
    if capture_depth - lip_overhang < 2.0:
        raise RecipeError(
            f"lip tip lands {capture_depth - lip_overhang:g} from the apron "
            "(needs >= 2) — deepen capture_depth or shorten the lip")

    # Sump extension (VF-4.2): the tray reaches drain_extension further back
    # so a VERTICAL drain bore can be drilled through solid body at the
    # floor's low point — the tube pushes in FROM BELOW and routes under the
    # row (no sagging horizontal ceiling, no teardrop trick needed).
    drain_extension = p.get("drain_extension", 10.0)
    if not (8.0 - 1e-9 <= drain_extension <= 14.0 + 1e-9):
        raise RecipeError(
            f"drain_extension {drain_extension:g} outside 8..14")
    drain_grip = p.get("drain_grip", 12.0)  # solid depth for the push-in tube

    rim_z = 3.0
    # The catch floor sits catch_fall below the handover datum so the mouth
    # captures the lip; the tray then slopes back to the sump's low point.
    catch_fall = p["catch_fall"]
    floor_at_catch = -catch_fall
    depth_start = rim_z + catch_fall
    y_drain_wall = -(capture_depth + 3.0 + drain_extension)  # sump outer end
    run = 1.6 - (y_drain_wall + 3.0)  # channel span catch->deep end
    depth_end = depth_start + run * math.tan(math.radians(slope))
    floor_low = rim_z - depth_end  # deepest floor point (design z)
    # base deep enough that the vertical drain grips >= drain_grip of solid
    tray_bottom = min(floor_at_catch - (depth_end - depth_start) - 3.0,
                      floor_low - drain_grip)
    if bore_d > tray_w_inner - 3.0:
        raise RecipeError(
            f"drain bore {bore_d:g} does not fit across the {tray_w_inner:g} "
            "tray with wall — widen tray_w or shrink tube_od")

    # base = the tray block; everything above is additive (arm/bib/tongue)
    u0, v0, u1, v1 = -tray_w_outer / 2.0, y_drain_wall, tray_w_outer / 2.0, -0.4
    state.section = SectionProfile(
        name="recipe", outer=rounded_rect_loop(u0, v0, u1, v1, p["corner_r"]),
        plane="XY", width_axis="Z",
    )
    state.width = rim_z - tray_bottom
    # shift: extrusion runs 0..width but our tray spans tray_bottom..rim_z.
    # Keep the native 0..width frame and express everything relative to it:
    # local z here = z - tray_bottom for the BASE ONLY is messy — instead
    # the base is extruded 0..width and we treat local z0 = tray_bottom by
    # translating all features: the compile frame IS the part frame, so we
    # place the channel/ribs in absolute coords by adding -tray_bottom.
    dz = -tray_bottom  # translate design coords -> extrusion coords

    state.channels.append(ChannelCutFeature(
        name=f"{op_id or 'collector'}_tray", center_x=0.0,
        y0=1.6, y1=y_drain_wall + 3.0, z_top=rim_z + dz,
        width=tray_w_inner, depth_start=depth_start, depth_end=depth_end,
        bottom_r=1.0,
    ))
    name = op_id or "collector"
    # Vertical drain (VF-4.2): the bore descends from the sump's low floor
    # point straight through the solid base and out the bottom — the push-in
    # tube enters FROM BELOW and routes under the row. A vertical bore has
    # no ceiling to bridge, so it prints supportless as-modeled.
    y_drain = y_drain_wall + 3.0 + bore_d / 2.0 + 1.0  # inboard of the back wall
    state.bores.append(BoreFeature(
        name=f"{name}_drain_hose", axis="Z",
        center=(0.0, y_drain, 0.0),
        d=bore_d, span=(0.0, floor_low + dz + 0.5),
        overshoot=(1.0, 1.0),
    ))
    # No tuck strip (VF correction): the cascade's relief recess is gone —
    # the wall face is solid, and the lap lip carries the drip band
    # lip_overhang outside the face, well inside the tray mouth. A strip
    # reaching INTO the wall would simply interfere with the rail body.
    # Two side WALLS (VF-4.2 U-frame): full side walls from the tray bottom
    # up to the arm, running the FULL length of the body — the cantilevered
    # tray, the mouth zone and the arm become one rigid U, not columns on
    # the tray rim. Walls stay at |x| >= cheek_x0 (they hug the captured
    # lip's wet zone, lip_w/2 + 1.5 per side, never touch) so the mouth's
    # open top survives between them. Vertical walls print supportless.
    lip_w = rail_channel_w + 2.0
    cheek_x0 = max(lip_w / 2.0 + 1.5, tray_w_inner / 2.0 + 0.5)
    wall_z0 = dz + tray_bottom + 1.0  # = 1.0: just above the base bottom
    arm_z0 = hang_drop + dz
    arm_z1 = hang_drop + 8.0 + dz
    # Walls run the FULL arm height (VF-4.2): they ARE the arm's side walls,
    # merging over the whole 8 mm — not a 0.6 mm glue line carrying the
    # hanging arm. The neck between the tray and the arm is one continuous
    # side wall, not a thin waist.
    wall_z1 = arm_z1
    cheek_e = Box3(cheek_x0, y_drain_wall, wall_z0, u1, -1.5, wall_z1)
    cheek_w = Box3(u0, y_drain_wall, wall_z0, -cheek_x0, -1.5, wall_z1)
    arm = Box3(u0, -1.5, arm_z0, u1, wall_t + fit, arm_z1)
    # the locator tongue rides the UPPER corridor only: its underside
    # clears the tray's vertical brush probes (rim + 14) and sits far
    # above the exiting water; X/Y capture is unchanged
    tongue = Box3(-tongue_w / 2.0, 1.0, rim_z + 14.2 + dz,
                  tongue_w / 2.0, wall_t + 0.25, hang_drop + 0.6 + dz)
    state.ribs.append(RibFeature(name=f"{name}_cheek_e", box=cheek_e))
    state.ribs.append(RibFeature(name=f"{name}_cheek_w", box=cheek_w))
    state.ribs.append(RibFeature(name=f"{name}_arm", box=arm))
    state.ribs.append(RibFeature(name=f"{name}_tongue", box=tongue))

    state.regions.extend([
        Region("catch_tray", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-tray_w_inner / 2.0, y_drain_wall - 0.5, tray_bottom + dz,
                    tray_w_inner / 2.0, 1.6, rim_z + dz + 2.0)),
        Region("saddle", RegionRole.INTERFACE_KEEPOUT, arm),
    ])

    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=p["corner_r"],
        hose_tube_od=tube_od, hose_bore_d=bore_d,
        spout_w=tongue_w, rail_channel_w=rail_channel_w,
        channel_center_x=0.0, channel_w=tray_w_inner,
        channel_top_z=rim_z + dz,
        channel_floor_z_inlet=floor_at_catch + dz, channel_y_inlet=0.0,
        saddle_slot_y0=-1.5, saddle_slot_y1=wall_t + fit,
        saddle_floor_z=hang_drop + dz, saddle_fit=fit,
        hang_drop=hang_drop,
        # receiver keys (VF-4.1) — DESIGN coords: z relative to the
        # handover plane (the lip tip underside), y relative to the face
        receiver_mouth_w=2.0 * cheek_x0,
        receiver_capture_depth=capture_depth,
        receiver_apron_z=rim_z,
        receiver_cheek_x0=cheek_x0,
        receiver_lip_overhang=lip_overhang,
        receiver_lip_w=lip_w,
        handover_dz=dz,
        # structure keys (VF-4.2) — the U-frame walls the sturdiness check
        # reads, and the vertical-drain marker
        wall_x0=cheek_x0, wall_t=u1 - cheek_x0,
        wall_z0=wall_z0, wall_z1=wall_z1,
        arm_z0=hang_drop + dz, tray_bottom_z=dz + tray_bottom,
        drain_vertical=1.0, drain_low_y=y_drain, drain_grip=drain_grip,
        tray_floor_low_z=floor_low + dz,
    )
    # The catch datum sits AT THE LIP TIP: lip_overhang outside the wall
    # face, on the handover plane — mating it onto the rail's drain_edge
    # lands the collector body exactly against the wall.
    state.datums["catch"] = {
        "at": [0.0, -p.get("lip_overhang", 4.0), dz], "rotate": [0.0, 0.0, 0.0]}
    # The drain exits the BOTTOM of the sump — the tube pushes in from below
    # and routes under the row (normal -Z).
    state.datums["drain_out"] = {
        "at": [0.0, y_drain, 0.0], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="collector_endcap_body",
    kind="base",
    params={
        "tray_w": ("length", 20.0), "tube_od": ("length", 9.0),
        "bore_clearance": ("length", 0.4),
        "rail_wall_t": ("length", 13.25), "saddle_fit": ("length", 0.4),
        "hang_drop": ("length", 20.4), "tongue_w": ("length", 14.0),
        "rail_channel_w": ("length", 16.0), "tray_slope_deg": ("number", 1.5),
        "catch_fall": ("length", 8.5), "lip_overhang": ("length", 4.0),
        "capture_depth": ("length", 8.0),
        "drain_extension": ("length", 10.0), "drain_grip": ("length", 12.0),
        "wall_extra": ("length", 3.0),
        "corner_r": ("length", 3.0),
    },
    validators=(
        "form.hose_bore_ok", "form.collector_tray_drains",
        "form.collector_receiver_matches_final_lap",
        "form.receiver_open_top_cleanable",
        "form.collector_drain_bore_supportless",
        "form.collector_structure_sturdy",
        "form.no_standing_water_ir",
        "topology.fluid_path_open", "topology.single_connected_solid",
        "topology.ribs_present",
    ),
    apply=_collector_endcap_body,
    description="catch-tray collector endcap (VF-4.2): sloped tray under the "
                "final lap lip, sturdy U-frame side walls carrying the "
                "cantilever, draining through a VERTICAL push-in bore out "
                "the sump bottom (tube enters from below, routes under the row)",
))


# -- profile_ref_body (VF-4: the sloped-carrier reference proxy) -----------------


def _profile_ref_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Aluminum profile REFERENCE GEOMETRY — after the VF correction the
    model is LITERALLY TRUE: a standard straight 2020/3030 extrusion, cut
    to length, modeled straight and horizontal. The physical row slope
    lives ONLY in the assembly's mount_context — never in this geometry
    and never in a pose. (The VF-4 sloped-top surrogate is superseded:
    slope_deg stays accepted for the IR but the canon is 0.)

    Stations along the flat top mark where each rail's groove ceiling
    lands; their datums drive the profile_perch joints."""
    if state.section is not None:
        raise RecipeError("profile_ref_body must be the (single) base op")
    size = 20.0 if p["size"] == "2020" else 30.0
    length = p["length"]
    slope = p["slope_deg"]
    pitch = p["station_pitch"]
    stations = int(round(p["stations"]))
    station_edge = p["station_edge"]
    drop_total = length * math.tan(math.radians(slope))
    if stations < 1:
        raise RecipeError("profile needs at least one station")
    span_needed = station_edge + (stations - 1) * pitch + 8.0
    if length < span_needed:
        raise RecipeError(
            f"profile {length:g} shorter than its stations need "
            f"({span_needed:g}) — cut it longer")

    y0, y1 = -length / 2.0, length / 2.0
    straight = abs(drop_total) < 1e-9
    height = size if straight else size + 2.0 + drop_total
    state.section = SectionProfile(
        name="recipe",
        outer=rounded_rect_loop(-size / 2.0, y0, size / 2.0, y1, 1.0),
        plane="XY", width_axis="Z",
    )
    state.width = height
    name = op_id or "profile"

    if not straight:
        # legacy sloped surrogate: wide U-cutter beheads the box — its
        # floor becomes the sloped top face (superseded by mount_context)
        state.channels.append(ChannelCutFeature(
            name=f"{name}_slope_cut", center_x=0.0,
            y0=y1, y1=y0, z_top=height,
            width=size + 10.0, depth_start=2.0, depth_end=2.0 + drop_total,
            bottom_r=1.0,
        ))

    def top_z_at(y: float) -> float:
        return size + (y - y0) * math.tan(math.radians(slope))

    for k in range(1, stations + 1):
        yk = y1 - station_edge - (k - 1) * pitch
        state.datums[f"station_{k}"] = {
            "at": [0.0, yk, top_z_at(yk)], "rotate": [0.0, 0.0, 0.0]}
        state.frame[f"station_{k}_y"] = yk
        state.frame[f"station_{k}_z"] = top_z_at(yk)

    state.regions.append(Region(
        "profile_body", RegionRole.MOUNTING_SURFACE,
        Box3(-size / 2.0, y0, 0.0, size / 2.0, y1, height)))
    state.frame.update(
        outline_u0=-size / 2.0, outline_v0=y0,
        outline_u1=size / 2.0, outline_v1=y1,
        outline_corner_r=1.0,
        profile_size=size, profile_len=length,
        profile_slope_deg=slope,
        profile_y_low=y0, profile_y_high=y1,
        profile_top_z_low=size,
        station_pitch=pitch, station_count=float(stations),
    )


_register(RecipeOpDecl(
    name="profile_ref_body",
    kind="base",
    params={
        "size": ("choice", "2020"), "length": ("length", 780.0),
        "slope_deg": ("number", 0.0), "station_pitch": ("length", 248.4),
        "stations": ("count", 3), "station_edge": ("length", 20.0),
    },
    validators=(
        "form.profile_ref_geometry_ok", "topology.single_connected_solid",
    ),
    apply=_profile_ref_body,
    description="aluminum profile reference geometry: standard straight "
                "2020/3030 cut to length, modeled straight — the row slope "
                "belongs to mount_context, never to the model",
))
