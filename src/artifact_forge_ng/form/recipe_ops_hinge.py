"""Hinge recipe ops — the pin/friction hinge LEAF: a mounting plate
whose edge carries interleaved knuckle barrel segments around one axial
bore. Two leaves (side a + side b) mesh into a hinge; the pin is
hardware (a nail, a music-wire pin) or, in bolt mode, a bolt whose
preload turns the pair into a FRICTION hinge. Printed-in-place hinges
are deliberately out — a fused pin is a broken hinge, not a feature.
Measurement contract: :mod:`artifact_forge_ng.form.checks_hinge`."""
from __future__ import annotations

from typing import Any

from ..core.fasteners import FDM_CLEARANCE, screw_spec
from .part import BoreFeature, PinFeature
from .profiles_plate import rounded_rect_loop
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from .section import SectionProfile
from ..product.archetype import RegionRole

#: Diametral slip band for a hardware pin in the printed barrel bore.
HINGE_PIN_SLIP_BAND = (0.2, 0.6)
#: Axial gap between meshing knuckles, per joint.
HINGE_GAP_BAND = (0.2, 0.8)
HINGE_WELD_BITE = 1.2


def _hinge_leaf(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """One hinge leaf: plate + interleaved knuckle segments + the axial
    pin bore (teardrop — the barrel prints flat on the bed). ``side``
    a takes the even segment slots, b the odd ones; a printed a+b pair
    meshes with the declared axial gap by construction."""
    if state.section is not None:
        raise RecipeError("hinge_leaf must be the (single) base op")
    leaf_l, leaf_w, t = p["leaf_l"], p["leaf_w"], p["t"]
    kd = p["knuckle_d"]
    n = int(round(p["knuckles"]))
    side = p["side"]
    mode = p["mode"]
    gap = p["gap"]
    if side not in ("a", "b"):
        raise RecipeError(f"side {side!r} not in (a, b)")
    if mode not in ("pin", "bolt"):
        raise RecipeError(f"mode {mode!r} not in (pin, bolt)")
    if n < 3 or n % 2 == 0:
        raise RecipeError(
            f"knuckles {n} must be odd and >= 3 — an even split leaves "
            "one leaf holding the whole moment")
    lo, hi = HINGE_GAP_BAND
    if not lo <= gap <= hi:
        raise RecipeError(f"gap {gap:g} outside [{lo:g}, {hi:g}]")
    if kd < t:
        raise RecipeError(
            f"knuckle Ø{kd:g} thinner than the {t:g} plate — the barrel "
            "must swallow the leaf edge")
    if mode == "pin":
        pin_d = p["pin_d"]
        bore_d = pin_d + p["pin_clearance"]
    else:
        spec = screw_spec(p["screw"])
        pin_d = spec["clear"]
        bore_d = spec["clear"] + FDM_CLEARANCE
    if bore_d + 2.0 > kd:
        raise RecipeError(
            f"bore Ø{bore_d:g} leaves under 1 mm barrel wall in Ø{kd:g}")

    u0, v0, u1, v1 = -leaf_l / 2.0, -leaf_w / 2.0, leaf_l / 2.0, leaf_w / 2.0
    state.section = SectionProfile(
        name="recipe", outer=rounded_rect_loop(u0, v0, u1, v1, p["corner_r"]),
        plane="XY", width_axis="Z",
    )
    state.width = t
    name = op_id or "leaf"

    # the barrel line: tangent to the bed, biting into the +Y plate edge
    cz = kd / 2.0
    cy = v1 + kd / 2.0 - HINGE_WELD_BITE
    pitch = leaf_l / n
    slots = range(0, n, 2) if side == "a" else range(1, n, 2)
    count = 0
    for k in slots:
        x0 = u0 + k * pitch + gap / 2.0
        seg = pitch - gap
        state.pins.append(PinFeature(
            name=f"{name}_knuckle_{k}", axis="X", at=(cy, cz), d=kd,
            z0=x0, length=seg, bore_d=bore_d))
        count += 1
    state.bores.append(BoreFeature(
        name=f"{name}_pin_bore", axis="X", d=bore_d,
        center=(0.0, cy, cz), span=(u0, u1), overshoot=(1.0, 1.0),
        roof="teardrop"))

    state.regions.extend([
        Region(name, RegionRole.MOUNTING_SURFACE,
               Box3(u0, v0, 0.0, u1, v1, t)),
        # the lightening canvas stops short of the barrel edge — fields
        # never reach the hinge; no explicit keepout (it would veto the
        # barrel's own pin bore — the bearing-seat lesson)
        Region(f"{name}_lightening", RegionRole.AESTHETIC_LIGHTENING,
               Box3(u0 + 4.0, v0 + 4.0, 0.0, u1 - 4.0, v1 - 4.0, t)),
    ])
    state.datums["hinge_axis"] = {
        "at": [0.0, cy, cz], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=p["corner_r"], plate_t=t,
        hinge_side=0.0 if side == "a" else 1.0,
        hinge_knuckles_total=float(n),
        hinge_knuckles_mine=float(count),
        hinge_pitch=pitch, hinge_gap=gap,
        hinge_knuckle_d=kd, hinge_bore_d=bore_d, hinge_pin_d=pin_d,
        hinge_is_bolt=0.0 if mode == "pin" else 1.0,
        hinge_axis_y=cy, hinge_axis_z=cz,
    )


_register(RecipeOpDecl(
    name="hinge_leaf",
    kind="base",
    params={
        "leaf_l": ("length", None),
        "leaf_w": ("length", None),
        "t": ("length", 3.0),
        "corner_r": ("length", 3.0),
        "knuckle_d": ("length", 8.0),
        "knuckles": ("count", 5),
        "side": ("choice", "a"),
        "mode": ("choice", "pin"),
        "gap": ("length", 0.4),
        "pin_d": ("length", 3.0),
        "pin_clearance": ("length", 0.35),
        "screw": ("choice", "m4"),
    },
    validators=(
        "form.hinge_pin_fit_ok",
        "form.hinge_knuckle_geometry_ok",
        "form.hinge_motion_unverified",
        "topology.pins_present",
        "topology.bores_open",
        "topology.single_connected_solid",
    ),
    apply=_hinge_leaf,
    description="hinge leaf: plate + interleaved knuckle barrel + axial "
                "teardrop pin bore (side a/b mesh; mode bolt = friction "
                "hinge via preload)",
))
