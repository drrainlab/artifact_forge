"""Jig-domain recipe ops — production-aid features on the core plate IR:
a press-fit line of steel drill-bushing seats and a hooked stop fence
(the registration edge). Shop-probe tier: verify the first article —
these are not certified measuring tools (docs/CLAIMS.md)."""
from __future__ import annotations

from typing import Any

from artifact_forge_ng.form.part import BoreFeature, RibFeature
from artifact_forge_ng.form.recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from artifact_forge_ng.form.regions import Box3, Region
from artifact_forge_ng.product.archetype import RegionRole

PRESS_FIT_BAND = (0.05, 0.2)   # diametral steel-in-plastic press band, mm
SEAT_ENGAGEMENT_K = 0.5        # plate thickness >= k * bushing OD
SEAT_WALL_MIN = 3.0            # plastic around a seat, mm
FENCE_DROP_BAND = (4.0, 25.0)  # fence reach below the plate, mm


def _bushing_seat_line(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """N press-fit through seats for steel drill bushings along a line at
    (cx, cy). The seat bore is bushing OD minus the press interference —
    the steel bushing, not the plastic, guides the drill."""
    state.require_base("bushing_seat_line")
    od, press = p["bushing_od"], p["press_fit"]
    count, spacing = int(p["count"]), p["spacing"]
    cx, cy = p["cx"], p["cy"]
    t = state.width
    lo, hi = PRESS_FIT_BAND
    if not lo <= press <= hi:
        raise RecipeError(
            f"press_fit {press:g} outside [{lo:g}, {hi:g}] — a loose bushing "
            "spins, an over-pressed one splits the plate")
    if count < 1:
        raise RecipeError("bushing_seat_line needs count >= 1")
    seat_d = od - press
    name = op_id or "bushings"
    x0 = cx - spacing * (count - 1) / 2.0
    for i in range(count):
        x = x0 + i * spacing
        state.bores.append(BoreFeature(
            name=f"{name}_{i}", axis="Z", d=seat_d,
            center=(x, cy, 0.0), span=(0.0, t), overshoot=(1.0, 1.0)))
        state.regions.append(Region(
            f"{name}_{i}_keepout", RegionRole.FASTENER_KEEPOUT,
            Box3(x - od / 2 - SEAT_WALL_MIN, cy - od / 2 - SEAT_WALL_MIN, 0.0,
                 x + od / 2 + SEAT_WALL_MIN, cy + od / 2 + SEAT_WALL_MIN, t)))
    state.frame.update(
        bushing_od=od,
        bushing_seat_d=seat_d,
        bushing_press_fit=press,
        bushing_count=float(count),
        bushing_spacing=spacing,
        bushing_row_cy=cy,
        seat_engagement=t,
    )


_register(RecipeOpDecl(
    name="bushing_seat_line",
    kind="feature",
    params={
        "bushing_od": ("length", None), "press_fit": ("length", 0.1),
        "count": ("count", 2), "spacing": ("length", 25.0),
        "cx": ("length", 0.0), "cy": ("length", 0.0),
    },
    validators=("form.bushing_fit_ok", "topology.bores_open"),
    apply=_bushing_seat_line,
    description="press-fit through seats for steel drill bushings along "
                "a line (seat Ø = bushing OD - press interference)",
))


def _stop_fence(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A fence welded under one long edge of the plate — the jig hooks
    over the workpiece edge, so every drilled hole repeats at the same
    distance from that edge."""
    state.require_base("stop_fence")
    t = state.width
    f = state.frame
    needed = ("outline_u0", "outline_v0", "outline_u1", "outline_v1")
    if any(k not in f for k in needed):
        raise RecipeError("stop_fence needs a rounded_plate base (outline)")
    fence_t, drop = p["fence_t"], p["fence_drop"]
    lo, hi = FENCE_DROP_BAND
    if not lo <= drop <= hi:
        raise RecipeError(f"fence_drop {drop:g} outside [{lo:g}, {hi:g}]")
    u0, v0, u1, _v1 = (f[k] for k in needed)
    name = op_id or "fence"
    # under the -v edge, full plate length, reaching below the plate
    box = Box3(u0, v0, -drop, u1, v0 + fence_t, 1.0)
    state.ribs.append(RibFeature(name=f"{name}_bar", box=box))
    state.regions.append(Region(
        f"{name}_face", RegionRole.MOUNTING_SURFACE,
        Box3(u0, v0 + fence_t - 0.1, -drop, u1, v0 + fence_t + 0.1, 0.0)))
    state.frame.update(
        fence_len=u1 - u0,
        fence_t=fence_t,
        fence_drop=drop,
        fence_face_v=v0 + fence_t,
        fence_plate_len=u1 - u0,
        plate_t=t,
    )


_register(RecipeOpDecl(
    name="stop_fence",
    kind="feature",
    params={
        "fence_t": ("length", 5.0), "fence_drop": ("length", 8.0),
    },
    validators=("form.stop_registration_ok", "topology.ribs_present"),
    apply=_stop_fence,
    description="registration fence welded under one plate edge — the jig "
                "hooks over the workpiece so every hole repeats",
))
