"""Repair-domain recipe ops — revolved spare bodies built from polyline
half-sections on the core IR (``profile_revolve``): a barbed two-step
hose adapter and a square-socket replacement knob. No new kernel
geometry — the compiler revolves the section exactly like the core
revolve_band / ring ops.

Spare Fit Standard frame keys published here are the measurement
contract of the checks in :mod:`artifact_forge_showcase.checks.spare`.
"""
from __future__ import annotations

from typing import Any

from artifact_forge_ng.form.part import CutBoxFeature
from artifact_forge_ng.form.recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from artifact_forge_ng.form.regions import Box3, Region
from artifact_forge_ng.form.section import LineSeg, ProfileLoop, Pt, SectionProfile
from artifact_forge_ng.product.archetype import RegionRole

#: Diametral hose-fit band: the crest must exceed the hose bore by this
#: much for real retention without splitting the hose.
BARB_H_BAND = (0.4, 1.5)          # per-side barb height over the root, mm
MIN_BORE_R = 2.0                  # a drain adapter is useless as a capillary
SQ_FIT_BAND = (0.1, 0.4)          # across-flats clearance band, mm
SOCKET_DEPTH_K = 1.0              # socket depth >= k * shaft size


def _sawtooth(points: list[Pt], r_root: float, r_crest: float,
              v0: float, v1: float, count: int, toward_tip_at_v0: bool) -> None:
    """Append barb sawtooth points between v0 and v1 (v0 < v1). The sharp
    (vertical) face looks toward the flange so the hose slides on from the
    tip and bites against pull-off."""
    pitch = (v1 - v0) / count
    ramp = 0.75 * pitch
    if toward_tip_at_v0:
        # tip at v0: each tooth ramps gently away from the tip, then drops
        # vertically (the sharp face looks toward the flange at v1)
        for k in range(count):
            a = v0 + k * pitch
            points.append(Pt(r_root, a))
            points.append(Pt(r_crest, a + ramp))
            points.append(Pt(r_root, a + ramp))
        points.append(Pt(r_root, v1))
    else:
        # tip at v1: mirrored — flat toward the flange, vertical sharp face
        # (looking toward v0), then a gentle ramp descending to the tip side
        points.append(Pt(r_root, v0))
        for k in range(count):
            a = v0 + k * pitch
            points.append(Pt(r_root, a + pitch - ramp))
            points.append(Pt(r_crest, a + pitch - ramp))
            points.append(Pt(r_root, a + pitch))


def _loop_from_points(points: list[Pt]) -> ProfileLoop:
    """Closed polyline loop. Every joint of a revolved spare is a
    machined-style corner by design (barb teeth, flange steps, chamfers) —
    tagged intentional so form.profile_smooth judges the styled parts, not
    this deliberately technical silhouette."""
    segs = []
    for a, b in zip(points, points[1:] + points[:1]):
        if a.dist(b) > 1e-6:
            segs.append(LineSeg(a, b, tags=frozenset({"intentional_corner"})))
    return ProfileLoop(segs)


def _hose_adapter_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Two barbed spigots joined by a stop flange, one through bore. The
    half-section (XZ, +u side, axis = Z) is a single polyline: bore edge,
    spigot A sawtooth, flange, spigot B sawtooth."""
    if state.section is not None:
        raise RecipeError("hose_adapter_body must be the (single) base op")
    d_a, d_b = p["spigot_d_a"], p["spigot_d_b"]
    len_a, len_b = p["spigot_len_a"], p["spigot_len_b"]
    wall, barb_h = p["wall"], p["barb_h"]
    n_a, n_b = int(p["barb_count_a"]), int(p["barb_count_b"])
    flange_t = p["flange_t"]

    r_crest_a, r_crest_b = d_a / 2.0, d_b / 2.0
    r_root_a, r_root_b = r_crest_a - barb_h, r_crest_b - barb_h
    r_bore = min(r_root_a, r_root_b) - wall
    if r_bore < MIN_BORE_R:
        raise RecipeError(
            f"bore radius {r_bore:.2f} < {MIN_BORE_R:g} — spigots too small "
            "for the declared wall")
    if min(n_a, n_b) < 2:
        raise RecipeError("each spigot needs at least 2 barbs")
    r_flange = max(r_crest_a, r_crest_b) + p["flange_lip"]
    z_fl0 = len_a
    z_fl1 = len_a + flange_t
    z_top = z_fl1 + len_b

    pts: list[Pt] = [Pt(r_bore, 0.0)]
    _sawtooth(pts, r_root_a, r_crest_a, 0.0, z_fl0, n_a, toward_tip_at_v0=True)
    pts.append(Pt(r_flange, z_fl0))
    pts.append(Pt(r_flange, z_fl1))
    _sawtooth(pts, r_root_b, r_crest_b, z_fl1, z_top, n_b, toward_tip_at_v0=False)
    pts.append(Pt(r_bore, z_top))

    state.section = SectionProfile(
        name="recipe_revolve",
        outer=_loop_from_points(pts),
        plane="XZ",
        width_axis="Y",
    )
    state.kind = "profile_revolve"
    state.width = 2.0 * r_flange

    name = op_id or "adapter"
    state.regions.append(Region(
        f"{name}_flange", RegionRole.MOUNTING_SURFACE,
        Box3(-r_flange, -r_flange, z_fl0, r_flange, r_flange, z_fl1)))
    state.frame.update(
        axis_clear_r=r_bore,
        bore_d=2.0 * r_bore,
        spigot_d_a=d_a, spigot_d_b=d_b,
        barb_h_a=barb_h, barb_h_b=barb_h,
        barb_count_a=float(n_a), barb_count_b=float(n_b),
        spigot_len_a=len_a, spigot_len_b=len_b,
        flange_z0=z_fl0, flange_z1=z_fl1,
        adapter_total_l=z_top,
    )


_register(RecipeOpDecl(
    name="hose_adapter_body",
    kind="base",
    params={
        "spigot_d_a": ("length", None), "spigot_d_b": ("length", None),
        "spigot_len_a": ("length", 30.0), "spigot_len_b": ("length", 30.0),
        "wall": ("length", 2.4), "barb_h": ("length", 0.8),
        "barb_count_a": ("count", 3), "barb_count_b": ("count", 3),
        "flange_t": ("length", 4.0), "flange_lip": ("length", 2.5),
    },
    validators=(
        "form.barb_retention_ok",
        "form.revolve_profile_clear_of_axis",
        "topology.single_connected_solid",
    ),
    apply=_hose_adapter_body,
    description="two barbed hose spigots joined by a stop flange, one "
                "through bore (spigot Ø = barb crest = nominal hose bore)",
))


def _knob_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Replacement knob: a revolved grip (cylinder + top chamfer) with a
    blind SQUARE shaft socket cut from the underside. Square shafts cover
    valve stems and appliance timers; a D-shaft variant needs a partial-cut
    primitive and is deliberately out of this wave."""
    if state.section is not None:
        raise RecipeError("knob_body must be the (single) base op")
    grip_d, grip_h = p["grip_d"], p["grip_h"]
    shaft_sq, depth = p["shaft_sq"], p["socket_depth"]
    clearance = p["fit_clearance"]
    chamfer = min(p["top_chamfer"], grip_h * 0.3, grip_d * 0.25)

    r_grip = grip_d / 2.0
    s_eff = shaft_sq + clearance
    corner_reach = s_eff * (2.0 ** 0.5) / 2.0
    if depth >= grip_h - 2.0:
        raise RecipeError("socket depth leaves no top skin on the knob")
    if corner_reach >= r_grip - 1.5:
        raise RecipeError("shaft socket corners break out of the grip wall")

    pts = [
        Pt(0.0, 0.0),
        Pt(r_grip, 0.0),
        Pt(r_grip, grip_h - chamfer),
        Pt(r_grip - chamfer, grip_h),
        Pt(0.0, grip_h),
    ]
    state.section = SectionProfile(
        name="recipe_revolve",
        outer=_loop_from_points(pts),
        plane="XZ",
        width_axis="Y",
    )
    state.kind = "profile_revolve"
    state.width = grip_d

    name = op_id or "knob"
    half = s_eff / 2.0
    state.cutboxes.append(CutBoxFeature(
        name=f"{name}_shaft_socket",
        box=Box3(-half, -half, -1.0, half, half, depth),
    ))
    state.regions.append(Region(
        f"{name}_grip", RegionRole.MOUNTING_SURFACE,
        Box3(-r_grip, -r_grip, 0.0, r_grip, r_grip, grip_h)))
    state.frame.update(
        shaft_sq=shaft_sq,
        socket_w_eff=s_eff,
        socket_depth=depth,
        fit_clearance=clearance,
        grip_d=grip_d,
        grip_top_z=grip_h,
        torque_wall=r_grip - corner_reach,
    )


_register(RecipeOpDecl(
    name="knob_body",
    kind="base",
    params={
        "grip_d": ("length", None), "grip_h": ("length", 18.0),
        "shaft_sq": ("length", None), "socket_depth": ("length", 10.0),
        "fit_clearance": ("length", 0.25), "top_chamfer": ("length", 2.0),
    },
    validators=(
        "form.shaft_fit_ok",
        "form.knob_torque_wall_ok",
        "topology.single_connected_solid",
    ),
    apply=_knob_body,
    description="revolved replacement knob with a blind square shaft "
                "socket (measured fit + torque wall)",
))
