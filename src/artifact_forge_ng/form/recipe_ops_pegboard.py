"""Pegboard recipe ops — the interface BASE, not one holder per tool: a
plate whose back grows board-standard pegs (straight or L-hooked, with an
anti-lift row). Holders for specific tools compose payload features on
the plate FACE; the peg side stays one measured standard.

Model frame: the plate lies in XY with its back at z=0; pegs descend -Z.
Mounted, plate-local +Y is world-up — the L-hook tips turn +Y, so both
peg cylinders stay axis-aligned (no angled geometry needed).
Measurement contract: :mod:`artifact_forge_ng.form.checks_pegboard`."""
from __future__ import annotations

from typing import Any

from .part import PinFeature
from .patterns import grid_centers
from .recipe_ops_core import KEEPOUT_CLEARANCE, RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from ..product.archetype import RegionRole

#: (pitch, hole_d, peg_d, board_t) per board standard, mm.
PEG_BOARDS: dict[str, tuple[float, float, float, float]] = {
    # 1" pitch, 1/4" holes — the classic US hardware pegboard
    "imperial_quarter": (25.4, 6.35, 6.0, 6.4),
    # 25 mm pitch, 6 mm holes — common metric shop boards
    "metric_25": (25.0, 6.0, 5.6, 6.0),
}

#: Peg-in-hole diametral fit band: hole_d - peg_d must land here.
PEG_FIT_BAND = (0.15, 0.8)
MIN_HOOK_LEN = 4.0


def _peg_pattern(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    state.require_base("peg_pattern")
    f = state.frame
    if "outline_u0" not in f:
        raise RecipeError("peg_pattern needs a rounded_plate base")
    board = p["board"]
    if board not in PEG_BOARDS:
        raise RecipeError(f"unknown board {board!r}; known: {sorted(PEG_BOARDS)}")
    pitch, hole_d, peg_d, board_t = PEG_BOARDS[board]
    cols, rows = int(round(p["cols"])), int(round(p["rows"]))
    hook = p["hook"]
    hook_len = p["hook_len"]
    anti_lift = int(round(p["anti_lift"]))
    peg_len = p["peg_len"] if p["peg_len"] > 1e-9 else board_t + peg_d / 2.0 + 1.0
    if cols < 1 or rows < 1:
        raise RecipeError("peg_pattern needs cols, rows >= 1")
    if hook not in ("none", "up"):
        raise RecipeError(f"hook {hook!r} not in (none, up)")
    if hook == "up" and hook_len < MIN_HOOK_LEN:
        raise RecipeError(f"hook_len {hook_len:g} < {MIN_HOOK_LEN:g}")
    if peg_len < board_t + 1.0:
        raise RecipeError(
            f"peg_len {peg_len:g} never passes the {board_t:g} board")

    name = op_id or "pegs"
    cx, cy = p["cx"], p["cy"]
    centers = list(grid_centers(cols, rows, pitch, pitch, (cx, cy)))
    if anti_lift and hook == "up":
        # a straight peg one pitch below the hooked row resists lift-off
        lowest = min(y for _, y in centers)
        centers.extend(
            (x, lowest - pitch)
            for x, y in centers if abs(y - lowest) < 1e-6)
    hook_count = 0
    for i, (px, py) in enumerate(centers):
        is_hooked = hook == "up" and i < cols * rows
        state.pins.append(PinFeature(
            name=f"{name}_{i}", axis="Z", at=(px, py), d=peg_d,
            z0=-peg_len, length=peg_len + 0.6))
        if is_hooked:
            hook_count += 1
            # tip center rides 0.5 above the peg's end plane — a flush
            # tangency between the tip cylinder and the peg's end cap is
            # OCC-invalid geometry, an overlap welds
            state.pins.append(PinFeature(
                name=f"{name}_{i}_tip", axis="Y",
                at=(px, -peg_len + peg_d / 2.0 + 0.5), d=peg_d,
                z0=py, length=hook_len))
        r_keep = peg_d / 2.0 + KEEPOUT_CLEARANCE
        state.regions.append(Region(
            f"{name}_root_{i}", RegionRole.FASTENER_KEEPOUT,
            Box3(px - r_keep, py - r_keep, 0.0,
                 px + r_keep, py + r_keep, state.width)))
        state.frame[f"{name}_{i}_x"] = px
        state.frame[f"{name}_{i}_y"] = py
    state.datums["board_face"] = {
        "at": [cx, cy, 0.0], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        peg_pitch=pitch, peg_d=peg_d, peg_len=peg_len,
        peg_count=float(len(centers)), board_t=board_t,
        board_hole_d=hole_d,
        peg_hook_len=hook_len if hook == "up" else 0.0,
        peg_hook_count=float(hook_count),
        peg_anti_lift=float(len(centers) - cols * rows),
    )


_register(RecipeOpDecl(
    name="peg_pattern",
    kind="feature",
    params={
        "board": ("choice", "imperial_quarter"),
        "cols": ("count", 1), "rows": ("count", 1),
        "peg_len": ("length", 0.0),
        "hook": ("choice", "up"), "hook_len": ("length", 8.0),
        "anti_lift": ("count", 1),
        "cx": ("length", 0.0), "cy": ("length", 0.0),
    },
    validators=(
        "form.peg_engagement_ok",
        "topology.pins_present",
        "topology.single_connected_solid",
    ),
    apply=_peg_pattern,
    description="board-standard pegs on the plate back (straight or "
                "L-hooked + anti-lift row); the board is external hardware",
))
