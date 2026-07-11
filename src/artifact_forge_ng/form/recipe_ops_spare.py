"""Spare-part recipe ops — revolved bodies built from polyline half-sections
on the core IR (``profile_revolve``): a barbed two-step hose adapter and a
square-socket knob. Promoted from the showcase pack once the tube/knob
family joined the core catalog.

Spare Fit Standard frame keys published here are the measurement contract
of the checks in :mod:`artifact_forge_ng.form.checks_spare`.
"""
from __future__ import annotations

import math
from typing import Any

from .part import BoreFeature, CutBoxFeature
from .profiles_revolve import loop_from_points, sawtooth
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from .section import Pt, SectionProfile
from ..product.archetype import RegionRole

#: Diametral hose-fit band: the crest must exceed the hose bore by this
#: much for real retention without splitting the hose.
BARB_H_BAND = (0.4, 1.5)          # per-side barb height over the root, mm
MIN_BORE_R = 2.0                  # a drain adapter is useless as a capillary
SQ_FIT_BAND = (0.1, 0.4)          # across-flats clearance band, mm
SOCKET_DEPTH_K = 1.0              # socket depth >= k * shaft size


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
    sawtooth(pts, r_root_a, r_crest_a, 0.0, z_fl0, n_a, toward_tip_at_v0=True)
    pts.append(Pt(r_flange, z_fl0))
    pts.append(Pt(r_flange, z_fl1))
    sawtooth(pts, r_root_b, r_crest_b, z_fl1, z_top, n_b, toward_tip_at_v0=False)
    pts.append(Pt(r_bore, z_top))

    state.section = SectionProfile(
        name="recipe_revolve",
        outer=loop_from_points(pts),
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
    """Knob body: a revolved grip (cylinder + top chamfer) with a blind
    SQUARE shaft socket cut from the underside. Square shafts cover valve
    stems, appliance timers, square nuts and carriage-bolt necks; a D-shaft
    variant needs a partial-cut primitive and is deliberately out of this
    wave. ``lobes`` > 0 scallops the grip with vertical finger coves cut
    around the perimeter (a star/wing grip) — the torque wall is measured
    at the scallop root, never at the untouched circle."""
    if state.section is not None:
        raise RecipeError("knob_body must be the (single) base op")
    grip_d, grip_h = p["grip_d"], p["grip_h"]
    shaft_sq, depth = p["shaft_sq"], p["socket_depth"]
    clearance = p["fit_clearance"]
    chamfer = min(p["top_chamfer"], grip_h * 0.3, grip_d * 0.25)
    lobes = int(round(p["lobes"]))
    bite = p["lobe_bite"]

    r_grip = grip_d / 2.0
    s_eff = shaft_sq + clearance
    corner_reach = s_eff * (2.0 ** 0.5) / 2.0
    if depth >= grip_h - 2.0:
        raise RecipeError("socket depth leaves no top skin on the knob")
    if corner_reach >= r_grip - 1.5:
        raise RecipeError("shaft socket corners break out of the grip wall")

    torque_wall = r_grip - corner_reach
    name = op_id or "knob"
    if lobes:
        if lobes < 3:
            raise RecipeError("a lobed knob needs at least 3 lobes")
        torque_wall = r_grip - bite - corner_reach
        if torque_wall < 1.5:
            raise RecipeError(
                f"lobe bite {bite:g} thins the torque wall to "
                f"{torque_wall:.2f} — socket corners break into the coves")
        # Finger coves: vertical cylinders tangent-bitten into the grip.
        # Cove radius scales with the pitch arc so deep-cut small knobs
        # keep real lobes between coves.
        scallop_r = max(2.0 * bite, math.pi * r_grip / lobes * 0.35)
        c_dist = r_grip + scallop_r - bite
        for k in range(lobes):
            ang = math.tau * k / lobes
            state.bores.append(BoreFeature(
                name=f"{name}_cove_{k}", axis="Z",
                d=2.0 * scallop_r,
                center=(c_dist * math.cos(ang), c_dist * math.sin(ang), 0.0),
                span=(0.0, grip_h), overshoot=(1.0, 1.0),
            ))

    pts = [
        Pt(0.0, 0.0),
        Pt(r_grip, 0.0),
        Pt(r_grip, grip_h - chamfer),
        Pt(r_grip - chamfer, grip_h),
        Pt(0.0, grip_h),
    ]
    state.section = SectionProfile(
        name="recipe_revolve",
        outer=loop_from_points(pts),
        plane="XZ",
        width_axis="Y",
    )
    state.kind = "profile_revolve"
    state.width = grip_d

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
        torque_wall=torque_wall,
        knob_lobes=float(lobes),
        # circle outline: the hole checks measure webs on the knob's
        # effective grip circle (scallop root when lobed)
        outline_outer_r=r_grip - (bite if lobes else 0.0),
    )


_register(RecipeOpDecl(
    name="knob_body",
    kind="base",
    params={
        "grip_d": ("length", None), "grip_h": ("length", 18.0),
        "shaft_sq": ("length", None), "socket_depth": ("length", 10.0),
        "fit_clearance": ("length", 0.25), "top_chamfer": ("length", 2.0),
        "lobes": ("count", 0), "lobe_bite": ("length", 2.0),
    },
    validators=(
        "form.shaft_fit_ok",
        "form.knob_torque_wall_ok",
        "topology.single_connected_solid",
    ),
    apply=_knob_body,
    description="revolved knob with a blind square shaft socket "
                "(measured fit + torque wall; lobes>0 scallops the grip)",
))
