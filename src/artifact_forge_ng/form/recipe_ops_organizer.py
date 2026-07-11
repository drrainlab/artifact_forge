"""Organizer recipe ops — features that turn a rounded_box_shell into a
drawer/storage bin: interior divider walls, an open finger scoop through
a rim, and a stacking lip so same-family bins nest. Measurement contract
lives in :mod:`artifact_forge_ng.form.checks_organizer`."""
from __future__ import annotations

from typing import Any

from .part import BoreFeature, CutBoxFeature, PlateFeature, RibFeature
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from ..product.archetype import RegionRole

WELD = 0.6              # the standard weld overlap into a host body, mm
MIN_DIVIDER_T = 1.2     # a thinner wall shears off with the first pull
SCOOP_FLOOR_MIN = 8.0   # material the scoop must leave above the floor, mm
MIN_LIP_WALL = 1.2      # thinnest printable nesting lip, mm


def _bin_dividers(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Interior divider walls welded into a rounded_box_shell cavity:
    ``nx`` walls across the length (planes of constant X) and ``ny``
    across the width. Cell sizes are published to the frame — the
    divider checks measure them, never recompute them."""
    state.require_base("bin_dividers")
    f = state.frame
    if "inner_u0" not in f or "floor_t" not in f:
        raise RecipeError("bin_dividers needs a rounded_box_shell base")
    nx, ny = int(round(p["nx"])), int(round(p["ny"]))
    t = p["divider_t"]
    min_cell = p["min_cell"]
    if nx < 0 or ny < 0:
        raise RecipeError("bin_dividers counts must be >= 0")
    if t < MIN_DIVIDER_T:
        raise RecipeError(f"divider_t {t:g} < {MIN_DIVIDER_T:g}")
    u0, v0, u1, v1 = f["inner_u0"], f["inner_v0"], f["inner_u1"], f["inner_v1"]
    floor_t, shell_h = f["floor_t"], f["shell_h"]
    height = p["height"]
    z_top = floor_t + height if height > 1e-9 else shell_h
    if z_top > shell_h + 1e-9:
        raise RecipeError("divider height rises past the shell rim")

    cell_x = ((u1 - u0) - nx * t) / (nx + 1)
    cell_y = ((v1 - v0) - ny * t) / (ny + 1)
    if nx and cell_x < min_cell:
        raise RecipeError(
            f"{nx} dividers leave {cell_x:.1f} mm cells along X "
            f"(min {min_cell:g})")
    if ny and cell_y < min_cell:
        raise RecipeError(
            f"{ny} dividers leave {cell_y:.1f} mm cells along Y "
            f"(min {min_cell:g})")

    name = op_id or "dividers"
    for i in range(nx):
        x = u0 + (i + 1) * (cell_x + t) - t / 2.0
        state.ribs.append(RibFeature(
            name=f"{name}_div_x_{i}",
            box=Box3(x, v0 - WELD, floor_t - WELD, x + t, v1 + WELD, z_top)))
        state.regions.append(Region(
            f"{name}_root_x_{i}", RegionRole.FASTENER_KEEPOUT,
            Box3(x - 1.0, v0, 0.0, x + t + 1.0, v1, floor_t)))
    for j in range(ny):
        y = v0 + (j + 1) * (cell_y + t) - t / 2.0
        state.ribs.append(RibFeature(
            name=f"{name}_div_y_{j}",
            box=Box3(u0 - WELD, y, floor_t - WELD, u1 + WELD, y + t, z_top)))
        state.regions.append(Region(
            f"{name}_root_y_{j}", RegionRole.FASTENER_KEEPOUT,
            Box3(u0, y - 1.0, 0.0, u1, y + t + 1.0, floor_t)))
    state.frame.update(
        divider_nx=float(nx), divider_ny=float(ny), divider_t=t,
        divider_z_top=z_top, divider_min_cell=min_cell,
        cell_w=cell_x, cell_l=cell_y,
    )


_register(RecipeOpDecl(
    name="bin_dividers",
    kind="feature",
    params={
        "nx": ("count", 1), "ny": ("count", 0),
        "divider_t": ("length", 2.0), "height": ("length", 0.0),
        "min_cell": ("length", 20.0),
    },
    validators=(
        "form.dividers_span_cavity",
        "form.divider_cells_min_size",
        "topology.ribs_present",
    ),
    apply=_bin_dividers,
    description="interior divider walls welded into a box shell "
                "(height 0 = full interior height)",
))


def _finger_scoop(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A rounded finger cove through one wall, open through the rim: a
    horizontal bore whose center sits ``drop`` below the rim, so the
    notch stays open by construction (drop < scoop_d/2)."""
    state.require_base("finger_scoop")
    f = state.frame
    if "shell_wall" not in f:
        raise RecipeError("finger_scoop needs a rounded_box_shell base")
    d, drop, off = p["scoop_d"], p["drop"], p["offset"]
    face = p["face"]
    h, wall, floor_t = f["shell_h"], f["shell_wall"], f["floor_t"]
    if drop >= d / 2.0 - 1.0:
        raise RecipeError(
            f"drop {drop:g} closes the scoop (must stay under "
            f"scoop_d/2 - 1 = {d / 2.0 - 1.0:g})")
    center_z = h - drop
    bottom_z = center_z - d / 2.0
    if bottom_z < floor_t + SCOOP_FLOOR_MIN:
        raise RecipeError(
            f"scoop bottom {bottom_z:.1f} dips under floor + "
            f"{SCOOP_FLOOR_MIN:g}")
    name = op_id or "scoop"
    if face in ("+y", "-y"):
        edge = f["outline_v1"] if face == "+y" else f["outline_v0"]
        c = edge - wall / 2.0 if face == "+y" else edge + wall / 2.0
        state.bores.append(BoreFeature(
            name=name, axis="Y", d=d, center=(off, c, center_z),
            span=(c - wall / 2.0 - 1.0, c + wall / 2.0 + 1.0),
            overshoot=(1.0, 1.0)))
    elif face in ("+x", "-x"):
        edge = f["outline_u1"] if face == "+x" else f["outline_u0"]
        c = edge - wall / 2.0 if face == "+x" else edge + wall / 2.0
        state.bores.append(BoreFeature(
            name=name, axis="X", d=d, center=(c, off, center_z),
            span=(c - wall / 2.0 - 1.0, c + wall / 2.0 + 1.0),
            overshoot=(1.0, 1.0)))
    else:
        raise RecipeError(f"finger_scoop face {face!r} not in (+x, -x, +y, -y)")
    state.frame.update(
        scoop_d=d, scoop_bottom_z=bottom_z, scoop_center_z=center_z,
    )


_register(RecipeOpDecl(
    name="finger_scoop",
    kind="feature",
    params={
        "scoop_d": ("length", 30.0), "drop": ("length", 2.0),
        "face": ("choice", "+y"), "offset": ("length", 0.0),
    },
    validators=("form.scoop_clears_floor", "topology.bores_open"),
    apply=_finger_scoop,
    description="rounded finger cove through one wall, open through the rim",
))


def _stacking_lip(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Nesting rim: a lip ring rises from the INNER edge of the rim, and
    the bottom outer perimeter is rebated so the floor plug of the next
    bin drops inside a sibling's lip — the classic stacking-box joint.
    The rebate stays SHALLOWER than the floor (it never severs the wall
    from the floor), which bounds lip_h to floor_t - clearance - 0.2."""
    state.require_base("stacking_lip")
    f = state.frame
    if "shell_wall" not in f:
        raise RecipeError("stacking_lip needs a rounded_box_shell base")
    lip_h, lip_wall, c = p["lip_h"], p["lip_wall"], p["clearance"]
    wall, h, floor_t = f["shell_wall"], f["shell_h"], f["floor_t"]
    if lip_wall < MIN_LIP_WALL:
        raise RecipeError(f"lip_wall {lip_wall:g} < {MIN_LIP_WALL:g}")
    if lip_wall > wall + 1e-9:
        raise RecipeError(
            f"lip_wall {lip_wall:g} wider than the {wall:g} wall")
    gz = lip_h + c
    if gz > floor_t - 0.2 + 1e-9:
        raise RecipeError(
            f"rebate {gz:g} (lip_h + clearance) must stay under "
            f"floor_t - 0.2 = {floor_t - 0.2:g} — a deeper rebate severs "
            "the wall from the floor")
    u0, v0, u1, v1 = f["outline_u0"], f["outline_v0"], f["outline_u1"], f["outline_v1"]
    iu0, iv0, iu1, iv1 = f["inner_u0"], f["inner_v0"], f["inner_u1"], f["inner_v1"]
    name = op_id or "lip"

    # the lip ring on the inner rim band: a plate with its middle cut out
    corner_r = max(0.5, f.get("outline_corner_r", 3.0) - (wall - lip_wall))
    state.plates.append(PlateFeature(
        name=f"{name}_ring",
        x0=iu0 - lip_wall, y0=iv0 - lip_wall,
        x1=iu1 + lip_wall, y1=iv1 + lip_wall,
        z_bottom=h - WELD, thickness=lip_h + WELD, corner_r=corner_r))
    state.cutboxes.append(CutBoxFeature(
        name=f"{name}_ring_hollow",
        box=Box3(iu0, iv0, h - 0.05, iu1, iv1, h + lip_h + 1.0)))

    # the bottom rebate: 4 overlapping bands strip the outer perimeter
    # down to the floor plug that nests inside a sibling's lip
    pu0, pv0, pu1, pv1 = iu0 + c, iv0 + c, iu1 - c, iv1 - c
    if pu1 - pu0 < 10.0 or pv1 - pv0 < 10.0:
        raise RecipeError("stacking rebate leaves no standing plug")
    o = 1.0
    for i, box in enumerate((
        Box3(u0 - o, v0 - o, -1.0, u1 + o, pv0, gz),   # -y band
        Box3(u0 - o, pv1, -1.0, u1 + o, v1 + o, gz),   # +y band
        Box3(u0 - o, pv0, -1.0, pu0, pv1, gz),         # -x band
        Box3(pu1, pv0, -1.0, u1 + o, pv1, gz),         # +x band
    )):
        state.cutboxes.append(CutBoxFeature(name=f"{name}_rebate_{i}", box=box))

    state.datums["stack_rim"] = {
        "at": [0.0, 0.0, h + lip_h], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        lip_h=lip_h, lip_wall=lip_wall, lip_clearance=c,
        lip_inner_u0=iu0, lip_inner_v0=iv0, lip_inner_u1=iu1, lip_inner_v1=iv1,
        plug_u0=pu0, plug_v0=pv0, plug_u1=pu1, plug_v1=pv1,
        recess_depth=gz,
    )


_register(RecipeOpDecl(
    name="stacking_lip",
    kind="feature",
    params={
        "lip_h": ("length", 4.0), "lip_wall": ("length", 1.6),
        "clearance": ("length", 0.3),
    },
    validators=(
        "form.stacking_lip_nests",
        "topology.cutout_present",
        "topology.single_connected_solid",
    ),
    apply=_stacking_lip,
    description="nesting rim lip + matching bottom groove so the same "
                "bin family stacks",
))
