"""Mounting recipe ops — wall ring mount, revolve band, angle bracket.
"""
from __future__ import annotations

import math
from typing import Any
from ..core.fasteners import FDM_CLEARANCE, screw_spec
from .profiles_plate import rounded_rect_loop
from .profiles_revolve import loop_from_points
from .regions import Box3, Region
from .section import Pt, SectionProfile
from ..product.archetype import RegionRole
from .part import BoreFeature, PlateFeature, RibFeature
from .recipe_ops_core import KEEPOUT_CLEARANCE, RecipeError, RecipeState, RecipeOpDecl, _register


# -- wall_ring_mount ------------------------------------------------------------


def _wall_ring_mount(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Wall tool ring mount base: a wall flange fused with a C-ring saddle
    around a vertical tool axis, buttressed by gusset ribs. Model frame:
    Z = wall normal (wall at z=0), X = vertical along the wall = tool axis
    = extrusion axis, Y = horizontal. The base section (top view: flange
    strip + fused ring) extrudes x in [0, collar_h]; the taller flange
    continues above as a PlateFeature — anchors land there via a separate
    hole op. Prints upright ("side_profile"): everything rises from the
    section on the bed."""
    from .profiles_wallmount import WallRingParams, build_wall_ring_section
    from .style import MOLDED_UTILITY_PART

    if state.section is not None:
        raise RecipeError("wall_ring_mount must be the (single) base op")
    collar_h, flange_h = p["collar_h"], p["flange_h"]
    if collar_h + 24.0 > flange_h:
        raise RecipeError(
            f"flange_h {flange_h:g} leaves no anchor panel above the "
            f"collar (needs >= collar_h + 24)"
        )
    wp = WallRingParams(
        tool_d=p["tool_d"], clearance=p["clearance"], ring_wall=p["ring_wall"],
        capture_deg=p["capture_deg"], standoff=p["standoff"],
        flange_w=p["flange_w"], flange_t=p["flange_t"],
        flange_corner_r=p["flange_corner_r"],
    )
    try:
        profile, f = build_wall_ring_section(wp, MOLDED_UTILITY_PART)
    except ValueError as exc:
        raise RecipeError(f"wall_ring_mount: {exc}") from exc
    state.section = profile
    state.width = collar_h
    state.print_orientation = "side_profile"

    fw, t = p["flange_w"], p["flange_t"]
    s, r_i, r_o = f["saddle_cz"], f["saddle_r"], f["r_outer"]
    name = op_id or "body"
    state.plates.append(
        PlateFeature(
            name=f"{name}_flange",
            x0=0.0, y0=-fw / 2.0, x1=flange_h, y1=fw / 2.0,
            z_bottom=0.0, thickness=t, corner_r=p["flange_corner_r"],
        )
    )

    # Gusset ribs: two side buttresses welding the flange front to the ring
    # flank, provably clear of the saddle cavity (|y| > saddle_r). A center
    # rib under the ring belly is geometrically impossible in this family —
    # it needs the ring floated off the flange, which contradicts the
    # direct-fusion guard — so the count is fixed, not a parameter.
    rib_t = p["rib_t"]
    rib_y0 = r_i + 1.5
    if rib_y0 + rib_t > fw / 2.0 - 1.0:
        raise RecipeError(
            f"gusset ribs at |y| {rib_y0 + rib_t:.1f} stick past the flange "
            f"(flange_w/2 - 1 = {fw / 2.0 - 1.0:.1f})"
        )
    for i, side in enumerate((-1.0, 1.0)):
        lo, hi = side * (rib_y0 + rib_t), side * rib_y0
        state.ribs.append(
            RibFeature(
                name=f"{name}_rib_{i}",
                box=Box3(0.0, min(lo, hi), t - 0.6, collar_h, max(lo, hi), s),
            )
        )
    # Semantic regions — names match the archetype YAML region ids.
    state.regions.extend([
        Region("wall_flange", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -fw / 2.0, 0.0, flange_h, fw / 2.0, t)),
        Region("saddle_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -r_i, s - r_i, collar_h, r_i, s + r_i)),
        Region("retaining_lip", RegionRole.RETAINING_FLEXURE,
               Box3(0.0, -(r_o + 1.0), s, collar_h, r_o + 1.0, s + r_o + 1.0)),
        Region("load_rib_zone", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, -(r_o + 1.0), t - 1.0, collar_h, r_o + 1.0, s)),
        Region("flange_lightening", RegionRole.AESTHETIC_LIGHTENING,
               Box3(collar_h + 6.0, -(fw / 2.0 - 4.0), 0.0,
                    flange_h - 4.0, fw / 2.0 - 4.0, t)),
        # Reserved for v2 cylindrical/biomorphic mapping (ring axis is X;
        # field mapping is Z-axis-only today) — non-editable in the YAML.
        Region("outer_shell", RegionRole.AESTHETIC_LIGHTENING,
               Box3(0.0, -r_o, t, collar_h, r_o, s + r_o)),
    ])

    load_n = p["tool_mass_kg"] * 9.81
    state.frame.update(f)
    state.frame.update(
        collar_h=collar_h,
        flange_h=flange_h,
        # the plate outline the hole-web checks measure against:
        outline_u0=0.0, outline_v0=-fw / 2.0,
        outline_u1=flange_h, outline_v1=fw / 2.0,
        outline_corner_r=p["flange_corner_r"], plate_t=t,
        load_n_est=load_n,
        moment_nmm_est=load_n * p["safety_factor"] * p["standoff"],
    )
    state.datums["tool_axis"] = {
        "at": [collar_h / 2.0, 0.0, s], "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["mount_face"] = {
        "at": [flange_h / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="wall_ring_mount",
    kind="base",
    params={
        "tool_d": ("length", None), "clearance": ("length", 1.0),
        "ring_wall": ("length", 7.0), "collar_h": ("length", 30.0),
        "capture_deg": ("number", 220.0), "standoff": ("length", None),
        "flange_w": ("length", None), "flange_h": ("length", None),
        "flange_t": ("length", None), "flange_corner_r": ("length", 6.0),
        "rib_t": ("length", 3.0),
        "tool_mass_kg": ("number", 2.5), "safety_factor": ("number", 2.5),
    },
    validators=(
        "form.tool_saddle_radius_ok",
        "form.tool_clearance_ok",
        "form.retention_angle_ok",
        "form.mouth_gap_ok",
        "form.ribs_connect_saddle_to_flange",
        "form.anchor_wall_strength_unverified",
        "topology.tool_void_open",
        "topology.single_connected_solid",
        "topology.ribs_present",
    ),
    apply=_wall_ring_mount,
    description="wall flange + fused C-ring tool saddle + gusset ribs "
                "(tool axis = X, prints upright)",
))


# -- revolve_band + cylindrical_z_mapping_v1 ------------------------------------

#: MVP guard: a cell wider than this fraction of the wall-midline radius
#: distorts too much when flattened onto its tangent plane.
CYL_MAX_CELL_FRACTION = 0.6


def _revolve_band(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A revolved band — ring, bushing, washer, bracelet, sleeve. The
    half-section (XZ plane, +u side of the axis) is a rounded rectangle;
    the compiler revolves it 360 degrees. size_clearance is added to the
    bore because a band is a CONTACT part (a finger, a shaft): declared
    inner_d is the nominal fit, the frame records the effective bore.

    The outer wall is a field canvas: a cylindrical_z_mapping_v1 window
    (axis Z only, one seam, full 360 band) with the seam and both edges as
    explicit keepout regions — the pattern math stays honest and visible."""
    from .part import FaceWindow
    from .regions import Rect2D as _Rect2D

    if state.section is not None:
        raise RecipeError("revolve_band must be the (single) base op")
    inner_d, height, wall = p["inner_d"], p["height"], p["wall"]
    clearance = p["size_clearance"]
    if wall < 1.5:
        raise RecipeError(
            f"wall {wall:g} < 1.5 — too thin for a through-cut band"
        )
    inner_d_eff = inner_d + clearance
    inner_r = inner_d_eff / 2.0
    outer_r = inner_r + wall
    corner_r = min(p["corner_r"], wall * 0.45, height * 0.3)
    state.section = SectionProfile(
        name="recipe_revolve",
        outer=rounded_rect_loop(inner_r, 0.0, outer_r, height, corner_r),
        plane="XZ",
        width_axis="Y",
    )
    state.kind = "profile_revolve"
    state.width = 2.0 * outer_r  # reporting; the compiler revolves
    r_mid = (inner_r + outer_r) / 2.0
    seam = p["seam_keepout"]
    margin = p["edge_margin"]
    circumference = 2.0 * math.pi * r_mid
    if circumference - 2.0 * seam < 10.0 or height - 2.0 * margin < 2.0:
        raise RecipeError("band too small for a patterned window")
    name = op_id or "band"
    state.regions.extend([
        Region("band_outer_surface", RegionRole.AESTHETIC_LIGHTENING,
               Box3(-outer_r, -outer_r, 0.0, outer_r, outer_r, height)),
        Region("bore_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(-inner_r, -inner_r, 0.0, inner_r, inner_r, height)),
        # Edge and seam keepouts are REAL regions — the honesty/region
        # lenses show them, and the field math is checked against them.
        Region("top_edge_keepout", RegionRole.HIGH_STRESS_REGION,
               Box3(-outer_r, -outer_r, height - margin, outer_r, outer_r, height)),
        Region("bottom_edge_keepout", RegionRole.HIGH_STRESS_REGION,
               Box3(-outer_r, -outer_r, 0.0, outer_r, outer_r, margin)),
        Region("seam_keepout", RegionRole.HIGH_STRESS_REGION,
               Box3(r_mid - wall, -seam, 0.0, outer_r + 1.0, seam, height)),
    ])
    # The cylindrical window in LOCAL (arc, height) coords; the seam sits
    # at theta=0, so the window starts past it and ends before it wraps.
    state.datums["axis"] = {"at": [0.0, 0.0, height / 2.0], "rotate": [0.0, 0.0, 0.0]}
    window = _Rect2D(seam, margin, circumference - seam, height - margin)
    state.frame.update(
        inner_d=inner_d, inner_d_effective=inner_d_eff,
        inner_r=inner_r, outer_r=outer_r, wall=wall,
        band_h=height, band_z0=0.0, band_z1=height,
        cyl_r_mid=r_mid,
        # the revolve probes read these names (cup convention):
        exit_r=inner_r, height=height, axis_clear_r=inner_r,
    )
    state.windows["band_outer_surface"] = FaceWindow(
        origin=(0.0, 0.0, 0.0), tilt_deg=0.0,
        window=window, depth=wall,
        keepouts=(),
        mapping="cylindrical", cyl_center=(0.0, 0.0),
        cyl_r=r_mid, cyl_r_outer=outer_r, cyl_z0=0.0,
        note="cylindrical_z_mapping_v1: axis Z, one seam at theta=0",
    )


_register(RecipeOpDecl(
    name="revolve_band",
    kind="base",
    params={
        "inner_d": ("length", None), "height": ("length", None),
        "wall": ("length", 2.2), "corner_r": ("length", 0.8),
        "size_clearance": ("length", 0.25),
        "seam_keepout": ("length", 2.0), "edge_margin": ("length", 0.9),
    },
    validators=(
        "form.revolve_profile_clear_of_axis",
        "topology.revolve_cavity_open",
        "topology.single_connected_solid",
    ),
    apply=_revolve_band,
    description="revolved band (ring/bushing/washer/bracelet) with a "
                "cylindrical field canvas on the outer wall",
))


# -- angle_bracket_body ----------------------------------------------------------


def _angle_bracket_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Universal L-bracket: two perpendicular legs sharing a corner,
    optionally webbed by a full-width diagonal gusset, with clearance
    holes cut in BOTH legs by the op itself (the base owns its holes —
    hole_pattern cuts along Z only and cannot reach the standing leg).

    Model frame: the L-section lives in XZ (leg A along +X on the bed,
    leg B rising +Z), extruded along Y by ``width`` — the natural
    side-profile print, support-free by construction. Leg A holes are
    Z-bores, leg B holes are X-bores; pan-head screws seat proud (no
    countersink in v1)."""
    if state.section is not None:
        raise RecipeError("angle_bracket_body must be the (single) base op")
    leg_a, leg_b, w, t = p["leg_a"], p["leg_b"], p["width"], p["t"]
    g = p["gusset"]
    n = int(round(p["holes_per_leg"]))
    inset = p["hole_inset"]
    spec = screw_spec(p["screw"])
    bore_d = spec["clear"] + FDM_CLEARANCE
    head_r = spec["head"] / 2.0

    if min(leg_a, leg_b) < t + 10.0:
        raise RecipeError(
            f"legs must clear the corner: min leg {min(leg_a, leg_b):g} "
            f"< t + 10 = {t + 10.0:g}")
    if g < 0.0 or (g > 0.0 and g + t + 2.0 > min(leg_a, leg_b)):
        raise RecipeError(
            f"gusset reach {g:g} runs past a leg (max "
            f"{min(leg_a, leg_b) - t - 2.0:g})")
    if w / 2.0 - bore_d / 2.0 < 3.0:
        raise RecipeError(
            f"width {w:g} leaves under 3 mm web beside a {bore_d:g} bore")
    if n < 1:
        raise RecipeError("angle_bracket_body needs holes_per_leg >= 1")

    # -- the L-section (XZ, CCW), gusset as a diagonal web in the corner --
    pts = [Pt(0.0, 0.0), Pt(leg_a, 0.0), Pt(leg_a, t)]
    if g > 0.0:
        pts += [Pt(t + g, t), Pt(t, t + g)]
    else:
        pts.append(Pt(t, t))
    pts += [Pt(t, leg_b), Pt(0.0, leg_b)]
    state.section = SectionProfile(
        name="recipe",
        outer=loop_from_points(pts),
        plane="XZ",
        width_axis="Y",
    )
    state.width = w
    state.print_orientation = "side_profile"

    # -- holes: evenly spread between the corner zone and the leg end -----
    name = op_id or "bracket"

    def _centers(leg_len: float) -> list[float]:
        lo = t + g + head_r + 3.0
        hi = leg_len - inset
        if hi < lo:
            raise RecipeError(
                f"leg {leg_len:g} too short for holes past the corner zone "
                f"(needs > {lo + inset:g})")
        if n == 1:
            return [(lo + hi) / 2.0]
        if (hi - lo) / (n - 1) < bore_d + 3.0:
            raise RecipeError(
                f"{n} holes on a {leg_len:g} leg leave webs under 3 mm")
        step = (hi - lo) / (n - 1)
        return [lo + i * step for i in range(n)]

    for i, x in enumerate(_centers(leg_a)):
        state.bores.append(BoreFeature(
            name=f"{name}_a_{i}", axis="Z", d=bore_d,
            center=(x, 0.0, 0.0), span=(0.0, t), overshoot=(1.0, 1.0)))
        state.regions.append(Region(
            f"{name}_a_{i}_keep", RegionRole.FASTENER_KEEPOUT,
            Box3(x - head_r - KEEPOUT_CLEARANCE, -head_r - KEEPOUT_CLEARANCE, 0.0,
                 x + head_r + KEEPOUT_CLEARANCE, head_r + KEEPOUT_CLEARANCE, t)))
        state.frame[f"{name}_a_{i}_x"] = x
    for i, z in enumerate(_centers(leg_b)):
        state.bores.append(BoreFeature(
            name=f"{name}_b_{i}", axis="X", d=bore_d,
            center=(0.0, 0.0, z), span=(0.0, t), overshoot=(1.0, 1.0)))
        state.regions.append(Region(
            f"{name}_b_{i}_keep", RegionRole.FASTENER_KEEPOUT,
            Box3(0.0, -head_r - KEEPOUT_CLEARANCE, z - head_r - KEEPOUT_CLEARANCE,
                 t, head_r + KEEPOUT_CLEARANCE, z + head_r + KEEPOUT_CLEARANCE)))
        state.frame[f"{name}_b_{i}_z"] = z

    # -- semantic regions ---------------------------------------------------
    state.regions.extend([
        Region("leg_a_face", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -w / 2.0, 0.0, leg_a, w / 2.0, t)),
        Region("leg_b_face", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -w / 2.0, 0.0, t, w / 2.0, leg_b)),
        Region("corner", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, -w / 2.0, 0.0, t + g, w / 2.0, t + g)),
    ])
    # Leg A carries the outline the Z-bore web checks measure against; the
    # X-bores on leg B are guarded by the op's own spacing math above.
    state.frame.update(
        leg_a_len=leg_a, leg_b_len=leg_b, angle_t=t,
        bracket_w=w, gusset_reach=g,
        holes_per_leg=float(n), bracket_bore_d=bore_d,
        outline_u0=0.0, outline_v0=-w / 2.0,
        outline_u1=leg_a, outline_v1=w / 2.0,
        plate_t=t,
    )
    state.datums["corner_line"] = {
        "at": [t, 0.0, t], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="angle_bracket_body",
    kind="base",
    params={
        "leg_a": ("length", None), "leg_b": ("length", None),
        "width": ("length", 30.0), "t": ("length", 4.0),
        "gusset": ("length", 12.0), "screw": ("choice", "M4"),
        "holes_per_leg": ("count", 2), "hole_inset": ("length", 8.0),
    },
    validators=(
        "form.holes_within_outline",
        "form.min_web_between_holes",
        "topology.bores_open",
        "topology.single_connected_solid",
    ),
    apply=_angle_bracket_body,
    description="L-bracket: two perpendicular legs + optional diagonal "
                "gusset web, clearance holes in both legs (side-profile print)",
))

# -- square_post_sleeve ----------------------------------------------------------

#: Sliding square-post fit band (diametral-ish, per side pair) — wider
#: than the torsion-driving SQ_FIT_BAND of the knob's end socket: the
#: sleeve slides ON and a set screw takes the slack.
POST_FIT_BAND = (0.3, 0.9)
SLEEVE_ENGAGE_K = 1.5     # sleeve height >= k * post width (anti-rock)
SLEEVE_WALL_MIN = 2.4
SLEEVE_WELD_BITE = 1.2


def _square_post_sleeve(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A collar sleeve welded to a vessel's OUTER wall with a vertical
    square through-channel — hangs a cup/pot on a 2x2 cm balcony post.
    The collar is a PolyLoft whose FRONT FACE IS THE WALL ARC at each
    height (constant weld bite regardless of taper — a flat face either
    gaps at the bottom or pierces the cavity at the top of a cone). The
    channel opens TOWARD the vessel, so the post presses directly
    against the wall and the teardrop set screw locks it there — the
    stiffest of the clamp schemes."""
    import math as _math

    state.require_base("square_post_sleeve")
    f = state.frame
    if "pot_r_top" not in f or "pot_h" not in f:
        raise RecipeError("square_post_sleeve needs a pot_body base")
    post_w = p["post_w"]
    clearance = p["fit_clearance"]
    sleeve_h = p["sleeve_h"]
    z_lo = p["z"]
    wall = p["wall"]
    direction = p["dir"]
    set_screw = p["set_screw"]
    lo, hi = POST_FIT_BAND
    if not lo <= clearance <= hi:
        raise RecipeError(
            f"fit_clearance {clearance:g} outside [{lo:g}, {hi:g}] — "
            "tighter binds on FDM swell, looser rocks on the post")
    if sleeve_h < SLEEVE_ENGAGE_K * post_w:
        raise RecipeError(
            f"sleeve {sleeve_h:g} shorter than {SLEEVE_ENGAGE_K:g}x post "
            f"({SLEEVE_ENGAGE_K * post_w:g}) — the cup rocks on the post")
    if direction not in ("+x", "-x", "+y", "-y"):
        raise RecipeError(f"dir {direction!r} not in (+x, -x, +y, -y)")
    if set_screw != "none":
        screw_spec(set_screw)  # unknown size fails loudly here
    if wall < SLEEVE_WALL_MIN:
        raise RecipeError(f"sleeve wall {wall:g} < {SLEEVE_WALL_MIN:g}")
    z_hi = z_lo + sleeve_h
    r_top, r_bot, pot_h = f["pot_r_top"], f["pot_r_bottom"], f["pot_h"]
    if z_lo < 0.0 or z_hi > pot_h + 1e-9:
        raise RecipeError(
            f"sleeve z {z_lo:g}..{z_hi:g} runs past the pot (0..{pot_h:g})")

    def r_out(z: float) -> float:
        return r_bot + (r_top - r_bot) * z / pot_h

    s_eff = post_w + clearance
    w_box = s_eff + 2.0 * wall
    if w_box / 2.0 >= r_out(z_lo) - 2.0:
        raise RecipeError(
            f"post {post_w:g} too wide for this vessel — the collar "
            "out-spans the wall chord")
    # the post rides the wall; its far face + clearance sets the channel
    x_post_front = r_out(z_hi)
    x_back = x_post_front + post_w + clearance
    u1 = x_back + wall

    def _map(u: float, v: float) -> tuple[float, float]:
        if direction == "+x":
            return (u, v)
        if direction == "-x":
            return (-u, v)
        if direction == "+y":
            return (v, u)
        return (v, -u)

    # -- the collar: front face = the wall arc minus the weld bite --------
    def _section(z: float) -> tuple[tuple[float, float], ...]:
        r = r_out(z)
        pts: list[tuple[float, float]] = [
            _map(u1, -w_box / 2.0), _map(u1, w_box / 2.0)]
        arc_n = 16
        for k in range(arc_n + 1):
            v = w_box / 2.0 - w_box * k / arc_n
            u = _math.sqrt(max(r * r - v * v, 0.0)) - SLEEVE_WELD_BITE
            pts.append(_map(u, v))
        return tuple(pts)

    from .part import CutBoxFeature, PolyLoftFeature

    name = op_id or "sleeve"
    state.poly_lofts.append(PolyLoftFeature(
        name=f"{name}_collar", z0=z_lo, z1=z_hi,
        bottom=_section(z_lo), top=_section(z_hi)))

    # -- the channel: opens toward the vessel (the post presses the wall) -
    x_cut0 = _math.sqrt(max(r_out(z_lo) ** 2 - (s_eff / 2.0) ** 2, 0.0)) - 2.0

    def _box(ua: float, ub: float, va: float, vb: float,
             za: float, zb: float) -> Box3:
        xa, ya = _map(ua, va)
        xb, yb = _map(ub, vb)
        return Box3(min(xa, xb), min(ya, yb), za,
                    max(xa, xb), max(ya, yb), zb)

    state.cutboxes.append(CutBoxFeature(
        name=f"{name}_post_channel",
        box=_box(x_cut0, x_back, -s_eff / 2.0, s_eff / 2.0,
                 z_lo - 1.0, z_hi + 1.0)))
    if set_screw != "none":
        spec = screw_spec(set_screw)
        axis = "X" if direction in ("+x", "-x") else "Y"
        z_mid = z_lo + sleeve_h / 2.0
        sign = 1.0 if direction.startswith("+") else -1.0
        span = tuple(sorted((sign * (x_back - 1.0), sign * (u1 + 1.0))))
        state.bores.append(BoreFeature(
            name=f"{name}_set_screw", axis=axis, d=spec["tap"],
            center=(0.0, 0.0, z_mid), span=span,
            overshoot=(1.0, 1.0), roof="teardrop"))
    cx, cy = _map((x_post_front + x_back) / 2.0, 0.0)
    state.regions.append(Region(
        f"{name}_post_channel", RegionRole.MOUNTING_SURFACE,
        _box(x_cut0, x_back, -s_eff / 2.0, s_eff / 2.0, z_lo, z_hi)))
    state.datums["post_axis"] = {
        "at": [cx, cy, z_hi], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        sleeve_post_w=post_w,
        sleeve_channel_w_eff=s_eff,
        sleeve_fit_clearance=clearance,
        sleeve_h_eff=sleeve_h,
        sleeve_wall=wall,
        sleeve_inner_web_eff=wall,  # the side pillars ARE the vessel web
        sleeve_dir=float(("+x", "-x", "+y", "-y").index(direction)),
    )


_register(RecipeOpDecl(
    name="square_post_sleeve",
    kind="feature",
    params={
        "post_w": ("length", None),
        "fit_clearance": ("length", 0.5),
        "sleeve_h": ("length", 40.0),
        "z": ("length", 0.0),
        "wall": ("length", 3.0),
        "dir": ("choice", "+x"),
        "set_screw": ("choice", "m4"),
    },
    validators=(
        "form.post_sleeve_fit_ok",
        "form.post_sleeve_engagement_ok",
        "form.post_sleeve_walls_ok",
        "topology.cutout_present",
        "topology.bores_open",
        "topology.single_connected_solid",
    ),
    apply=_square_post_sleeve,
    description="square-post collar welded to a vessel wall: vertical "
                "through-channel + teardrop set-screw bore (the cup "
                "holder on a 2x2 balcony post)",
))
