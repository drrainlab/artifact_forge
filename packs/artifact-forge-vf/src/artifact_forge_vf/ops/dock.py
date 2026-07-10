"""Vertical-farm rail edge/dock ops — magnet pockets, endcap dock
pockets, profile seat slot, tongue-groove edges.
"""
from __future__ import annotations

from typing import Any
from artifact_forge_ng.product.archetype import RegionRole
from artifact_forge_ng.form.regions import Box3, Region
from artifact_forge_ng.form.part import BoreFeature, CutBoxFeature, RibFeature
from artifact_forge_ng.form.recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register


# -- edge_magnet_pockets (feature) ---------------------------------------------


def _edge_magnet_pockets(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Optional module-alignment magnets: SEALED dry pockets — blind bores
    into both +-Y faces, in dry body far from every wet zone, leaving a
    plastic floor to the face gap and >= 1.2 wall to any water. Magnets
    align neighbouring modules and NOTHING else: never a seal, never a
    support. No magnet face is ever exposed to water."""
    state.require_base("edge_magnet_pockets")
    f = state.frame
    if "rail_y1" not in f:
        raise RecipeError("edge_magnet_pockets needs a water_rail_body base")
    if not p.get("enabled", False):
        state.frame.update(magnet_count=0)
        return
    # press-fit (VF-4.1): the magnet pushes in from the DRY mating face
    # and stays without a plug; a drop of CA glue is the BOM recommendation
    d = p.get("magnet_d", 6.0) + p.get("fit_clearance", 0.2)
    depth = p.get("magnet_t", 2.0) + 0.4
    x_off, z_c = p.get("x_offset", 60.0), p.get("z_center", 8.0)
    name = op_id or "magnets"
    count = 0
    for face_label, face_y, sign in (("in", f["rail_y1"], 1.0), ("out", f["rail_y0"], -1.0)):
        for x_label, x in (("e", x_off), ("w", -x_off)):
            span = (face_y - depth, face_y) if sign > 0 else (face_y, face_y + depth)
            overshoot = (0.0, 1.0) if sign > 0 else (1.0, 0.0)
            state.bores.append(BoreFeature(
                name=f"{name}_pocket_{face_label}_{x_label}", axis="Y",
                center=(x, 0.0, z_c), d=d, span=span, overshoot=overshoot,
            ))
            state.regions.append(Region(
                f"module_magnet_pocket_{face_label}_{x_label}",
                RegionRole.INTERFACE_KEEPOUT,
                Box3(x - d / 2.0 - 1.0, min(span) - 1.0, z_c - d / 2.0 - 1.0,
                     x + d / 2.0 + 1.0, max(span) + 1.0, z_c + d / 2.0 + 1.0)))
            count += 1
    state.frame.update(
        magnet_count=count, magnet_pocket_d=d, magnet_pocket_depth=depth,
        magnet_x_offset=x_off, magnet_z=z_c,
        magnet_fit_clearance=d - p.get("magnet_d", 6.0),
        magnet_d_nominal=p.get("magnet_d", 6.0),
    )


_register(RecipeOpDecl(
    name="edge_magnet_pockets",
    kind="feature",
    params={
        "enabled": ("bool", False),
        "magnet_d": ("length", 6.0), "magnet_t": ("length", 2.0),
        "fit_clearance": ("length", 0.2),
        "x_offset": ("length", 60.0), "z_center": ("length", 8.0),
    },
    validators=(
        "form.magnet_pockets_outside_water_zone",
        "form.magnet_pockets_do_not_break_wall",
    ),
    apply=_edge_magnet_pockets,
    description="optional sealed dry magnet pockets in both +-Y faces — "
                "module alignment only, never a seal, never a support",
))


# -- endcap_dock_pockets (feature) --------------------------------------------


def _endcap_dock_pockets(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Endcap docking magnets (VF-6): the terminal module's END faces have no
    neighbour, so their module magnets go to waste. Instead the row END wall
    TOP carries a pair of UP-facing Z pockets that the collector (front) or
    inlet cap (back) arm docks onto — arm underside sits flat on the wall top
    at the module height, magnet to magnet, alignment-only. The pockets live
    in the dry perimeter END wall (x = +-dock_x, inboard of the seat, far
    from channel and root troughs); they open UP and print supportless."""
    state.require_base("endcap_dock_pockets")
    f = state.frame
    if "rail_y1" not in f:
        raise RecipeError("endcap_dock_pockets needs a water_rail_body base")
    end = p.get("dock_end", "none")
    if end == "none":
        state.frame.update(dock_pocket_count=0)
        return
    if end not in ("front", "back", "both"):
        raise RecipeError(f"dock_end {end!r} not in none|front|back|both")
    style = p.get("dock_style", "top")
    if style not in ("top", "face"):
        raise RecipeError(f"dock_style {style!r} not in top|face")
    d = p.get("magnet_d", 6.0) + p.get("fit_clearance", 0.2)
    depth = p.get("magnet_t", 2.0) + 0.4
    dock_x = p.get("dock_x", 22.0)
    inset = p.get("dock_inset", 7.0)
    z_top = f["body_h"]
    # face dock height: a common DROP below the wall top so the cap (which
    # measures from its own frame) and the rail land at the same world z.
    face_z = z_top - p.get("dock_drop", 4.0)
    # front = outlet face (rail_y0, -Y, collector); back = inlet (rail_y1, cap)
    ends = {
        "front": [("f", f["rail_y0"], 1.0)],
        "back": [("b", f["rail_y1"], -1.0)],
        "both": [("f", f["rail_y0"], 1.0), ("b", f["rail_y1"], -1.0)],
    }[end]
    name = op_id or "dock"
    count = 0
    for tag, face_y, inward in ends:
        for x_label, x in (("e", dock_x), ("w", -dock_x)):
            if style == "face":
                # VF-9 Part B: Y-axis pocket in the END FACE, bored inward from
                # the face (mouth opens outward) — the cap's +Y-face hook magnet
                # docks here. Vertical face → prints support-free; blind (dry).
                if inward < 0:   # back (+Y) face
                    lo, hi, ov = face_y - depth, face_y, (0.0, 1.0)
                else:            # front (-Y) face
                    lo, hi, ov = face_y, face_y + depth, (1.0, 0.0)
                state.bores.append(BoreFeature(
                    name=f"{name}_{tag}_{x_label}", axis="Y",
                    center=(x, 0.0, face_z), d=d, span=(lo, hi), overshoot=ov,
                ))
                state.regions.append(Region(
                    f"endcap_dock_{tag}_{x_label}", RegionRole.INTERFACE_KEEPOUT,
                    Box3(x - d / 2.0 - 1.0, lo - 1.0, face_z - d / 2.0 - 1.0,
                         x + d / 2.0 + 1.0, hi + 1.0, face_z + d / 2.0 + 1.0)))
            else:
                dock_y = face_y + inward * inset  # step inboard off the end face
                state.bores.append(BoreFeature(
                    name=f"{name}_{tag}_{x_label}", axis="Z",
                    center=(x, dock_y, 0.0), d=d,
                    span=(z_top - depth, z_top), overshoot=(0.0, 1.0),
                ))
                state.regions.append(Region(
                    f"endcap_dock_{tag}_{x_label}", RegionRole.INTERFACE_KEEPOUT,
                    Box3(x - d / 2.0 - 1.0, dock_y - d / 2.0 - 1.0, z_top - depth - 1.0,
                         x + d / 2.0 + 1.0, dock_y + d / 2.0 + 1.0, z_top + 1.0)))
            count += 1
    state.frame.update(
        dock_pocket_count=count, dock_pocket_d=d, dock_pocket_depth=depth,
        dock_x=dock_x, dock_inset=inset, dock_z_plane=z_top,
        dock_style_face=1.0 if style == "face" else 0.0, dock_face_z=face_z,
        dock_front=1.0 if end in ("front", "both") else 0.0,
        dock_back=1.0 if end in ("back", "both") else 0.0,
        dock_fit_clearance=d - p.get("magnet_d", 6.0),
    )


_register(RecipeOpDecl(
    name="endcap_dock_pockets",
    kind="feature",
    params={
        "dock_end": ("choice", "none"), "dock_style": ("choice", "top"),
        "magnet_d": ("length", 6.0), "magnet_t": ("length", 2.0),
        "fit_clearance": ("length", 0.2),
        "dock_x": ("length", 22.0), "dock_inset": ("length", 7.0),
        "dock_drop": ("length", 4.0),
    },
    validators=(
        "form.dock_pockets_dry",
    ),
    apply=_endcap_dock_pockets,
    description="optional dock magnets on a terminal module END — style: top "
                "(UP Z pockets on the wall top, collector) or face (Y pockets "
                "in the +/-Y end face, VF-9 cap); alignment-only, dry, "
                "supportless",
))


# -- profile_seat_slot (feature) ----------------------------------------------


def _profile_seat_slot(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Top-drop-in seating on two aluminum profile rails running along the
    flow axis under the +-X edges — far from the water by construction,
    removable by lifting."""
    state.require_base("profile_seat_slot")
    f = state.frame
    if "seat_floor_z" not in f:
        raise RecipeError("profile_seat_slot needs a water_rail_body base")
    size = 20.0 if p["profile"] == "2020" else 30.0
    clearance, depth, inset = p["clearance"], p["depth"], p["inset"]
    if depth > f["seat_floor_z"] - 2.0:
        raise RecipeError(
            f"profile slot depth {depth:g} undercuts the seat floor at "
            f"{f['seat_floor_z']:g}")
    slot_w = size + 2.0 * clearance
    name = op_id or "profile"
    for label, sign in (("e", 1.0), ("w", -1.0)):
        cx = sign * (f["rail_x1"] - inset)
        box = Box3(cx - slot_w / 2.0, f["rail_y0"] - 1.0, -1.0,
                   cx + slot_w / 2.0, f["rail_y1"] + 1.0, depth)
        state.cutboxes.append(CutBoxFeature(name=f"{name}_slot_{label}", box=box))
        state.regions.append(Region(
            f"profile_seat_{label}", RegionRole.INTERFACE_KEEPOUT, box))
    state.frame.update(
        profile_size=size, profile_slot_w=slot_w,
        profile_slot_clearance=clearance, profile_slot_depth=depth,
        profile_slot_x=f["rail_x1"] - inset,
    )
    # Seat datums (VF-4): the point where the groove CEILING rests on the
    # profile's sloped support line — at the groove's UPSTREAM (+Y) edge,
    # where a flat groove meets a falling line first. 0.5 in from the face:
    # any deeper and the rising support line would wedge into the ceiling
    # upstream of the contact (a real interference, not a modeling nit).
    edge_y = f["rail_y1"] - 0.5
    state.datums["seat_e"] = {
        "at": [f["rail_x1"] - inset, edge_y, depth], "rotate": [0.0, 0.0, 0.0]}
    state.datums["seat_w"] = {
        "at": [-(f["rail_x1"] - inset), edge_y, depth], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="profile_seat_slot",
    kind="feature",
    params={
        "profile": ("choice", "2020"), "clearance": ("length", 0.2),
        "depth": ("length", 6.0), "inset": ("length", 24.0),
    },
    validators=("form.profile_seat_dry_ok", "topology.cutout_present"),
    apply=_profile_seat_slot,
    description="bottom slots seating the module onto 2020/3030 aluminum "
                "rails, tool-free, outside the water path",
))


# -- tongue_groove_edges (feature) ----------------------------------------------


def _tongue_groove_edges(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Module-to-module line alignment: a tongue rib on the +X edge, a
    groove notch in the -X edge. Alignment only — the tongue never bottoms
    (non-load-bearing) and nothing seals."""
    state.require_base("tongue_groove_edges")
    f = state.frame
    if "rail_x1" not in f:
        raise RecipeError("tongue_groove_edges needs a water_rail_body base")
    t_w, t_h, t_len = p["tongue_w"], p["tongue_h"], p["tongue_len"]
    clearance, z0 = p["clearance"], p["z0"]
    groove_w = t_w + 2.0 * clearance
    groove_depth = t_len + p["bottom_margin"] + (f["module_pitch"] - (f["rail_x1"] - f["rail_x0"]))
    name = op_id or "edges"
    tongue = Box3(f["rail_x1"] - 0.6, -t_w / 2.0, z0,
                  f["rail_x1"] + t_len, t_w / 2.0, z0 + t_h)
    groove = Box3(f["rail_x0"] - 1.0, -groove_w / 2.0, z0 - clearance,
                  f["rail_x0"] + groove_depth, groove_w / 2.0, z0 + t_h + clearance)
    state.ribs.append(RibFeature(name=f"{name}_tongue", box=tongue))
    state.cutboxes.append(CutBoxFeature(name=f"{name}_groove", box=groove))
    state.regions.extend([
        Region("tongue_edge", RegionRole.INTERFACE_KEEPOUT, tongue),
        Region("groove_edge", RegionRole.INTERFACE_KEEPOUT, groove),
    ])
    state.frame.update(
        tongue_w=t_w, tongue_h=t_h, tongue_len=t_len,
        groove_w=groove_w, groove_depth=groove_depth,
        edge_clearance=clearance,
        tongue_cy=0.0, groove_cy=0.0, tongue_z0=z0, groove_z0=z0,
    )


_register(RecipeOpDecl(
    name="tongue_groove_edges",
    kind="feature",
    params={
        "tongue_w": ("length", 6.0), "tongue_h": ("length", 4.0),
        "tongue_len": ("length", 3.6), "clearance": ("length", 0.4),
        "z0": ("length", 4.0), "bottom_margin": ("length", 0.4),
    },
    validators=(
        "form.tongue_groove_profile_ok", "topology.ribs_present",
        "topology.cutout_present",
    ),
    apply=_tongue_groove_edges,
    description="tongue (+X) / groove (-X) line-alignment edges, "
                "non-bearing, non-sealing",
))


