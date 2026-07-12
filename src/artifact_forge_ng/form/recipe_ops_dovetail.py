"""Dovetail adapter body op.

NOTE: registers AFTER the water ops to preserve the original RECIPE_OPS
insertion order; semantically core.
"""
from __future__ import annotations

from typing import Any
from .regions import Box3, Region
from ..product.archetype import RegionRole
from .part import BoreFeature
from .recipe_ops_core import RecipeError, RecipeState, RecipeOpDecl, _register




def _dovetail_adapter_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Payload adapter (wave A1): male dovetail foot sliding into the cuff
    socket along the arm axis, carrying a snap-C clip or a flat accessory
    plate. Axial retention is friction-only in v1 (a cold-shoe reality,
    stated, not hidden) — an end stop is a future op."""
    from .profiles_wearable import AdapterParams, build_dovetail_adapter_profile

    if state.section is not None:
        raise RecipeError("dovetail_adapter_body must be the (single) base op")
    ap = AdapterParams(
        head=p["head"], groove_top_w=p["groove_top_w"],
        groove_bottom_w=p["groove_bottom_w"], groove_depth=p["groove_depth"],
        fit_clearance=p["fit_clearance"], base_w=p["base_w"],
        base_t=p["base_t"], payload_d=p["payload_d"],
        payload_clearance=p["payload_clearance"],
        payload_arc_deg=p["payload_arc_deg"], clip_wall=p["clip_wall"],
        neck_drop=p["neck_drop"], plate_w=p["plate_w"],
        hole_span=p["hole_span"], corner_r=p["corner_r"],
    )
    try:
        profile, f = build_dovetail_adapter_profile(ap)
    except ValueError as exc:
        raise RecipeError(f"dovetail_adapter_body: {exc}") from exc
    w = p["adapter_l"]
    state.section = profile
    state.width = w
    state.kind = "section_extrude"
    state.print_orientation = "side_profile"
    state.frame.update(f)
    bw2 = f["base_w"] / 2.0
    state.frame.update(
        outline_u0=0.0, outline_v0=-bw2, outline_u1=w, outline_v1=bw2,
        outline_corner_r=0.0,
    )
    state.regions.append(
        Region("foot_interface", RegionRole.INTERFACE_KEEPOUT,
               Box3(0.0, -f["dovetail_top_w"] / 2.0, 0.0,
                    w, f["dovetail_top_w"] / 2.0, f["foot_plane_v"])),
    )
    state.datums["mount_foot"] = {
        "at": [w / 2.0, 0.0, f["foot_plane_v"]], "rotate": [0.0, 0.0, 0.0],
    }
    if ap.head == "snap_clip":
        state.regions.extend([
            Region("payload_saddle", RegionRole.SOFT_CONTACT_SURFACE,
                   Box3(0.0, -f["payload_r_inner"],
                        f["payload_cv"] - f["payload_r_inner"],
                        w, f["payload_r_inner"],
                        f["payload_cv"] + f["payload_r_inner"])),
        ])
        state.datums["payload_axis"] = {
            "at": [w / 2.0, 0.0, f["payload_cv"]], "rotate": [0.0, 0.0, 0.0],
        }
    else:
        # accessory plate: two vertical through-HOLES on the hole span —
        # HoleFeatures, so the plate is a legal screw_joint B side (its
        # holes land on a carrier's boss pilots)
        from .part import HoleFeature
        plate_t = f["base_top_v"] - f["foot_plane_v"]
        for uy in (-p["hole_span"] / 2.0, p["hole_span"] / 2.0):
            state.holes.append(HoleFeature(
                at=(w / 2.0, uy, f["base_top_v"]),
                screw=str(p.get("hole_screw", "M4")), through=plate_t,
                countersink=False,
            ))
        state.regions.append(
            Region("accessory_plate", RegionRole.MOUNTING_SURFACE,
                   Box3(0.0, -bw2, f["foot_plane_v"], w, bw2,
                        f["base_top_v"])),
        )
        state.datums["plate_top"] = {
            "at": [w / 2.0, 0.0, f["base_top_v"]], "rotate": [0.0, 0.0, 0.0],
        }


_register(RecipeOpDecl(
    name="dovetail_adapter_body",
    kind="base",
    params={
        "head": ("choice", "snap_clip"), "adapter_l": ("length", None),
        "groove_top_w": ("length", 12.0),
        "groove_bottom_w": ("length", 17.0),
        "groove_depth": ("length", 6.0), "fit_clearance": ("length", 0.25),
        "base_w": ("length", 30.0), "base_t": ("length", 4.0),
        "payload_d": ("length", 25.0), "payload_clearance": ("length", 0.3),
        "payload_arc_deg": ("angle", 240.0), "clip_wall": ("length", 3.0),
        "neck_drop": ("length", 4.0), "plate_w": ("length", 40.0),
        "hole_span": ("length", 20.0), "hole_d": ("length", 4.5),
        "hole_screw": ("choice", "M4"),
        "corner_r": ("length", 2.0),
    },
    validators=(
        "form.dovetail_foot_profile_ok",
        "topology.single_connected_solid",
    ),
    apply=_dovetail_adapter_body,
    description="payload adapter: male dovetail foot + snap-C clip or "
                "accessory plate (slides on the cuff socket along X)",
))


# -- rail_slider_body (R2.12) ----------------------------------------------------

#: Lateral / vertical sliding clearance bands for a printed shoe on a
#: printed rail (friction slide, not a bearing).
SLIDE_LAT_BAND = (0.2, 0.6)
SLIDE_VERT_BAND = (0.2, 0.5)
SLIDER_WALL_MIN = 2.4
SLIDER_ENGAGE_K = 1.2   # travel >= k * rail top width (no yaw wobble)


def _rail_slider_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The sliding SHOE for the clamp family's dovetail rail: a constant
    YZ section (block with a female dovetail slot opening downward)
    extruded along the travel axis X — sideprint, zero overhangs by
    construction. Parameterized by the RAIL's own numbers (top width,
    height, flank angle) so one shoe slides every rail in the family."""
    import math as _math

    if state.section is not None:
        raise RecipeError("rail_slider_body must be the (single) base op")
    from .profiles_revolve import loop_from_points
    from .section import Pt, SectionProfile

    top_w = p["rail_top_w"]
    rail_h = p["rail_h"]
    angle = p["rail_angle"]
    c_lat = p["slide_clearance"]
    c_vert = p["vert_clearance"]
    travel = p["travel"]
    wall = p["wall"]
    ceiling = p["ceiling_t"]
    if not 0.0 < angle <= 25.0:
        raise RecipeError(
            f"rail_angle {angle:g} outside (0, 25] — 0 is a plain ridge, "
            "no dovetail retention")
    lo, hi = SLIDE_LAT_BAND
    if not lo <= c_lat <= hi:
        raise RecipeError(
            f"slide_clearance {c_lat:g} outside [{lo:g}, {hi:g}]")
    vlo, vhi = SLIDE_VERT_BAND
    if not vlo <= c_vert <= vhi:
        raise RecipeError(
            f"vert_clearance {c_vert:g} outside [{vlo:g}, {vhi:g}]")
    root_w = top_w - 2.0 * rail_h * _math.tan(_math.radians(angle))
    if root_w < 4.0:
        raise RecipeError(
            f"rail root {root_w:.1f} < 4 — this rail cannot exist")
    if travel < SLIDER_ENGAGE_K * top_w:
        raise RecipeError(
            f"travel {travel:g} shorter than {SLIDER_ENGAGE_K:g}x rail "
            f"top ({SLIDER_ENGAGE_K * top_w:g}) — the shoe yaws")
    g_neck = root_w + c_lat          # the bottom opening rides the neck
    g_top = top_w + c_lat            # the inside width over the rail top
    depth = rail_h + c_vert
    body_w = g_top + 2.0 * wall
    body_h = depth + ceiling

    pts = [
        Pt(-body_w / 2.0, 0.0),
        Pt(-g_neck / 2.0, 0.0),
        Pt(-g_top / 2.0, depth),
        Pt(g_top / 2.0, depth),
        Pt(g_neck / 2.0, 0.0),
        Pt(body_w / 2.0, 0.0),
        Pt(body_w / 2.0, body_h),
        Pt(-body_w / 2.0, body_h),
    ]
    state.section = SectionProfile(
        name="recipe", outer=loop_from_points(pts),
        plane="YZ", width_axis="X",
    )
    state.width = travel
    state.print_orientation = "side_profile"

    name = op_id or "shoe"
    state.regions.extend([
        Region(f"{name}_payload_face", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -body_w / 2.0, depth, travel, body_w / 2.0, body_h)),
        Region(f"{name}_rail_slot", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -g_top / 2.0, 0.0, travel, g_top / 2.0, depth)),
    ])
    state.datums["rail_slot"] = {
        "at": [travel / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]}

    # optional payload mount stack on the shoe's TOP: two bosses with
    # pilot bores — the carriage CARRIES a payload (a snap box on the
    # slider), the missing physical link of the station story
    payload_mount = int(round(p.get("payload_mount", 0)))
    if payload_mount:
        if payload_mount != 2:
            raise RecipeError(
                f"payload_mount must be 0 or 2, got {payload_mount}")
        from .part import RibFeature
        p_sx = p.get("payload_sx", 30.0) / 2.0
        boss = p.get("payload_boss", 7.0)
        b_h = p.get("payload_boss_h", 6.0)
        pd, pdepth = p.get("payload_pilot_d", 4.0), p.get("payload_pilot_depth", 5.0)
        if p.get("payload_sx", 30.0) > travel - boss:
            raise RecipeError(
                f"payload_sx {p['payload_sx']:g} does not fit the "
                f"{travel:g} travel")
        top = body_h + b_h
        cx = travel / 2.0
        for i, bx in enumerate((cx - p_sx, cx + p_sx)):
            state.ribs.append(RibFeature(
                name=f"{name}_payload_boss_{i}",
                box=Box3(bx - boss / 2.0, -boss / 2.0, body_h - 0.6,
                         bx + boss / 2.0, boss / 2.0, top),
            ))
            state.bores.append(BoreFeature(
                name=f"payload_pilot_{i}", axis="Z", center=(bx, 0.0, 0.0),
                d=pd, span=(top - pdepth, top), overshoot=(0.0, 1.0),
            ))
        state.datums["payload_top"] = {
            "at": [cx, 0.0, top], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        # dovetail_rail FEMALE frame keys in the SOCKET convention the
        # dovetail_joint ir_check measures: groove_top_w is the OPENING a
        # male enters (the slot mouth = the neck), groove_bottom_w the
        # wide flank end inside, socket_top_v the opening plane the male
        # foot seats on (v=0, the slot mouth face). The shoe's slot is a
        # legitimate short socket — an adapter foot slides it like a rail
        # segment.
        groove_top_w=g_neck, groove_bottom_w=g_top, groove_depth=depth,
        socket_top_v=0.0,
        slider_travel=travel, slider_wall=wall, slider_ceiling=ceiling,
        slider_lat_clearance=c_lat, slider_vert_clearance=c_vert,
        slider_rail_top_w=top_w, slider_rail_h=rail_h,
    )


_register(RecipeOpDecl(
    name="rail_slider_body",
    kind="base",
    params={
        "rail_top_w": ("length", None),
        "rail_h": ("length", 5.0),
        "rail_angle": ("number", 10.0),
        "slide_clearance": ("length", 0.35),
        "vert_clearance": ("length", 0.3),
        "travel": ("length", 30.0),
        "wall": ("length", 3.0),
        "ceiling_t": ("length", 4.0),
        "payload_mount": ("count", 0),
        "payload_sx": ("length", 30.0),
        "payload_boss": ("length", 7.0),
        "payload_boss_h": ("length", 6.0),
        "payload_pilot_d": ("length", 4.0),
        "payload_pilot_depth": ("length", 5.0),
    },
    validators=(
        "form.rail_slider_fit_ok",
        "form.rail_slider_walls_ok",
        "form.constant_section",
        "topology.single_connected_solid",
    ),
    apply=_rail_slider_body,
    description="female dovetail shoe sliding the clamp family's rail — "
                "constant section, sideprint, rail-parameterized",
))
