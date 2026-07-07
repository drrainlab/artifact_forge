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
from .part import ChannelCutFeature, CutBoxFeature, FieldFeature, RibFeature
from .profiles_plate import rounded_rect_loop
from .recipe_ops import RECIPE_OPS, RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from .section import SectionProfile

#: Material the deepest channel point must keep beneath it.
FLOOR_MARGIN_MIN = 2.0
#: Corridor over the channel through the seat walls — brush-open by design.
CORRIDOR_MARGIN = 2.0


# -- water_rail_body (base) ---------------------------------------------------


def _water_rail_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The Base Water Rail: a level plan-view body carrying a recessed
    cassette seat, and the sloped open U-channel cut from the SEAT FLOOR —
    the body stays horizontal, the water falls. Flow axis Y: inlet at the
    back (+Y), outlet at the front (-Y). Corridor notches open the channel
    to the sky through both seat walls, so the whole run is brush-reachable
    and the water exits by construction."""
    if state.section is not None:
        raise RecipeError("water_rail_body must be the (single) base op")
    l, w, h = p["module_l"], p["module_w"], p["body_h"]
    ch_w, ch_d, slope = p["channel_w"], p["channel_d"], p["slope_deg"]
    bottom_r = p["channel_bottom_r"]
    cassette_l, cassette_w = p["cassette_l"], p["cassette_w"]
    seat_depth, clearance = p["seat_depth"], p["seat_clearance"]
    pitch = p["module_pitch"]

    seat_floor = h - seat_depth
    depth_out = ch_d + w * math.tan(math.radians(slope))
    floor_margin = seat_floor - depth_out
    if floor_margin < FLOOR_MARGIN_MIN:
        raise RecipeError(
            f"channel floor would leave only {floor_margin:.1f} under the outlet "
            f"(needs >= {FLOOR_MARGIN_MIN:g}) — raise body_h or shrink seat_depth/slope")
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

    state.channels.append(ChannelCutFeature(
        name=f"{name}_water", center_x=0.0,
        y0=v1, y1=v0, z_top=seat_floor,
        width=ch_w, depth_start=ch_d, depth_end=depth_out, bottom_r=bottom_r,
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
               Box3(-ch_w / 2.0, v0, seat_floor - depth_out - 0.5,
                    ch_w / 2.0, v1, seat_floor)),
        Region("cassette_seat_walls", RegionRole.INTERFACE_KEEPOUT,
               Box3(-seat_l / 2.0 - 4.0, -seat_w / 2.0 - 4.0, seat_floor,
                    seat_l / 2.0 + 4.0, seat_w / 2.0 + 4.0, h)),
        Region("dry_zone_back", RegionRole.MOUNTING_SURFACE,
               Box3(corridor_half + 4.0, seat_w / 2.0 + 1.0, 0.0, u1 - 4.0, v1, h)),
    ])

    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=p["corner_r"],
        rail_x0=u0, rail_x1=u1, rail_y0=v0, rail_y1=v1, body_h=h,
        channel_center_x=0.0, channel_w=ch_w, channel_bottom_r=bottom_r,
        channel_top_z=seat_floor,
        channel_y_inlet=v1, channel_y_outlet=v0,
        channel_floor_z_inlet=seat_floor - ch_d,
        channel_floor_z_outlet=seat_floor - depth_out,
        channel_slope_deg=slope, channel_floor_margin=floor_margin,
        seat_u0=-seat_l / 2.0, seat_v0=-seat_w / 2.0,
        seat_u1=seat_l / 2.0, seat_v1=seat_w / 2.0,
        seat_floor_z=seat_floor, seat_depth=seat_depth, seat_clearance=clearance,
        module_pitch=pitch,
    )
    state.datums["cassette_seat"] = {"at": [0.0, 0.0, seat_floor], "rotate": [0.0, 0.0, 0.0]}
    state.datums["module_origin"] = {"at": [0.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]}
    state.datums["line_east"] = {"at": [u1, 0.0, h / 2.0], "rotate": [0.0, 0.0, 0.0]}
    state.datums["line_west"] = {"at": [u0, 0.0, h / 2.0], "rotate": [0.0, 0.0, 0.0]}
    state.datums["inlet"] = {"at": [0.0, v1, seat_floor], "rotate": [0.0, 0.0, 0.0]}
    state.datums["outlet"] = {"at": [0.0, v0, seat_floor], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="water_rail_body",
    kind="base",
    params={
        "module_l": ("length", None), "module_w": ("length", None),
        "body_h": ("length", 30.0),
        "channel_w": ("length", 16.0), "channel_d": ("length", 5.0),
        "slope_deg": ("number", 1.25), "channel_bottom_r": ("length", 1.2),
        "cassette_l": ("length", None), "cassette_w": ("length", None),
        "seat_depth": ("length", 14.0), "seat_clearance": ("length", 0.75),
        "module_pitch": ("length", 250.0), "corner_r": ("length", 4.0),
    },
    validators=(
        "form.water_channel_slope_ok", "form.water_channel_dims_ok",
        "form.no_standing_water_ir", "form.cassette_seat_fit_ok",
        "topology.water_channel_open", "topology.water_channel_floor_solid",
        "topology.single_connected_solid", "topology.cutout_present",
    ),
    apply=_water_rail_body,
    description="level rail body + recessed cassette seat + sloped open "
                "U-channel cut from the seat floor (flow -Y, corridors open both ends)",
))


# -- overflow_lip (feature) ---------------------------------------------------


def _overflow_lip(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The droplet-detachment edge: the channel already exits through the
    front face; this op UNDERCUTS the wall below the exiting floor by the
    air gap, leaving a lip_h-thick floor tongue whose edge stays sharp by
    never being blended (lip radius = the printed edge, assumed, checked).
    The relief void doubles as the open drip receiver."""
    state.require_base("overflow_lip")
    f = state.frame
    if "channel_floor_z_outlet" not in f:
        raise RecipeError("overflow_lip needs a water_rail_body base")
    lip_h, air_gap, lip_r = p["lip_h"], p["air_gap"], p["lip_r"]
    lip_z = f["channel_floor_z_outlet"]
    if lip_z - lip_h < 0.5:
        raise RecipeError(
            f"no wall below the lip to relieve (floor exits at z={lip_z:g}, "
            f"lip_h={lip_h:g})")
    face = f["rail_y0"]
    half = f["channel_w"] / 2.0 + CORRIDOR_MARGIN
    name = op_id or "lip"
    relief = Box3(-half, face - 1.0, -1.0, half, face + air_gap, lip_z - lip_h)
    state.cutboxes.append(CutBoxFeature(name=f"{name}_relief", box=relief))
    state.regions.extend([
        Region("overflow_lip", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-half, face - 1.0, lip_z - lip_h, half, face + 2.0,
                    f["channel_top_z"])),
        Region("drip_receiver", RegionRole.TRANSIENT_WATER_PATH, relief),
    ])
    state.frame.update(lip_z=lip_z, lip_h=lip_h, air_gap=air_gap, lip_r_assumed=lip_r)


_register(RecipeOpDecl(
    name="overflow_lip",
    kind="feature",
    params={
        "lip_h": ("length", 2.0), "air_gap": ("length", 1.5),
        "lip_r": ("length", 0.4),
    },
    validators=(
        "form.overflow_lip_geometry_ok", "form.no_secondary_water_channel",
        "topology.overflow_relief_open", "topology.cutout_present",
    ),
    apply=_overflow_lip,
    description="sharp overflow edge: air-gap undercut below the exiting "
                "channel floor; the relief void is the open drip receiver",
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
