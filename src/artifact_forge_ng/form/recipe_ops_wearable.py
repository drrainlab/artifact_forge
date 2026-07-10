"""Split-branch clamp and wearable recipe ops (Bio-1) — clamp halves,
axial channels, cord slots, forearm cuff body.
"""
from __future__ import annotations

import math
from typing import Any
from .regions import Box3, Region
from ..product.archetype import RegionRole
from .part import BoreFeature, CutBoxFeature
from .recipe_ops_core import RecipeError, RecipeState, RecipeOpDecl, _register


# -- split branch clamp (Bio-1, docs/BIOMORPHIC.md) ------------------------------


def _clamp_common(state: RecipeState, p: dict[str, Any]) -> Any:
    from .profiles_clamp import ClampHalfParams

    if state.section is not None:
        raise RecipeError("a clamp half must be the (single) base op")
    return ClampHalfParams(
        branch_d=p["branch_d"], gap=p["gap"], flange_t=p["flange_t"],
        bolt_y=p["bolt_y"], edge_m=p["edge_m"], wall=p["wall"],
        corner_r=p["corner_r"], land_angle=p["land_angle"],
        land_w=p["land_w"], pad_recess=p["pad_recess"],
        base_t=p.get("base_t", 8.0), top_t=p.get("top_t", 20.0),
        rail_w=p.get("rail_w", 20.0), rail_h=p.get("rail_h", 6.0),
        rail_angle=p.get("rail_angle", 10.0),
    )


def _clamp_finish(
    state: RecipeState, p: dict[str, Any], profile: Any, f: dict[str, float]
) -> None:
    """Shared tail of both halves: section, outline frame (in the Z-hole
    plane: x = extrusion axis, y = profile u), print orientation."""
    state.section = profile
    state.width = p["clamp_w"]
    state.kind = "section_extrude"
    state.print_orientation = "side_profile"
    state.frame.update(f)
    state.frame.update(
        outline_u0=0.0, outline_v0=-f["wing_u_out"],
        outline_u1=p["clamp_w"], outline_v1=f["wing_u_out"],
        outline_corner_r=0.0,
    )


def _clamp_bio_canvas(
    state: RecipeState, p: dict[str, Any], profile: Any, f: dict[str, float]
) -> None:
    """Publish the outer_shell as a developable ``profile_surface`` canvas
    (Bio-4M stage B) — the pattern of ``_revolve_band``'s cylindrical window,
    now the section unrolled along the extrusion. The bio applicator grows
    ribs + RECESSED organic windows there; a through-cut would breach the
    saddle, so the op computes ``safe_recess`` = the min wall from the canvas
    to the saddle circle minus a residual skin margin (the ONE internal
    feature sharing the base op's frame; the axial channel and cord slots sit
    farther out or are masked) and publishes it as FaceWindow.depth."""
    from .exoskeleton.profile_surface import profile_surface_canvas
    from .part import FaceWindow
    from .regions import Rect2D as _Rect2D, Region2D

    width = p["clamp_w"]
    canvas = profile_surface_canvas(profile.outer, width)
    surface = canvas.surface
    s0, s1 = canvas.s0, canvas.s1
    # seam MUST sit off the canvas (inside the mate/saddle block) — a rib
    # graph never crosses a discontinuity.
    if not (canvas.seam_s > s1 - 1e-6):
        raise RecipeError("profile_surface seam landed on the canvas")
    edge = 3.0
    win_s0, win_s1 = s0 + edge, s1 - edge
    x0, x1 = edge, width - edge
    if win_s1 <= win_s0 + 1.0 or x1 <= x0 + 1.0:
        return  # body too small for a bio skin — leave the region window-less
    window = _Rect2D(win_s0, x0, win_s1, x1)

    scz, sr = f["saddle_cz"], f["saddle_r"]
    wall_margin = p.get("window_wall", 1.2)
    min_wall = math.inf
    for s, (u, v) in zip(surface.s_breaks, surface.points):
        if s < s0 - 1e-9 or s > s1 + 1e-9:
            continue
        min_wall = min(min_wall, abs(math.hypot(u, v - scz) - sr))
    if not math.isfinite(min_wall):
        min_wall = wall_margin + 0.8
    safe_recess = max(0.8, min_wall - wall_margin)
    cap = p.get("window_depth", 0.0)
    if cap and cap > 0.0:
        safe_recess = min(safe_recess, cap)

    keepouts: list[Region2D] = []
    if canvas.rail_interval is not None:
        r_lo, r_hi = canvas.rail_interval
        k_lo, k_hi = max(win_s0, r_lo - 2.0), min(win_s1, r_hi + 2.0)
        if k_hi > k_lo + 1e-6:
            keepouts.append(Region2D(
                "rail_keepout", RegionRole.MOUNTING_SURFACE,
                _Rect2D(k_lo, x0, k_hi, x1)))

    state.windows["outer_shell"] = FaceWindow(
        origin=(0.0, 0.0, 0.0), tilt_deg=0.0,
        window=window, depth=safe_recess,
        keepouts=tuple(keepouts),
        mapping="profile_surface", surface=surface,
        note="profile_surface (Bio-4M stage B): developable section-sweep; "
             "organic windows are RECESSED (through-cuts would breach the "
             "saddle/channel)",
    )
    state.frame.update(
        skin_safe_recess=safe_recess,
        skin_canvas_s0=s0, skin_canvas_s1=s1,
        skin_canvas_span=s1 - s0, skin_seam_s=canvas.seam_s,
        skin_total_s=surface.total_s,
    )
    if p.get("skin_depth", 0.0):
        state.frame["skin_depth"] = p["skin_depth"]


def _clamp_half_lower(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Lower half of the split branch clamp: base slab, open saddle notch
    in the mating (top) edge, wing flanges carrying the bolt columns.

    The ``clamp_mate`` datum bakes the compression gap in: it sits at
    ``mate_z + gap`` — joints land datum-on-datum and cannot express an
    offset, so the LOWER half's datum carries the gap and the upper half
    (modeled mating-face-down, datum at v=0) poses with rotate [0,0,0]."""
    from .profiles_clamp import build_clamp_lower_profile

    cp = _clamp_common(state, p)
    try:
        profile, f = build_clamp_lower_profile(cp)
    except ValueError as exc:
        raise RecipeError(f"clamp_half_lower: {exc}") from exc
    _clamp_finish(state, p, profile, f)
    _clamp_bio_canvas(state, p, profile, f)
    w, mh = p["clamp_w"], f["saddle_mouth_half"]
    state.regions.extend([
        Region("saddle_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -mh, f["saddle_apex_v"] - p["pad_recess"],
                    w, mh, f["mate_z"])),
        Region("outer_shell", RegionRole.EXOSKELETON_PANEL,
               Box3(0.0, -f["body_half"], 0.0, w, f["body_half"], f["wing_v0"])),
    ])
    state.datums["clamp_mate"] = {
        "at": [w / 2.0, 0.0, f["mate_z"] + p["gap"]], "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["branch_axis"] = {
        "at": [w / 2.0, 0.0, f["saddle_cz"]], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="clamp_half_lower",
    kind="base",
    params={
        "branch_d": ("length", None), "clamp_w": ("length", None),
        "gap": ("length", 3.0), "base_t": ("length", 8.0),
        "flange_t": ("length", 10.0), "bolt_y": ("length", None),
        "edge_m": ("length", 10.0), "wall": ("length", 4.0),
        "corner_r": ("length", 2.5), "land_angle": ("angle", 50.0),
        "land_w": ("length", 14.0), "pad_recess": ("length", 1.2),
        "window_wall": ("length", 1.2), "window_depth": ("length", 0.0),
        "skin_depth": ("length", 0.0),
    },
    validators=(
        "form.saddle_geometry_ok",
        "form.pad_lands_present",
        "topology.cavity_open",
        "topology.single_connected_solid",
    ),
    apply=_clamp_half_lower,
    description="lower split-clamp half: open branch saddle + bolt wings "
                "(X = branch axis, prints on its section)",
))


def _clamp_half_upper(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Upper half, modeled MATING-FACE-DOWN (mating plane at v=0, saddle
    notch in the bottom edge, dovetail rail on top) — the assembly poses it
    with rotate [0,0,0], no flip needed. Its ``clamp_mate`` datum sits ON
    the mating plane; the gap is baked into the LOWER half's datum."""
    from .profiles_clamp import build_clamp_upper_profile

    cp = _clamp_common(state, p)
    try:
        profile, f = build_clamp_upper_profile(cp)
    except ValueError as exc:
        raise RecipeError(f"clamp_half_upper: {exc}") from exc
    _clamp_finish(state, p, profile, f)
    _clamp_bio_canvas(state, p, profile, f)
    w, mh = p["clamp_w"], f["saddle_mouth_half"]
    state.regions.extend([
        Region("saddle_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -mh, 0.0, w, mh, f["saddle_apex_v"] + p["pad_recess"])),
        Region("outer_shell", RegionRole.EXOSKELETON_PANEL,
               Box3(0.0, -f["body_half"], f["flange_t"],
                    w, f["body_half"], f["body_top_v"])),
        Region("rail_interface", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -f["rail_top_w"] / 2.0 - 1.0, f["rail_v0"],
                    w, f["rail_top_w"] / 2.0 + 1.0, f["rail_v1"] + 0.5)),
    ])
    state.datums["clamp_mate"] = {
        "at": [w / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["branch_axis"] = {
        "at": [w / 2.0, 0.0, f["saddle_cz"]], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="clamp_half_upper",
    kind="base",
    params={
        "branch_d": ("length", None), "clamp_w": ("length", None),
        "gap": ("length", 3.0), "flange_t": ("length", 10.0),
        "bolt_y": ("length", None), "edge_m": ("length", 10.0),
        "wall": ("length", 4.0), "corner_r": ("length", 2.5),
        "land_angle": ("angle", 50.0), "land_w": ("length", 14.0),
        "pad_recess": ("length", 1.2), "top_t": ("length", 20.0),
        "rail_w": ("length", 20.0), "rail_h": ("length", 6.0),
        "rail_angle": ("angle", 10.0),
        "window_wall": ("length", 1.2), "window_depth": ("length", 0.0),
        "skin_depth": ("length", 0.0),
    },
    validators=(
        "form.saddle_geometry_ok",
        "form.pad_lands_present",
        "topology.cavity_open",
        "topology.single_connected_solid",
        "form.dovetail_rail_profile",
        "topology.rail_present",
    ),
    apply=_clamp_half_upper,
    description="upper split-clamp half, mating-face-down: saddle + wings + "
                "male dovetail rail on top",
))


def _axial_channel(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A through cable channel along the extrusion (branch) axis, open at
    both ends — verified void end to end by topology.bores_open and placed
    clear of the saddle/rail by form.clamp_channel_clear."""
    state.require_base("axial_channel")
    name = op_id or "channel"
    state.bores.append(
        BoreFeature(
            name=name, axis="X", center=(0.0, p["y"], p["z"]),
            d=p["d"], span=(0.0, state.width), overshoot=(1.0, 1.0),
        )
    )
    state.frame.update(channel_z=p["z"], channel_y=p["y"], channel_d=p["d"])


_register(RecipeOpDecl(
    name="axial_channel",
    kind="feature",
    params={
        "d": ("length", 10.0), "y": ("length", 0.0), "z": ("length", None),
    },
    validators=("form.clamp_channel_clear", "topology.bores_open"),
    apply=_axial_channel,
    description="through cable channel along the extrusion axis, open both ends",
))


def _cord_slot_pair(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Two through slots near the saddle center (shock cord / zip tie for
    mounting) — they exit INTO the saddle void through the mating plane.
    cx = 0 means the width center; the keepout check keeps them honest
    around the bolt columns."""
    state.require_base("cord_slot_pair")
    mate_z = state.frame.get("mate_z")
    if mate_z is None:
        raise RecipeError("cord_slot_pair needs a clamp_half base (mate_z)")
    cx = p["cx"] if abs(p["cx"]) > 1e-9 else state.width / 2.0
    half_l, half_w = p["slot_l"] / 2.0, p["slot_w"] / 2.0
    name = op_id or "cord_slots"
    for i, sy in enumerate((-p["spacing"] / 2.0, p["spacing"] / 2.0)):
        state.cutboxes.append(
            CutBoxFeature(
                name=f"{name}_{i}",
                box=Box3(cx - half_l, sy - half_w, -1.0,
                         cx + half_l, sy + half_w, mate_z + 1.0),
            )
        )
        state.frame[f"{name}_{i}_v"] = sy
    state.frame[f"{name}_l"] = p["slot_l"]
    state.frame[f"{name}_w"] = p["slot_w"]


_register(RecipeOpDecl(
    name="cord_slot_pair",
    kind="feature",
    params={
        "slot_l": ("length", 8.0), "slot_w": ("length", 4.0),
        "spacing": ("length", None), "cx": ("length", 0.0),
    },
    validators=("form.cuts_respect_keepouts", "topology.cutout_present"),
    apply=_cord_slot_pair,
    description="through cord/tie slot pair exiting into the saddle void",
))


def _forearm_cuff_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Wearable forearm cuff (wave P2): open C-ring sized from body_fit,
    strap tabs at the mouth tips, three recessed TPU pad lands, payload
    snap-C on top — ONE constant section, printed on its profile.

    The ``outer_aesthetic_shell`` region is RESERVED for the bio skin: no
    profile_surface FaceWindow is published in v1 (mirror _clamp_bio_canvas
    here once the Bio-4M stage-B canvas lands for two-cavity sections)."""
    from .profiles_wearable import CuffParams, build_forearm_cuff_profile

    if state.section is not None:
        raise RecipeError("forearm_cuff_body must be the (single) base op")
    cp = CuffParams(
        arm_circumference=p["arm_circumference"],
        arm_clearance=p["arm_clearance"], wall=p["wall"],
        arm_capture_deg=p["arm_capture_deg"], land_angle=p["land_angle"],
        land_w=p["land_w"], pad_recess=p["pad_recess"],
        comfort_edge_r=p["comfort_edge_r"], tab_t=p["tab_t"],
        tab_len=p["tab_len"], payload_d=p["payload_d"],
        payload_clearance=p["payload_clearance"],
        payload_arc_deg=p["payload_arc_deg"], clip_wall=p["clip_wall"],
        neck_drop=p["neck_drop"], payload_mount=p["payload_mount"],
        groove_top_w=p["groove_top_w"], groove_bottom_w=p["groove_bottom_w"],
        groove_depth=p["groove_depth"], crown_wall=p["crown_wall"],
        crown_floor=p["crown_floor"],
    )
    try:
        profile, f = build_forearm_cuff_profile(cp)
    except ValueError as exc:
        raise RecipeError(f"forearm_cuff_body: {exc}") from exc
    w = p["cuff_l"]
    state.section = profile
    state.width = w
    state.kind = "section_extrude"
    state.print_orientation = "side_profile"
    state.frame.update(f)
    v_ext = max(f["tab_u_out"], f["arm_r_outer"])
    state.frame.update(
        outline_u0=0.0, outline_v0=-v_ext, outline_u1=w, outline_v1=v_ext,
        outline_corner_r=0.0,
    )
    r_ai, r_ao = f["arm_r_inner"], f["arm_r_outer"]
    socket = "socket_top_v" in f
    if socket:
        ch, v_ct = f["crown_half_w"], f["socket_top_v"]
        state.regions.extend([
            Region("arm_contact", RegionRole.BODY_CONTACT_SURFACE,
                   Box3(0.0, -r_ai, f["arm_mouth_tip_v"] + 2.0, w, r_ai, r_ai)),
            Region("strap_land_left", RegionRole.MOUNTING_SURFACE,
                   Box3(0.0, -f["tab_u_out"], f["tab_v_bot"],
                        w, -f["tab_u_x"] - 1.0, f["tab_v_top"])),
            Region("strap_land_right", RegionRole.MOUNTING_SURFACE,
                   Box3(0.0, f["tab_u_x"] + 1.0, f["tab_v_bot"],
                        w, f["tab_u_out"], f["tab_v_top"])),
            # The whole socket crown is an interface keepout: nothing may
            # cut into the walls that retain the adapter foot.
            Region("socket_crown", RegionRole.INTERFACE_KEEPOUT,
                   Box3(0.0, -ch, f["crown_shoulder_v"], w, ch, v_ct)),
            Region("outer_aesthetic_shell", RegionRole.EXOSKELETON_PANEL,
                   Box3(0.0, -r_ao, 0.0, w, r_ao, f["crown_shoulder_v"])),
        ])
        state.datums["arm_axis"] = {
            "at": [w / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0],
        }
        state.datums["payload_socket"] = {
            "at": [w / 2.0, 0.0, v_ct], "rotate": [0.0, 0.0, 0.0],
        }
        return
    r_pi, r_po = f["payload_r_inner"], f["payload_r_outer"]
    p_cv, n = f["payload_cv"], f["neck_half_w"]
    p_h = (360.0 - f["payload_arc_deg"]) / 2.0
    tip_u = r_pi * math.cos(math.radians(90.0 - p_h))
    tip_v = p_cv + r_pi * math.sin(math.radians(90.0 - p_h))
    tip_o = p_cv + r_po * math.sin(math.radians(90.0 - p_h))
    state.regions.extend([
        # The BODY_CONTACT keepout deliberately starts 2 mm ABOVE the mouth
        # tips: tabs and strap slots live at/below tip level, so the coarse
        # AABB never vetoes a legal strap cut; the precise circle guard is
        # form.strap_access_ok + the applicator's own check.
        Region("arm_contact", RegionRole.BODY_CONTACT_SURFACE,
               Box3(0.0, -r_ai, f["arm_mouth_tip_v"] + 2.0, w, r_ai, r_ai)),
        # Strap windows start OUTSIDE the ring wall (tab_u_x, the chord-
        # mouth junction) — the modifier can only pierce clear tab plate.
        Region("strap_land_left", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -f["tab_u_out"], f["tab_v_bot"],
                    w, -f["tab_u_x"] - 1.0, f["tab_v_top"])),
        Region("strap_land_right", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, f["tab_u_x"] + 1.0, f["tab_v_bot"],
                    w, f["tab_u_out"], f["tab_v_top"])),
        Region("payload_saddle", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -r_pi, p_cv - r_pi, w, r_pi, p_cv + r_pi)),
        Region("clip_flexure_left", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, -tip_u - 3.0, tip_v - 3.0, w, -tip_u + 3.0,
                    tip_o + 2.0)),
        Region("clip_flexure_right", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, tip_u - 3.0, tip_v - 3.0, w, tip_u + 3.0,
                    tip_o + 2.0)),
        Region("outer_aesthetic_shell", RegionRole.EXOSKELETON_PANEL,
               Box3(0.0, -r_ao, 0.0, w, r_ao,
                    math.sqrt(r_ao * r_ao - n * n))),
    ])
    state.datums["arm_axis"] = {
        "at": [w / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["payload_axis"] = {
        "at": [w / 2.0, 0.0, p_cv], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="forearm_cuff_body",
    kind="base",
    params={
        "arm_circumference": ("length", None), "cuff_l": ("length", None),
        "arm_clearance": ("length", 6.0), "wall": ("length", 4.0),
        "arm_capture_deg": ("angle", 240.0), "land_angle": ("angle", 45.0),
        "land_w": ("length", 14.0), "pad_recess": ("length", 1.5),
        "comfort_edge_r": ("length", 2.0), "tab_t": ("length", 4.0),
        "tab_len": ("length", 26.0), "payload_d": ("length", 25.0),
        "payload_clearance": ("length", 0.3),
        "payload_arc_deg": ("angle", 240.0), "clip_wall": ("length", 3.0),
        "neck_drop": ("length", 4.0), "payload_mount": ("choice", "snap_clip"),
        "groove_top_w": ("length", 12.0),
        "groove_bottom_w": ("length", 17.0),
        "groove_depth": ("length", 6.0), "crown_wall": ("length", 3.5),
        "crown_floor": ("length", 3.0),
    },
    validators=(
        "form.body_clearance_ok",
        "form.arm_mouth_dons_ok",
        "form.comfort_edge_radius_ok",
        "form.pad_recess_exists",
        "form.payload_mount_not_on_skin_side",
        "form.payload_retention_ok",
        "topology.cavity_open",
        "topology.payload_void_open",
        "topology.single_connected_solid",
    ),
    apply=_forearm_cuff_body,
    description="wearable forearm cuff: body_fit C-ring + strap tabs + "
                "TPU pad lands + payload snap-C (X = forearm axis, "
                "prints on its section)",
))
