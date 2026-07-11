"""Ratchet recipe ops — the toothed WHEEL: an asymmetric sawtooth ring
in the section itself (steep locking face + gentle ramp), extruded flat,
with a square or round shaft socket. The pawl (a sprung flexure with its
own fatigue story) is a separate iteration — a wheel without a pawl is
still a wheel; the honesty check says the mechanism is incomplete.
Measurement contract: :mod:`artifact_forge_ng.form.checks_ratchet`."""
from __future__ import annotations

import math
from typing import Any

from .part import BoreFeature, CutBoxFeature
from .profiles_revolve import loop_from_points
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from .section import Pt, SectionProfile
from ..product.archetype import RegionRole

RATCHET_TEETH_BAND = (8, 60)
RATCHET_DEPTH_MIN = 1.5      # a shallower tooth prints as a ripple
RATCHET_STEEP_FRAC_MAX = 0.15  # locking face <= this fraction of the pitch
RATCHET_TIP_ARC_MIN = 2.0    # printable tooth pitch at the tip circle
SQ_FIT_BAND = (0.1, 0.4)     # shared with the knob's shaft socket


def _ratchet_wheel_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    if state.section is not None:
        raise RecipeError("ratchet_wheel_body must be the (single) base op")
    n = int(round(p["teeth"]))
    r_tip = p["wheel_d"] / 2.0
    depth = p["tooth_depth"]
    steep = p["steep_frac"]
    t = p["t"]
    socket = p["socket"]
    lo, hi = RATCHET_TEETH_BAND
    if not lo <= n <= hi:
        raise RecipeError(f"teeth {n} outside [{lo}, {hi}]")
    if depth < RATCHET_DEPTH_MIN:
        raise RecipeError(
            f"tooth depth {depth:g} < {RATCHET_DEPTH_MIN:g} — prints as a "
            "ripple, not a ratchet")
    if depth > 0.25 * r_tip:
        raise RecipeError(
            f"tooth depth {depth:g} eats a quarter of the Ø{2 * r_tip:g} "
            "wheel")
    if not 0.02 <= steep <= RATCHET_STEEP_FRAC_MAX:
        raise RecipeError(
            f"steep_frac {steep:g} outside [0.02, {RATCHET_STEEP_FRAC_MAX:g}] "
            "— the locking face must be nearly radial or it is a worm ramp")
    pitch_arc = 2.0 * math.pi * r_tip / n
    if pitch_arc < RATCHET_TIP_ARC_MIN:
        raise RecipeError(
            f"{n} teeth on Ø{2 * r_tip:g} give a {pitch_arc:.1f} mm pitch "
            f"(min {RATCHET_TIP_ARC_MIN:g}) — unprintable serration")
    r_root = r_tip - depth

    pts: list[Pt] = []
    step = math.tau / n
    for k in range(n):
        a_tip = k * step
        a_root = a_tip + steep * step
        pts.append(Pt(r_tip * math.cos(a_tip), r_tip * math.sin(a_tip)))
        pts.append(Pt(r_root * math.cos(a_root), r_root * math.sin(a_root)))
    state.section = SectionProfile(
        name="recipe", outer=loop_from_points(pts),
        plane="XY", width_axis="Z",
    )
    state.width = t

    name = op_id or "wheel"
    if socket == "square":
        s_eff = p["shaft_sq"] + p["fit_clearance"]
        gap = p["fit_clearance"]
        flo, fhi = SQ_FIT_BAND
        if not flo <= gap <= fhi:
            raise RecipeError(
                f"fit_clearance {gap:g} outside [{flo:g}, {fhi:g}]")
        corner_reach = s_eff * math.sqrt(2.0) / 2.0
        if corner_reach >= r_root - 2.0:
            raise RecipeError(
                "square socket corners break into the tooth roots")
        half = s_eff / 2.0
        state.cutboxes.append(CutBoxFeature(
            name=f"{name}_shaft_socket",
            box=Box3(-half, -half, -1.0, half, half, t + 1.0)))
        state.frame.update(shaft_sq=p["shaft_sq"], socket_w_eff=s_eff,
                           socket_depth=t, fit_clearance=gap)
    elif socket == "round":
        bore = p["shaft_sq"] + p["fit_clearance"]
        if bore / 2.0 >= r_root - 2.0:
            raise RecipeError("round socket breaks into the tooth roots")
        state.bores.append(BoreFeature(
            name=f"{name}_shaft_bore", axis="Z", d=bore,
            center=(0.0, 0.0, 0.0), span=(0.0, t), overshoot=(1.0, 1.0)))
    else:
        raise RecipeError(f"socket {socket!r} not in (square, round)")

    state.regions.append(Region(
        f"{name}_teeth", RegionRole.HIGH_STRESS_REGION,
        Box3(-r_tip, -r_tip, 0.0, r_tip, r_tip, t)))
    state.datums["wheel_axis"] = {
        "at": [0.0, 0.0, t / 2.0], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        ratchet_teeth=float(n), ratchet_tooth_depth=depth,
        ratchet_r_tip=r_tip, ratchet_r_root=r_root,
        ratchet_steep_frac=steep, ratchet_pitch_arc=pitch_arc,
        outline_outer_r=r_root,
    )


_register(RecipeOpDecl(
    name="ratchet_wheel_body",
    kind="base",
    params={
        "wheel_d": ("length", None),
        "teeth": ("count", 24),
        "tooth_depth": ("length", 2.5),
        "steep_frac": ("number", 0.08),
        "t": ("length", 6.0),
        "socket": ("choice", "square"),
        "shaft_sq": ("length", 8.0),
        "fit_clearance": ("length", 0.25),
    },
    validators=(
        "form.ratchet_teeth_ok",
        "form.ratchet_pawl_unverified",
        "topology.single_connected_solid",
    ),
    apply=_ratchet_wheel_body,
    description="asymmetric sawtooth ratchet wheel (steep locking face + "
                "ramp in the section) with a square/round shaft socket; "
                "the pawl is its own iteration",
))
