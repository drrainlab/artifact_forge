"""Dovetail adapter body op.

NOTE: registers AFTER the water ops to preserve the original RECIPE_OPS
insertion order; semantically core.
"""
from __future__ import annotations

from typing import Any
from .regions import Box3, Region
from ..product.archetype import RegionRole
from .part import BoreFeature
from .recipe_ops_core import RecipeError, RecipeState, RecipeOpDecl, _register




def _dovetail_adapter_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Payload adapter (wave A1): male dovetail foot sliding into the cuff
    socket along the arm axis, carrying a snap-C clip or a flat accessory
    plate. Axial retention is friction-only in v1 (a cold-shoe reality,
    stated, not hidden) — an end stop is a future op."""
    from .profiles_wearable import AdapterParams, build_dovetail_adapter_profile

    if state.section is not None:
        raise RecipeError("dovetail_adapter_body must be the (single) base op")
    ap = AdapterParams(
        head=p["head"], groove_top_w=p["groove_top_w"],
        groove_bottom_w=p["groove_bottom_w"], groove_depth=p["groove_depth"],
        fit_clearance=p["fit_clearance"], base_w=p["base_w"],
        base_t=p["base_t"], payload_d=p["payload_d"],
        payload_clearance=p["payload_clearance"],
        payload_arc_deg=p["payload_arc_deg"], clip_wall=p["clip_wall"],
        neck_drop=p["neck_drop"], plate_w=p["plate_w"],
        hole_span=p["hole_span"], corner_r=p["corner_r"],
    )
    try:
        profile, f = build_dovetail_adapter_profile(ap)
    except ValueError as exc:
        raise RecipeError(f"dovetail_adapter_body: {exc}") from exc
    w = p["adapter_l"]
    state.section = profile
    state.width = w
    state.kind = "section_extrude"
    state.print_orientation = "side_profile"
    state.frame.update(f)
    bw2 = f["base_w"] / 2.0
    state.frame.update(
        outline_u0=0.0, outline_v0=-bw2, outline_u1=w, outline_v1=bw2,
        outline_corner_r=0.0,
    )
    state.regions.append(
        Region("foot_interface", RegionRole.INTERFACE_KEEPOUT,
               Box3(0.0, -f["dovetail_top_w"] / 2.0, 0.0,
                    w, f["dovetail_top_w"] / 2.0, f["foot_plane_v"])),
    )
    state.datums["mount_foot"] = {
        "at": [w / 2.0, 0.0, f["foot_plane_v"]], "rotate": [0.0, 0.0, 0.0],
    }
    if ap.head == "snap_clip":
        state.regions.extend([
            Region("payload_saddle", RegionRole.SOFT_CONTACT_SURFACE,
                   Box3(0.0, -f["payload_r_inner"],
                        f["payload_cv"] - f["payload_r_inner"],
                        w, f["payload_r_inner"],
                        f["payload_cv"] + f["payload_r_inner"])),
        ])
        state.datums["payload_axis"] = {
            "at": [w / 2.0, 0.0, f["payload_cv"]], "rotate": [0.0, 0.0, 0.0],
        }
    else:
        # accessory plate: two vertical through-bores on the hole span
        for i, uy in enumerate((-p["hole_span"] / 2.0, p["hole_span"] / 2.0)):
            state.bores.append(BoreFeature(
                f"{op_id or 'plate'}_hole_{i}", "Z", (w / 2.0, uy, 0.0),
                p["hole_d"], (f["foot_plane_v"] - 1.0, f["base_top_v"] + 1.0),
            ))
        state.regions.append(
            Region("accessory_plate", RegionRole.MOUNTING_SURFACE,
                   Box3(0.0, -bw2, f["foot_plane_v"], w, bw2,
                        f["base_top_v"])),
        )
        state.datums["plate_top"] = {
            "at": [w / 2.0, 0.0, f["base_top_v"]], "rotate": [0.0, 0.0, 0.0],
        }


_register(RecipeOpDecl(
    name="dovetail_adapter_body",
    kind="base",
    params={
        "head": ("choice", "snap_clip"), "adapter_l": ("length", None),
        "groove_top_w": ("length", 12.0),
        "groove_bottom_w": ("length", 17.0),
        "groove_depth": ("length", 6.0), "fit_clearance": ("length", 0.25),
        "base_w": ("length", 30.0), "base_t": ("length", 4.0),
        "payload_d": ("length", 25.0), "payload_clearance": ("length", 0.3),
        "payload_arc_deg": ("angle", 240.0), "clip_wall": ("length", 3.0),
        "neck_drop": ("length", 4.0), "plate_w": ("length", 40.0),
        "hole_span": ("length", 20.0), "hole_d": ("length", 4.5),
        "corner_r": ("length", 2.0),
    },
    validators=(
        "form.dovetail_foot_profile_ok",
        "topology.single_connected_solid",
    ),
    apply=_dovetail_adapter_body,
    description="payload adapter: male dovetail foot + snap-C clip or "
                "accessory plate (slides on the cuff socket along X)",
))
