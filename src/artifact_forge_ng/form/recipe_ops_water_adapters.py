"""Vertical-farm fluid adapter ops — inlet cap (VF-9.2 chute-cap),
collector endcap, profile reference proxy.
"""
from __future__ import annotations

import math
from typing import Any
from ..product.archetype import RegionRole
from .profiles_plate import rounded_rect_loop
from .regions import Box3, Region
from .section import SectionProfile
from .part import BoreFeature, ChannelCutFeature, CutBoxFeature, FunnelCutFeature, RibFeature
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .recipe_ops_water_common import DRIP_INSET, ORIFICE_LEN, CAP_COVERED_RUN_MAX


# -- VF-3 fluid adapters --------------------------------------------------------
#
# Both adapters use a LOCAL FRAME ANCHORED AT THE RAIL FACE PLANE (local
# y=0 = the rail face the adapter hangs on) and at the fluid handover
# height (the fluid datum). Everything else — saddle, spout/tongue, tray —
# is derived from that anchor, so datum-on-datum posing lands the saddle
# on the wall by construction (verified, not hoped: assembly.saddle_hang_ir).


def _inlet_cap_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The Water Inlet Cap (VF-9.2 chute-cap): a support-free Г-hook whose water
    path is VISIBLE — no closed horizontal tunnel, no ambiguous through bore.
    The path: a vertical TUBE SOCKET in the tower (blind, with a stop shoulder —
    the tube cannot be pushed through) -> a narrow DRIP ORIFICE through the stop
    -> a small covered CHAMBER (a short drop shaft) -> an OPEN-TOP CHUTE (a
    U-trough: floor + two walls) that carries the drip inboard and drops it off
    the nose tip onto the rail's floored lip-seat, DRIP_INSET inside the channel
    (the mounted row tilt then carries the water along the rail channel — the
    cap transports nothing sideways itself; the level trough drains by the same
    tilt). The cap HOOKS the outboard edge of the rail back wall (short rest
    ledge + outboard leg/foot to the bed, VF-9 Part B) and prints AS-MODELED.
    Local frame: y=0 = the rail back (+Y) face, -Y inboard toward the channel;
    z=0 = the cap body bottom, wall top at z = saddle_depth."""
    if state.section is not None:
        raise RecipeError("inlet_cap_body must be the (single) base op")
    cap_w, cap_h = p["cap_w"], p["cap_h"]
    tube_od, grip = p["tube_od"], p["bore_clearance"]
    fit = p["saddle_fit"]
    saddle_depth = p["saddle_depth"]
    hang_drop = p["hang_drop"]
    nose_w = p["spout_w"]
    rail_channel_w = p["rail_channel_w"]
    hook_reach = p.get("hook_reach", 3.5)  # rest-ledge reach onto the wall top
    socket_depth = p.get("socket_depth", 12.0)
    orifice_d = p.get("orifice_d", 5.0)
    socket_d = tube_od + grip
    z_exit = saddle_depth - hang_drop
    if z_exit > -1.0:
        raise RecipeError(
            f"nose exit z={z_exit:g} does not descend below the body — "
            "hang_drop must exceed saddle_depth")
    if nose_w > rail_channel_w - 2.0:
        raise RecipeError(
            f"nose {nose_w:g} cannot dip into the {rail_channel_w:g} rail channel")
    if not (2.5 <= hook_reach <= 5.0):
        raise RecipeError(
            f"hook_reach {hook_reach:g} outside 2.5..5.0 — the rest ledge must "
            "be a short printable overhang on the wall top, not a deep cantilever")
    if not (8.0 <= socket_depth <= 14.0):
        raise RecipeError(f"socket_depth {socket_depth:g} outside 8..14")
    if not (4.0 <= orifice_d <= tube_od - 2.0):
        raise RecipeError(
            f"orifice_d {orifice_d:g} outside 4..{tube_od - 2.0:g} — the stop "
            "shoulder must be real (narrower than the tube) yet not clog")

    y_leg = fit                    # outboard leg inboard face (fit off the wall)
    y_ledge_in = -hook_reach       # rest-ledge inboard edge (short reach)
    trough_half = nose_w / 2.0     # trough outer half-width (fits the channel)
    slot_half = trough_half - 2.0  # trough inner half-width (2mm walls)
    # the socket needs solid tower on both sides of its Ø in Y:
    y_sock = y_leg + 1.6 + socket_d / 2.0            # inboard wall >= 1.6
    y_out = y_sock + socket_d / 2.0 + 1.9            # outboard wall >= 1.9
    y_chamber_out = y_sock + orifice_d / 2.0 + 0.3   # chamber covers the orifice
    if y_chamber_out - y_leg > CAP_COVERED_RUN_MAX:
        raise RecipeError(
            f"covered chamber run {y_chamber_out - y_leg:.1f} exceeds "
            f"{CAP_COVERED_RUN_MAX:g} — a closed horizontal water tunnel")
    stop_z = cap_h - socket_depth        # the tube-stop shoulder plane
    chamber_top_z = stop_z - ORIFICE_LEN  # the chamber ceiling (orifice exit)
    u0, u1 = -cap_w / 2.0, cap_w / 2.0
    state.section = SectionProfile(
        name="recipe",
        outer=rounded_rect_loop(u0, y_ledge_in, u1, y_out, p["corner_r"]),
        plane="XY", width_axis="Z",
    )
    state.width = cap_h
    name = op_id or "cap"

    # HOOK SLOT: clear the wall's outboard strip under the rest ledge so the
    # ledge lands on the wall top and the leg grips the +Y face (open bottom).
    slot = Box3(u0 - 1.0, y_ledge_in - 0.5, -1.0, u1 + 1.0, y_leg, saddle_depth)
    state.cutboxes.append(CutBoxFeature(name=f"{name}_saddle_slot", box=slot))
    # CHAMBER: the short covered drop shaft under the orifice — cut into the
    # tower interior; the trough floor rib (welded after all cuts) closes its
    # bottom. Ceiling = a counterbore-scale 2x`slot_half` bridge, printable.
    chamber = Box3(-slot_half, y_leg, z_exit - 1.0,
                   slot_half, y_chamber_out, chamber_top_z)
    state.cutboxes.append(CutBoxFeature(name=f"{name}_chamber", box=chamber))
    # SKY SLOT: open the roof/ledge over the chute run — the water path is
    # visible and brushable from above. z0 below the floor keeps the cut
    # open-bottom at IR (the floor rib closes it after welding).
    sky = Box3(-slot_half, y_ledge_in - 0.5, z_exit - 1.0,
               slot_half, y_leg, cap_h + 1.0)
    state.cutboxes.append(CutBoxFeature(name=f"{name}_chute_sky", box=sky))
    # U-FOOT: ground the leg/tower to the bed AROUND the chamber (a single
    # full-width foot would refill the chamber — ribs weld after cuts). Welded
    # FIRST: the feet root in the tower body and reach the bed, giving the
    # walls and floor below z=0 something to weld onto.
    for tag, bx in (("e", Box3(slot_half, y_leg, z_exit - 1.0, u1, y_out, 0.6)),
                    ("w", Box3(u0, y_leg, z_exit - 1.0, -slot_half, y_out, 0.6)),
                    ("c", Box3(-slot_half, y_chamber_out, z_exit - 1.0,
                               slot_half, y_out, 0.6))):
        state.ribs.append(RibFeature(name=f"{name}_foot_{tag}", box=bx))
    # OPEN CHUTE: a U-trough — two walls (rooted in the tower), then the level
    # floor (welds onto the feet/walls; drains inboard by the mounted row
    # tilt, exactly like the rail channel itself). The tip edge at
    # y = -DRIP_INSET drips from z_exit into the channel. Same outer envelope
    # as the VF-9B nose: it passes through the rail's inlet corridor void.
    for tag, x0, x1 in (("e", slot_half, trough_half),
                        ("w", -trough_half, -slot_half)):
        state.ribs.append(RibFeature(
            name=f"{name}_nose_wall_{tag}",
            box=Box3(x0, -DRIP_INSET, z_exit - 1.0, x1, y_chamber_out,
                     saddle_depth)))
    floor = Box3(-trough_half, -DRIP_INSET, z_exit - 1.0,
                 trough_half, y_chamber_out, z_exit)
    state.ribs.append(RibFeature(name=f"{name}_nose_floor", box=floor))
    # TUBE SOCKET: blind, open-top — its flat bottom IS the stop shoulder the
    # tube seats on (the tube physically cannot be pushed through). The DRIP
    # ORIFICE continues coaxially through the stop into the chamber.
    state.bores.append(BoreFeature(
        name=f"{name}_hose_socket", axis="Z", center=(0.0, y_sock, 0.0),
        d=socket_d, span=(stop_z, cap_h), overshoot=(0.0, 1.0),
    ))
    state.bores.append(BoreFeature(
        name=f"{name}_hose_drop", axis="Z", center=(0.0, y_sock, 0.0),
        d=orifice_d, span=(chamber_top_z, stop_z), overshoot=(1.0, 1.0),
    ))

    state.regions.extend([
        Region("spout_path", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-slot_half, -DRIP_INSET - 0.5, z_exit - 1.1,
                    slot_half, y_sock + socket_d / 2.0 + 0.1, cap_h + 0.5)),
        Region("saddle", RegionRole.INTERFACE_KEEPOUT, slot),
    ])

    # Endcap dock magnets (VF-9 Part B): Y-axis pockets in the leg's inboard
    # face, docking to the rail's +Y END-FACE pockets — vertical faces print
    # support-free. Alignment-only, press-fit, n/a when off.
    dock_z = saddle_depth - p.get("dock_drop", 4.0)  # same drop below the wall top
    _collect_dock(state, p, name, dock_y=y_leg, z_plane=dock_z,
                  side_front=False, style="face")

    state.frame.update(
        outline_u0=u0, outline_v0=y_ledge_in, outline_u1=u1, outline_v1=y_out,
        outline_corner_r=p["corner_r"],
        hose_tube_od=tube_od, hose_bore_d=socket_d,
        hose_socket_depth=socket_depth, hose_socket_y=y_sock,
        drip_orifice_d=orifice_d,
        chute_tip_y=-DRIP_INSET, chute_uphill_y=y_chamber_out,
        spout_w=nose_w, rail_channel_w=rail_channel_w,
        channel_center_x=0.0, channel_w=2.0 * slot_half, channel_top_z=cap_h,
        channel_floor_z_outlet=z_exit, channel_y_outlet=-DRIP_INSET,
        saddle_slot_y0=y_ledge_in, saddle_slot_y1=y_leg,
        saddle_floor_z=saddle_depth, saddle_fit=fit,
        hang_drop=hang_drop, hang_mode=1.0,          # 1 = one-sided hook
        cap_hook_reach=hook_reach, cap_leg_y=y_leg,
        cap_nose_bottom_z=z_exit, cap_roof_z=saddle_depth,
    )
    # The spout datum = the REAL drip point: the trough tip edge, DRIP_INSET
    # inboard of the rail face — paired with the rail's feed datum inset.
    state.datums["spout"] = {"at": [0.0, -DRIP_INSET, z_exit],
                             "rotate": [0.0, 0.0, 0.0]}
    state.datums["tube_in"] = {"at": [0.0, y_sock, cap_h],
                               "rotate": [0.0, 0.0, 0.0]}
    # Prints as-modeled: short rest ledge, trough floor and feet reach the bed,
    # socket/orifice vertical, chamber ceiling a counterbore-scale bridge.


_register(RecipeOpDecl(
    name="inlet_cap_body",
    kind="base",
    params={
        "cap_w": ("length", 64.0), "cap_h": ("length", 22.0),
        "tube_od": ("length", 9.0), "bore_clearance": ("length", 0.4),
        "socket_depth": ("length", 12.0), "orifice_d": ("length", 5.0),
        "rail_wall_t": ("length", 13.25), "saddle_fit": ("length", 0.4),
        "saddle_depth": ("length", 8.0), "hang_drop": ("length", 16.5),
        "spout_w": ("length", 14.0), "rail_channel_w": ("length", 16.0),
        "corner_r": ("length", 3.0), "hook_reach": ("length", 3.5),
        "dock_magnets": ("bool", False),
        "magnet_d": ("length", 6.0), "magnet_t": ("length", 2.0),
        "dock_fit_clearance": ("length", 0.2),
        "dock_x": ("length", 22.0), "dock_inset": ("length", 7.0),
        "dock_drop": ("length", 4.0),
    },
    validators=(
        "form.hose_bore_ok", "form.spout_drop_path_ok",
        "form.cap_water_path_visible",
        "form.dock_pockets_dry",
        "form.no_standing_water_ir",
        "manufacturing.cap_supportless_verified",
        "topology.fluid_path_open", "topology.single_connected_solid",
        "topology.cutout_present", "topology.ribs_present",
    ),
    apply=_inlet_cap_body,
    description="support-free Г-hook inlet cap (VF-9 Part B): vertical hose "
                "bore through a nose column dipping into the rail inlet "
                "channel; hooks the wall's outboard edge, docks on the +Y "
                "face; prints as-modeled with no floating cantilever",
))


def _collect_dock(state: RecipeState, p: dict[str, Any], name: str, *,
                  dock_y: float, z_plane: float, side_front: bool,
                  style: str = "top") -> None:
    """Shared endcap docking magnets. ``style="top"`` (VF-6, collector): a pair
    of DOWN-facing Z pockets in the arm underside that contacts the rail END
    wall TOP — they bore UP into the arm at x = +-dock_x. ``style="face"``
    (VF-9 Part B, cap): a pair of -Y-facing Y-axis pockets in the leg's inboard
    face (at y = dock_y, z = z_plane) that dock to the rail's +Y END-FACE
    pockets — vertical-face pockets print support-free. Gated by
    ``dock_magnets``; alignment-only, press-fit, n/a when off."""
    if not p.get("dock_magnets", False):
        state.frame.update(dock_pocket_count=0)
        return
    d = p.get("magnet_d", 6.0) + p.get("dock_fit_clearance", 0.2)
    depth = p.get("magnet_t", 2.0) + 0.4
    dock_x = p.get("dock_x", 22.0)
    for x_label, x in (("e", dock_x), ("w", -dock_x)):
        if style == "face":
            # -Y-facing pocket: mouth opens -Y at the leg's inboard face, blind
            # +Y into the leg body (open lo, blind hi).
            state.bores.append(BoreFeature(
                name=f"{name}_dock_{x_label}", axis="Y",
                center=(x, dock_y, z_plane), d=d,
                span=(dock_y, dock_y + depth), overshoot=(1.0, 0.0),
            ))
            state.regions.append(Region(
                f"endcap_dock_{x_label}", RegionRole.INTERFACE_KEEPOUT,
                Box3(x - d / 2.0 - 1.0, dock_y - 1.0, z_plane - d / 2.0 - 1.0,
                     x + d / 2.0 + 1.0, dock_y + depth + 1.0,
                     z_plane + d / 2.0 + 1.0)))
        else:
            state.bores.append(BoreFeature(
                name=f"{name}_dock_{x_label}", axis="Z",
                center=(x, dock_y, 0.0), d=d,
                span=(z_plane, z_plane + depth), overshoot=(1.0, 0.0),
            ))
            state.regions.append(Region(
                f"endcap_dock_{x_label}", RegionRole.INTERFACE_KEEPOUT,
                Box3(x - d / 2.0 - 1.0, dock_y - d / 2.0 - 1.0, z_plane - 1.0,
                     x + d / 2.0 + 1.0, dock_y + d / 2.0 + 1.0,
                     z_plane + depth + 1.0)))
    state.frame.update(
        dock_pocket_count=2, dock_pocket_d=d, dock_pocket_depth=depth,
        dock_x=dock_x, dock_inset=p.get("dock_inset", 7.0), dock_y=dock_y,
        dock_z_plane=z_plane, dock_side_front=1.0 if side_front else 0.0,
        dock_style_face=1.0 if style == "face" else 0.0,
        dock_fit_clearance=d - p.get("magnet_d", 6.0),
    )


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
    # A drop-in strainer needs a deeper tray so a radial funnel sump fits
    # around the drain between the back wall and the docking arm — bump the
    # back reach (and relax the band) when screen_seat is on.
    screen_on = p.get("screen_seat", False)
    if screen_on:
        drain_extension = max(drain_extension, 12.0)
    band_hi = 22.0 if screen_on else 14.0
    if not (8.0 - 1e-9 <= drain_extension <= band_hi + 1e-9):
        raise RecipeError(
            f"drain_extension {drain_extension:g} outside 8..{band_hi:g}")
    drain_grip = p.get("drain_grip", 12.0)  # solid depth for the push-in tube
    # Strainer basket footprint (compact sink-filter cup) — read early so the
    # drain can be centred in the arm-clear tray for a radial funnel sump.
    bkt_x = p.get("screen_seat_w", 24.0)
    bkt_y = p.get("screen_seat_d", 13.0)
    s_clear = p.get("screen_seat_clearance", 1.0)
    mouth_x = bkt_x + 2.0 * s_clear
    mouth_y = bkt_y + 2.0 * s_clear

    rim_z = 3.0
    # The catch floor sits catch_fall below the handover datum so the mouth
    # captures the lip; the tray then slopes back to the sump's low point.
    catch_fall = p["catch_fall"]
    floor_at_catch = -catch_fall
    depth_start = rim_z + catch_fall
    y_drain_wall = -(capture_depth + 3.0 + drain_extension)  # sump outer end
    # The vertical drain sits at the tray's TRUE low point (VF-7): the floor
    # slopes down to the drain and NOTHING behind it is deeper, so the tray
    # empties instead of pooling at the back (before, the drain sat forward
    # of the deep end and water stood behind it). The bore stays inboard of
    # the sump wall so it keeps solid grip for the push-in tube.
    y_drain = y_drain_wall + 3.0 + bore_d / 2.0 + 1.0  # snug at the back (default)
    if screen_on:
        # Centre the sump well between the back wall and the arm-clear tray
        # front (the docking arm roofs y >= -1.5), so a radial funnel fits
        # around the drain with the basket overhanging the bore on every side.
        arm_clear = -1.5 - 2.0
        lo = y_drain_wall + wall + mouth_y / 2.0   # back: funnel touches the wall
        hi = arm_clear - mouth_y / 2.0             # front: clear of the arm roof
        grip_lo = y_drain_wall + 3.0 + bore_d / 2.0 + 1.0  # keep the bore grip
        lo = max(lo, grip_lo)
        if lo > hi + 1e-6:
            raise RecipeError(
                f"strainer sump {mouth_y:g} deep does not fit the tray "
                f"({hi - lo:g} short) — raise drain_extension")
        y_drain = (lo + hi) / 2.0
    run = 1.6 - y_drain  # channel span: catch -> the drain (the low point)
    depth_end = depth_start + run * math.tan(math.radians(slope))
    floor_low = rim_z - depth_end  # deepest floor point (design z), at the drain
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
        y0=1.6, y1=y_drain, z_top=rim_z + dz,
        width=tray_w_inner, depth_start=depth_start, depth_end=depth_end,
        bottom_r=1.0,
    ))
    name = op_id or "collector"
    # Vertical drain (VF-4.2): the bore descends from the sump's low floor
    # point straight through the solid base and out the bottom — the push-in
    # tube enters FROM BELOW and routes under the row. A vertical bore has
    # no ceiling to bridge, so it prints supportless as-modeled.
    state.bores.append(BoreFeature(
        name=f"{name}_drain_hose", axis="Z",
        center=(0.0, y_drain, 0.0),
        d=bore_d, span=(0.0, floor_low + dz + 0.5),
        overshoot=(1.0, 1.0),
    ))
    # Strainer sump (VF-8, param-gated): a LOWERED sump WELL around the drain
    # fed by a RADIAL FUNNEL — the tray floor slopes down to the sump from
    # every side (a FunnelCutFeature, the kernel's first floor that slopes in
    # both X and Y), the drain sits at the sump's absolute low point, and a
    # compact drop-in strainer basket seats in the well OVER the drain. Water
    # falls INTO the basket (it is not a wall across the tray); a clog rises
    # visibly in the OPEN tray. The seat FRAME KEYS + datum are ALWAYS
    # published; the funnel + well geometry is cut only when screen_seat is on.
    sx = mouth_x / 2.0                        # mouth = basket + clearance (set early)
    my0, my1 = y_drain - mouth_y / 2.0, y_drain + mouth_y / 2.0
    tray_floor_z = floor_low + dz            # channel low point = tray floor at drain
    seat_floor_z = tray_floor_z
    if screen_on:
        sump_depth = p.get("screen_sump_depth", 5.0)
        seat_floor_z = tray_floor_z - sump_depth
        # radial funnel opening: reaches the back sump wall and forward to the
        # arm-clear tray front, converging to the well mouth. Skewed (mouth at
        # the drain, opening spanning the tray) so it drains the whole floor.
        top_back = min(y_drain_wall + wall, my0)          # touch the back wall
        top_front = max(-1.5 - 2.0, my1)                  # stay clear of the arm roof
        top_x = min(p.get("screen_funnel_w", 74.0), tray_w_inner - 6.0)
        top_x = max(top_x, mouth_x + 2.0)                 # keep mouth enclosed
        top_cy = (top_back + top_front) / 2.0
        state.funnel_cuts.append(FunnelCutFeature(
            name=f"{name}_sump_funnel",
            bottom_center=(0.0, y_drain), top_center=(0.0, top_cy),
            z_top=tray_floor_z, z_bottom=seat_floor_z,
            top=(top_x, top_front - top_back), bottom=(mouth_x, mouth_y),
        ))
        # Open the roof over the well: the sump reaches BEHIND the drain but the
        # tray channel only opens the top down to the drain, so the well's back
        # half would be roofed. This vertical shaft (well mouth up to the rim)
        # lets the basket drop in and a brush reach; it drains through the funnel
        # + bore below (no_standing_water via the through-bore exemption).
        state.cutboxes.append(CutBoxFeature(
            name=f"{name}_sump_shaft",
            box=Box3(-sx, my0, tray_floor_z, sx, my1, rim_z + dz)))
        state.regions.append(Region(
            "screen_seat", RegionRole.INTERFACE_KEEPOUT,
            Box3(-sx, my0, seat_floor_z, sx, my1, rim_z + dz)))
        # The strainer-sump frame keys + datum are published ONLY when a sump is
        # actually cut. A base collector must publish NO screen_sump_floor_z, so
        # the four funnel checks (checks_water.py) stay on their `is None -> n/a`
        # gate instead of failing on a non-existent sump.
        state.frame.update(
            screen_seat_u0=-sx, screen_seat_v0=my0,
            screen_seat_u1=sx, screen_seat_v1=my1,
            screen_seat_floor_z=seat_floor_z, screen_seat_clearance=s_clear,
            screen_seat_drain_y=y_drain, screen_seat_drain_d=bore_d,
            screen_sump_floor_z=seat_floor_z, screen_funnel_top_z=tray_floor_z,
            tray_overflow_z=rim_z + dz,
        )
        state.datums["screen_seat"] = {
            "at": [0.0, y_drain, seat_floor_z], "rotate": [0.0, 0.0, 0.0]}
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

    # Endcap dock magnets (VF-6): the arm underside sits flat on the LAST
    # rail's front wall top (z = arm_z0, the module height). A pair of
    # DOWN-facing Z pockets there docks onto matching UP pockets in that
    # rail's front-end wall top — magnet to magnet, alignment-only. The
    # pockets bore UP into the solid arm (a plastic floor above), far from
    # the tray, and print with a short bridged roof.
    _collect_dock(state, p, name, dock_y=p.get("dock_inset", 7.0),
                  z_plane=arm_z0, side_front=True)

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
        "dock_magnets": ("bool", False),
        "magnet_d": ("length", 6.0), "magnet_t": ("length", 2.0),
        "dock_fit_clearance": ("length", 0.2),
        "dock_x": ("length", 22.0), "dock_inset": ("length", 7.0),
        "screen_seat": ("bool", False),
        "screen_seat_w": ("length", 24.0), "screen_seat_d": ("length", 13.0),
        "screen_sump_depth": ("length", 5.0), "screen_funnel_w": ("length", 74.0),
        "screen_seat_clearance": ("length", 0.75),
    },
    validators=(
        "form.hose_bore_ok", "form.collector_tray_drains",
        "form.collector_receiver_matches_final_lap",
        "form.receiver_open_top_cleanable",
        "form.collector_drain_bore_supportless",
        "form.collector_structure_sturdy",
        "form.dock_pockets_dry",
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
