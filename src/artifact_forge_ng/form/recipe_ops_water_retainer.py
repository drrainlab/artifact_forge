"""Vertical-farm retainer frame ops — frame body, snap hooks.
"""
from __future__ import annotations

from typing import Any
from ..product.archetype import RegionRole
from .profiles_plate import rounded_rect_loop
from .regions import Box3, Region
from .section import SectionProfile
from .part import CutBoxFeature, RibFeature
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register


# -- retainer_frame_body (base) -----------------------------------------------


def _retainer_frame_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The Snap Retainer Frame: a flat rounded ring plate — a band wide
    enough to hold the coco mat down lightly, an opening big enough to
    let the greens through."""
    if state.section is not None:
        raise RecipeError("retainer_frame_body must be the (single) base op")
    l, w, t = p["l"], p["w"], p["t"]
    band = p["band_w"]
    if 2.0 * band + 20.0 >= min(l, w):
        raise RecipeError("frame band leaves no opening for the greens")
    u0, v0, u1, v1 = -l / 2.0, -w / 2.0, l / 2.0, w / 2.0
    state.section = SectionProfile(
        name="recipe", outer=rounded_rect_loop(u0, v0, u1, v1, p["corner_r"]),
        plane="XY", width_axis="Z",
    )
    state.width = t
    name = op_id or "frame"
    state.cutboxes.append(CutBoxFeature(
        name=f"{name}_opening",
        box=Box3(u0 + band, v0 + band, -1.0, u1 - band, v1 - band, t + 1.0),
    ))
    state.regions.append(Region(
        "frame_band", RegionRole.MOUNTING_SURFACE, Box3(u0, v0, 0.0, u1, v1, t)))
    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=p["corner_r"], frame_band_w=band, frame_t=t,
    )
    # The seat datum sits on the plate TOP (hook side): the assembly flips
    # the frame 180 about X onto the cassette rim, so the plate lands ABOVE
    # the rim plane and the hooks descend inside the walls.
    state.datums["seat"] = {"at": [0.0, 0.0, t], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="retainer_frame_body",
    kind="base",
    params={
        "l": ("length", None), "w": ("length", None), "t": ("length", 3.0),
        "band_w": ("length", 10.0), "corner_r": ("length", 3.0),
    },
    validators=("topology.cutout_present", "topology.single_connected_solid"),
    apply=_retainer_frame_body,
    description="flat ring plate holding the substrate down lightly",
))


# -- frame_snap_hooks (feature) -------------------------------------------------


def _frame_snap_hooks(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Four cantilever hooks rising from the frame plate at the +-X edges
    (two per side, spaced along Y), lips outward — the assembly flips the
    frame onto the cassette rim and the lips click into the cassette's
    snap windows. Light retention: strain is verified by the snap joint."""
    state.require_base("frame_snap_hooks")
    f = state.frame
    if "frame_t" not in f:
        raise RecipeError("frame_snap_hooks needs a retainer_frame_body base")
    beam_t, hook_w = p["beam_t"], p["hook_w"]
    hook_len, lip_d, lip_h = p["hook_len"], p["lip_d"], p["lip_h"]
    span, sy = p["hook_span"], p["sy"]
    t = f["frame_t"]
    name = op_id or "snap"
    i = 0
    for side in (-1.0, 1.0):
        edge = side * span / 2.0
        post_x0, post_x1 = (edge - beam_t, edge) if side > 0 else (edge, edge + beam_t)
        lip_x0, lip_x1 = (edge, edge + lip_d) if side > 0 else (edge - lip_d, edge)
        for cy in (-sy / 2.0, sy / 2.0):
            state.ribs.append(RibFeature(
                name=f"{name}_post_{i}",
                box=Box3(post_x0, cy - hook_w / 2.0, t - 0.6,
                         post_x1, cy + hook_w / 2.0, t + hook_len),
            ))
            state.ribs.append(RibFeature(
                name=f"{name}_lip_{i}",
                box=Box3(lip_x0, cy - hook_w / 2.0, t + hook_len - lip_h,
                         lip_x1, cy + hook_w / 2.0, t + hook_len),
            ))
            state.regions.append(Region(
                f"snap_root_{i}", RegionRole.HIGH_STRESS_REGION,
                Box3(post_x0 - 1.0, cy - hook_w / 2.0 - 1.0, t - 1.0,
                     post_x1 + 1.0, cy + hook_w / 2.0 + 1.0, t + 3.0),
            ))
            i += 1
    state.frame.update({
        f"{name}_beam_t": beam_t, f"{name}_hook_len": hook_len,
        f"{name}_lip_d": lip_d, f"{name}_lip_h": lip_h,
        f"{name}_hook_w": hook_w, f"{name}_span": span, f"{name}_sy": sy,
    })


_register(RecipeOpDecl(
    name="frame_snap_hooks",
    kind="feature",
    params={
        "beam_t": ("length", 1.6), "hook_w": ("length", 8.0),
        "hook_len": ("length", 9.0), "lip_d": ("length", 1.4),
        "lip_h": ("length", 3.0),
        "hook_span": ("length", None), "sy": ("length", 120.0),
    },
    validators=("topology.ribs_present",),
    apply=_frame_snap_hooks,
    description="four light cantilever hooks (two per X side), lips outward",
))


