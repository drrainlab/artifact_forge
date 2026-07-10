"""Fit-interface and fastener recipe ops — plugs, pins, counterbores,
heat-set pockets, standoffs, nut traps, wire exits, snap pairs, truss webs.
"""
from __future__ import annotations

import math
from typing import Any
from ..core.fasteners import screw_spec
from .regions import Box3, Region
from ..product.archetype import RegionRole
from .part import BoreFeature, CutBoxFeature, PinFeature, PlateFeature, RibFeature
from .recipe_ops_base import _HOLE_PARAMS, _hole_pattern
from .recipe_ops_core import KEEPOUT_CLEARANCE, RecipeError, RecipeState, RecipeOpDecl, _register


# -- fit-interface & fastener ops (registry completion wave) -------------------


def _inset_plug(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The lid's plug: a smaller plate welded ON TOP of the base plate.
    The lid is MODELED plug-up (plate on the bed, plug and pins rising —
    the natural print orientation); the lid_seat joint flips it 180 into
    the box. Frame publishes the plug chain the joint verifies."""
    state.require_base("inset_plug")
    f = state.frame
    if "outline_u0" not in f:
        raise RecipeError("inset_plug needs a rounded_plate base")
    l, w, depth = p["l"], p["w"], p["depth"]
    if l >= (f["outline_u1"] - f["outline_u0"]) or w >= (f["outline_v1"] - f["outline_v0"]):
        raise RecipeError("plug larger than its own lid plate")
    t = state.width
    state.plates.append(
        PlateFeature(
            name=op_id or "plug",
            x0=-l / 2.0, y0=-w / 2.0, x1=l / 2.0, y1=w / 2.0,
            z_bottom=t - 0.6,  # weld overlap into the lid plate
            thickness=depth + 0.6,
            corner_r=p["corner_r"],
        )
    )
    state.frame.update(
        plug_u0=-l / 2.0, plug_v0=-w / 2.0, plug_u1=l / 2.0, plug_v1=w / 2.0,
        plug_depth=depth, plug_corner_r=p["corner_r"],
        plug_top_z=t + depth, plug_mid_z=t + depth / 2.0,
    )
    # The mating plane: the plate top, where the plug starts.
    state.datums["seat"] = {"at": [0.0, 0.0, t], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="inset_plug",
    kind="feature",
    params={
        "l": ("length", None), "w": ("length", None),
        "depth": ("length", 4.0), "corner_r": ("length", 3.0),
    },
    validators=("topology.single_connected_solid",),
    apply=_inset_plug,
    description="lid plug plate welded under the base — mates a box shell",
))


def _pin_pair(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Two press-fit/alignment pins rising +Z from ``z0`` (a lid's plug
    top in the model frame; the assembly pose flips them into the box's
    receiving bores), spaced along X."""
    state.require_base("pin_pair")
    sx = p["spacing"] / 2.0
    cx, cy = p["cx"], p["cy"]
    z0 = p["z0"] if p["z0"] > 1e-9 else state.width
    name = op_id or "pins"
    for i, px in enumerate((cx - sx, cx + sx)):
        state.pins.append(
            PinFeature(
                name=f"{name}_{i}", at=(px, cy), d=p["pin_d"],
                z0=z0 - 0.6, length=p["length"] + 0.6,  # weld overlap
            )
        )
        state.frame[f"{name}_{i}_x"] = px
        state.frame[f"{name}_{i}_y"] = cy
    state.frame[f"{name}_d"] = p["pin_d"]
    state.frame[f"{name}_len"] = p["length"]


_register(RecipeOpDecl(
    name="pin_pair",
    kind="feature",
    params={
        "pin_d": ("length", 4.1), "length": ("length", 5.0),
        "spacing": ("length", None), "cx": ("length", 0.0),
        "cy": ("length", 0.0), "z0": ("length", 0.0),
    },
    validators=("topology.pins_present",),
    apply=_pin_pair,
    description="press-fit/alignment pin pair rising +Z (z0=0 means the part top)",
))


def _counterbore_hole_pattern(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    state.require_base("counterbore_hole_pattern")
    _hole_pattern(state, p, op_id, countersunk=False, counterbore=True)


_register(RecipeOpDecl(
    name="counterbore_hole_pattern",
    kind="feature",
    params=_HOLE_PARAMS,
    validators=(
        "form.min_web_between_holes",
        "form.holes_within_outline",
        "topology.screw_holes_open",
        "topology.countersinks_present",
    ),
    apply=_counterbore_hole_pattern,
    description="cylindrical-head recesses (socket-cap screws) over clearance holes",
))


def _heatset_insert_pocket(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Blind pockets sized for heatset inserts, entered from the top face.

    ``z_top`` = 0 is the legacy behavior (pockets descend from the part's
    ``state.width`` top — the plate archetypes). A positive ``z_top`` names
    the entry plane explicitly (a clamp wing top, a rail top) AND drops a
    FASTENER_KEEPOUT column under each pocket down to z=0 (the boss_pattern
    floor-slab trick) so later cuts through the bolt column honestly fail
    ``form.cuts_respect_keepouts``."""
    state.require_base("heatset_insert_pocket")
    spec = screw_spec(p["screw"])
    t = state.width
    depth = p["depth"]
    z_top = p.get("z_top", 0.0)  # .get: direct callers predate the param
    if z_top <= 1e-9:
        # legacy path — behavior kept EXACTLY (fastener_plate_v1 and friends)
        if depth >= t - 0.8:
            raise RecipeError("heatset pocket would pierce the plate")
        z_top = t
        keepout_column = False
    else:
        if depth >= z_top - 0.8:
            raise RecipeError("heatset pocket would pierce below its entry plane")
        keepout_column = True
    sx = p["spacing"] / 2.0
    name = op_id or "inserts"
    r_keep = spec["heatset"] / 2.0 + KEEPOUT_CLEARANCE
    for i, px in enumerate((p["cx"] - sx, p["cx"] + sx)):
        state.bores.append(
            BoreFeature(
                name=f"{name}_{i}", axis="Z", center=(px, p["cy"], 0.0),
                d=spec["heatset"], span=(z_top - depth, z_top), overshoot=(0.0, 1.0),
            )
        )
        if keepout_column and z_top - depth - 0.5 > 0.0:
            state.regions.append(
                Region(f"{name}_keep_{i}", RegionRole.FASTENER_KEEPOUT,
                       Box3(px - r_keep, p["cy"] - r_keep, 0.0,
                            px + r_keep, p["cy"] + r_keep,
                            z_top - depth - 0.5))
            )
        state.frame[f"{name}_{i}_x"] = px
        state.frame[f"{name}_{i}_y"] = p["cy"]


_register(RecipeOpDecl(
    name="heatset_insert_pocket",
    kind="feature",
    params={
        "screw": ("choice", "M3"), "depth": ("length", 5.0),
        "spacing": ("length", None), "cx": ("length", 0.0),
        "cy": ("length", 0.0), "z_top": ("length", 0.0),
    },
    validators=("topology.pockets_present",),
    apply=_heatset_insert_pocket,
    description="blind pockets sized from the heatset table, pair along X "
                "(z_top>0: explicit entry plane + bolt-column keepout)",
))


def _standoff_pattern(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """PCB standoffs rising from a PLATE top (the plate cousin of
    boss_pattern, which needs a shell floor)."""
    state.require_base("standoff_pattern")
    t = state.width
    sx, sy = p["sx"] / 2.0, p["sy"] / 2.0
    cx, cy = p["cx"], p["cy"]
    boss, height = p["boss"], p["height"]
    pilot_d, pilot_depth = p["pilot_d"], p["pilot_depth"]
    if pilot_depth >= height + t - 0.8:
        raise RecipeError("standoff pilot would pierce the plate")
    name = op_id or "standoffs"
    top = t + height
    for i, (bx, by) in enumerate(
        [(cx - sx, cy - sy), (cx + sx, cy - sy), (cx + sx, cy + sy), (cx - sx, cy + sy)]
    ):
        state.ribs.append(
            RibFeature(
                name=f"{name}_{i}",
                box=Box3(bx - boss / 2.0, by - boss / 2.0, t - 0.6,
                         bx + boss / 2.0, by + boss / 2.0, top),
            )
        )
        state.bores.append(
            BoreFeature(
                name=f"{name}_pilot_{i}", axis="Z", center=(bx, by, 0.0),
                d=pilot_d, span=(top - pilot_depth, top), overshoot=(0.0, 1.0),
            )
        )
        state.regions.append(
            Region(f"{name}_keep_{i}", RegionRole.FASTENER_KEEPOUT,
                   Box3(bx - boss / 2.0 - KEEPOUT_CLEARANCE,
                        by - boss / 2.0 - KEEPOUT_CLEARANCE, 0.0,
                        bx + boss / 2.0 + KEEPOUT_CLEARANCE,
                        by + boss / 2.0 + KEEPOUT_CLEARANCE, t))
        )
        state.frame[f"{name}_{i}_x"] = bx
        state.frame[f"{name}_{i}_y"] = by


_register(RecipeOpDecl(
    name="standoff_pattern",
    kind="feature",
    params={
        "sx": ("length", None), "sy": ("length", None),
        "cx": ("length", 0.0), "cy": ("length", 0.0),
        "boss": ("length", 7.0), "height": ("length", 6.0),
        "pilot_d": ("length", 2.7), "pilot_depth": ("length", 5.0),
    },
    validators=("topology.ribs_present", "topology.pockets_present"),
    apply=_standoff_pattern,
    description="4 PCB standoffs with blind pilots, rising from a plate top",
))


def _nut_trap(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Top-access hex nut pocket over a through screw bore. The hexagon is
    cut FLAT-TO-FLAT correct (the 30-degree lesson) with FDM clearance on
    the across-flats size."""
    from .part import FieldFeature

    state.require_base("nut_trap")
    spec = screw_spec(p["screw"])
    af = spec["nut_af"] + 2.0 * p["clearance"]
    nut_h = spec["nut_h"] + p["clearance"]
    t = state.width
    if nut_h >= t - 1.0:
        raise RecipeError("nut trap deeper than the plate")
    cx, cy = p["cx"], p["cy"]
    r_hex = af / math.sqrt(3.0)
    hexagon = tuple(
        (cx + r_hex * math.cos(math.radians(30 + 60 * k)),
         cy + r_hex * math.sin(math.radians(30 + 60 * k)))
        for k in range(6)
    )
    state.fields.append(
        FieldFeature(
            plane_z=t, centers=(), cell=af, depth=nut_h,
            pattern="slots", polygons=(hexagon,), min_ligament=0.0,
        )
    )
    state.bores.append(
        BoreFeature(
            name=f"{op_id or 'nut'}_bore", axis="Z", center=(cx, cy, 0.0),
            d=spec["clear"], span=(-0.5, t - nut_h + 0.5), overshoot=(1.0, 1.0),
        )
    )
    state.frame[f"{op_id or 'nut'}_af"] = af


_register(RecipeOpDecl(
    name="nut_trap",
    kind="feature",
    params={
        "screw": ("choice", "M4"), "clearance": ("length", 0.25),
        "cx": ("length", 0.0), "cy": ("length", 0.0),
    },
    validators=("topology.hex_field_present", "topology.bores_open"),
    apply=_nut_trap,
    description="top-access hex nut pocket over a clearance bore",
))


def _wire_exit(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """An open U-notch in a shell's rim for a cable — reaches down from
    the top edge so the wire drops in during assembly."""
    state.require_base("wire_exit")
    f = state.frame
    if "shell_wall" not in f:
        raise RecipeError("wire_exit needs a rounded_box_shell base")
    w = p["cable_d"] + 2.0 * p["clearance"]
    depth = p["cable_d"] + p["drop"]
    h, wall = f["shell_h"], f["shell_wall"]
    off = p["offset"]
    face = p["face"]
    if face in ("+y", "-y"):
        edge = f["outline_v1"] if face == "+y" else f["outline_v0"]
        y0, y1 = (edge - wall - 1.0, edge + 1.0) if face == "+y" else (edge - 1.0, edge + wall + 1.0)
        box = Box3(off - w / 2.0, y0, h - depth, off + w / 2.0, y1, h + 1.0)
    elif face in ("+x", "-x"):
        edge = f["outline_u1"] if face == "+x" else f["outline_u0"]
        x0, x1 = (edge - wall - 1.0, edge + 1.0) if face == "+x" else (edge - 1.0, edge + wall + 1.0)
        box = Box3(x0, off - w / 2.0, h - depth, x1, off + w / 2.0, h + 1.0)
    else:
        raise RecipeError(f"wire_exit face {face!r} not in (+x, -x, +y, -y)")
    state.cutboxes.append(CutBoxFeature(name=op_id or "wire_exit", box=box))


_register(RecipeOpDecl(
    name="wire_exit",
    kind="feature",
    params={
        "cable_d": ("length", 5.0), "clearance": ("length", 0.5),
        "drop": ("length", 3.0), "face": ("choice", "+x"),
        "offset": ("length", 0.0),
    },
    validators=("form.cuts_respect_keepouts", "topology.cutout_present"),
    apply=_wire_exit,
    description="open U-notch through a shell rim for a drop-in cable",
))


def _snap_hook_pair(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Two cantilever snap hooks rising from the plug top at the +-X plug
    edges, lips pointing OUTWARD — the assembly flips the lid and the lips
    click into receiver windows in the box walls. v1 lips are square
    (no insertion ramp): flex the hooks by hand while seating the lid.
    The flexure strain is verified by the snap_joint, not hoped for."""
    state.require_base("snap_hook_pair")
    f = state.frame
    if "plug_u1" not in f:
        raise RecipeError("snap_hook_pair needs an inset_plug first")
    beam_t, hook_w = p["beam_t"], p["hook_w"]
    hook_len, lip_d, lip_h = p["hook_len"], p["lip_d"], p["lip_h"]
    z0 = f["plug_top_z"]
    name = op_id or "snap"
    for i, side in enumerate((-1.0, 1.0)):
        edge = f["plug_u1"] if side > 0 else f["plug_u0"]
        post_x0 = edge - beam_t if side > 0 else edge
        post_x1 = edge if side > 0 else edge + beam_t
        state.ribs.append(RibFeature(
            name=f"{name}_post_{i}",
            box=Box3(post_x0, -hook_w / 2.0, z0 - 0.6,
                     post_x1, hook_w / 2.0, z0 + hook_len),
        ))
        lip_x0 = edge if side > 0 else edge - lip_d
        lip_x1 = edge + lip_d if side > 0 else edge
        state.ribs.append(RibFeature(
            name=f"{name}_lip_{i}",
            box=Box3(lip_x0, -hook_w / 2.0, z0 + hook_len - lip_h,
                     lip_x1, hook_w / 2.0, z0 + hook_len),
        ))
    state.frame.update({
        f"{name}_beam_t": beam_t, f"{name}_hook_len": hook_len,
        f"{name}_lip_d": lip_d, f"{name}_lip_h": lip_h,
        f"{name}_hook_w": hook_w,
    })


_register(RecipeOpDecl(
    name="snap_hook_pair",
    kind="feature",
    params={
        "beam_t": ("length", 1.8), "hook_w": ("length", 8.0),
        "hook_len": ("length", 9.0), "lip_d": ("length", 1.6),
        "lip_h": ("length", 3.0),
    },
    validators=("topology.ribs_present",),
    apply=_snap_hook_pair,
    description="cantilever snap hooks on the plug edges, lips outward",
))


def _snap_window_pair(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Receiver windows through the +-X shell walls for a snap lid.
    ``offset`` shifts the pair along Y so several pairs stack on one shell
    (the vertical farm retainer frame runs four hooks)."""
    state.require_base("snap_window_pair")
    f = state.frame
    if "shell_wall" not in f:
        raise RecipeError("snap_window_pair needs a rounded_box_shell base")
    w_win, h_win, off = p["w"], p["h"], p["top_offset"]
    cy = p["offset"]
    h_shell = f["shell_h"]
    name = op_id or "snap_window"
    for i, (x0, x1) in enumerate((
        (f["outline_u0"] - 1.0, f["outline_u0"] + f["shell_wall"] + 1.0),
        (f["outline_u1"] - f["shell_wall"] - 1.0, f["outline_u1"] + 1.0),
    )):
        state.cutboxes.append(CutBoxFeature(
            name=f"{name}_{i}",
            box=Box3(x0, cy - w_win / 2.0, h_shell - off - h_win,
                     x1, cy + w_win / 2.0, h_shell - off),
        ))
    state.frame[f"{name}_w"] = w_win
    state.frame[f"{name}_h"] = h_win
    state.frame[f"{name}_top_offset"] = off


_register(RecipeOpDecl(
    name="snap_window_pair",
    kind="feature",
    params={
        "w": ("length", 8.8), "h": ("length", 3.8),
        "top_offset": ("length", 6.0), "offset": ("length", 0.0),
    },
    validators=("form.cuts_respect_keepouts", "topology.cutout_present"),
    apply=_snap_window_pair,
    description="through-wall receiver windows on both X walls",
))


def _truss_web_cutouts(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Warren-truss lightening for a flat beam plate: alternating
    triangular cutouts between two solid chords. Struts and chords hold
    their declared thickness BY CONSTRUCTION and the ligament check
    measures the actual polygons — a printed 2D truss, not clip art."""
    from .part import FieldFeature

    state.require_base("truss_web_cutouts")
    f = state.frame
    if "outline_u0" not in f:
        raise RecipeError("truss_web_cutouts needs a rounded_plate base")
    chord, strut = p["chord"], p["strut_t"]
    panels = int(round(p["panels"]))
    margin = p["end_margin"]
    y0, y1 = f["outline_v0"] + chord, f["outline_v1"] - chord
    x0, x1 = f["outline_u0"] + margin, f["outline_u1"] - margin
    if y1 - y0 < 6.0 or panels < 2:
        raise RecipeError("truss web too small for triangles")
    pitch = (x1 - x0) / panels
    s2 = strut / 2.0
    tris: list[tuple[tuple[float, float], ...]] = []
    for i in range(panels):
        a, b = x0 + i * pitch, x0 + (i + 1) * pitch
        if i % 2 == 0:  # apex up
            tris.append((
                (a + s2 * 2.2, y0 + s2), (b - s2 * 2.2, y0 + s2),
                ((a + b) / 2.0, y1 - s2),
            ))
        else:  # apex down
            tris.append((
                (a + s2 * 2.2, y1 - s2), (b - s2 * 2.2, y1 - s2),
                ((a + b) / 2.0, y0 + s2),
            ))
    state.fields.append(FieldFeature(
        plane_z=state.width, centers=(), cell=strut, depth=state.width,
        pattern="slots", polygons=tuple(tris), min_ligament=strut,
    ))
    state.frame[f"{op_id or 'truss'}_panels"] = float(panels)


_register(RecipeOpDecl(
    name="truss_web_cutouts",
    kind="feature",
    params={
        "chord": ("length", 8.0), "strut_t": ("length", 5.0),
        "panels": ("count", 5), "end_margin": ("length", 10.0),
    },
    validators=("form.min_ligament_ok", "topology.hex_field_present"),
    apply=_truss_web_cutouts,
    description="warren-truss triangular lightening between solid chords",
))


