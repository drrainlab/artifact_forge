"""Base and feature recipe ops — plates, box shells, bosses, ports,
bearing seats, hole patterns, cutouts.
"""
from __future__ import annotations

from typing import Any
from ..core.fasteners import screw_spec
from .patterns import bolt_circle_centers, grid_centers, holes_from_centers, line_centers
from .profiles_plate import rounded_rect_loop
from .regions import Box3, Region
from .section import SectionProfile
from ..product.archetype import RegionRole
from .part import BoreFeature, CutBoxFeature, HoleFeature, RibFeature
from .recipe_ops_core import KEEPOUT_CLEARANCE, PORT_SIZES, BEARINGS, RecipeError, RecipeState, RecipeOpDecl, _register


# -- base ---------------------------------------------------------------------


def _rounded_plate(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    if state.section is not None:
        raise RecipeError("rounded_plate must be the (single) base op")
    l, w, t, r = p["l"], p["w"], p["t"], p["corner_r"]
    u0, v0, u1, v1 = -l / 2.0, -w / 2.0, l / 2.0, w / 2.0
    state.section = SectionProfile(
        name="recipe", outer=rounded_rect_loop(u0, v0, u1, v1, r),
        plane="XY", width_axis="Z",
    )
    state.width = t
    name = op_id or "plate"
    state.regions.append(
        Region(name, RegionRole.MOUNTING_SURFACE, Box3(u0, v0, 0.0, u1, v1, t))
    )
    # Every plate is also a lightening canvas: field modifiers target this
    # region and the protected regions/prior cuts become keepouts.
    state.regions.append(
        Region(f"{name}_lightening", RegionRole.AESTHETIC_LIGHTENING,
               Box3(u0 + 4.0, v0 + 4.0, 0.0, u1 - 4.0, v1 - 4.0, t))
    )
    # The standard outline frame the hole checks measure against.
    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=r, plate_t=t,
    )


_register(RecipeOpDecl(
    name="rounded_plate",
    kind="base",
    params={
        "l": ("length", None), "w": ("length", None), "t": ("length", None),
        "corner_r": ("length", 3.0),
    },
    validators=("form.holes_within_outline",),
    apply=_rounded_plate,
    description="rounded-rect plate; the plate IS the section (XY, extruded by t)",
))


def _rounded_box_shell(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Open-top box: outer rounded rect extruded to full height, interior
    cut from the floor up. Inner corners are square in v1 — honest scope."""
    if state.section is not None:
        raise RecipeError("rounded_box_shell must be the (single) base op")
    l, w, h = p["l"], p["w"], p["h"]
    wall, floor_t, r = p["wall"], p["floor_t"], p["corner_r"]
    if 2.0 * wall + 4.0 >= min(l, w) or floor_t + 2.0 >= h:
        raise RecipeError("box shell walls/floor leave no interior")
    u0, v0, u1, v1 = -l / 2.0, -w / 2.0, l / 2.0, w / 2.0
    state.section = SectionProfile(
        name="recipe", outer=rounded_rect_loop(u0, v0, u1, v1, r),
        plane="XY", width_axis="Z",
    )
    state.width = h
    name = op_id or "shell"
    state.cutboxes.append(
        CutBoxFeature(
            name=f"{name}_interior",
            box=Box3(u0 + wall, v0 + wall, floor_t, u1 - wall, v1 - wall, h + 1.0),
        )
    )
    state.regions.extend([
        Region("floor", RegionRole.AESTHETIC_LIGHTENING,
               Box3(u0 + wall, v0 + wall, 0.0, u1 - wall, v1 - wall, floor_t)),
        Region(name, RegionRole.MOUNTING_SURFACE, Box3(u0, v0, 0.0, u1, v1, h)),
    ])
    state.frame.update(
        outline_u0=u0, outline_v0=v0, outline_u1=u1, outline_v1=v1,
        outline_corner_r=r,
        inner_u0=u0 + wall, inner_v0=v0 + wall,
        inner_u1=u1 - wall, inner_v1=v1 - wall,
        shell_wall=wall, floor_t=floor_t, shell_h=h,
    )
    # The rim center — what a lid's `seat` datum mates against.
    state.datums["rim"] = {"at": [0.0, 0.0, h], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="rounded_box_shell",
    kind="base",
    params={
        "l": ("length", None), "w": ("length", None), "h": ("length", None),
        "wall": ("length", 2.4), "floor_t": ("length", 3.0),
        "corner_r": ("length", 5.0),
    },
    validators=("form.shell_walls_ok", "topology.cutout_present"),
    apply=_rounded_box_shell,
    description="open-top enclosure shell (outer body + interior cavity cut)",
))


def _boss_pattern(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Screw bosses rising from the shell floor with blind pilot bores
    (self-tap or heatset). Square bosses in v1 (RibFeature machinery);
    the floor-slab keepout regions protect them from lightening fields."""
    state.require_base("boss_pattern")
    floor_t = state.frame.get("floor_t")
    if floor_t is None:
        raise RecipeError("boss_pattern needs a rounded_box_shell base (floor_t)")
    sx, sy = p["sx"] / 2.0, p["sy"] / 2.0
    cx, cy = p["cx"], p["cy"]
    boss, height = p["boss"], p["height"]
    pilot_d, pilot_depth = p["pilot_d"], p["pilot_depth"]
    if pilot_depth >= height + floor_t - 0.8:
        raise RecipeError("pilot bore would pierce the floor under the boss")
    name = op_id or "bosses"
    top = floor_t + height
    for i, (bx, by) in enumerate(
        [(cx - sx, cy - sy), (cx + sx, cy - sy), (cx + sx, cy + sy), (cx - sx, cy + sy)]
    ):
        state.ribs.append(
            RibFeature(
                name=f"{name}_{i}",
                box=Box3(bx - boss / 2.0, by - boss / 2.0, floor_t - 0.6,
                         bx + boss / 2.0, by + boss / 2.0, top),
            )
        )
        state.bores.append(
            BoreFeature(
                name=f"{name}_pilot_{i}", axis="Z", center=(bx, by, 0.0),
                d=pilot_d, span=(top - pilot_depth, top), overshoot=(0.0, 1.0),
            )
        )
        # Keepout lives in the FLOOR slab only, so the boss's own pilot
        # (entirely above the floor) never trips cuts_respect_keepouts.
        state.regions.append(
            Region(f"{name}_keep_{i}", RegionRole.FASTENER_KEEPOUT,
                   Box3(bx - boss / 2.0 - KEEPOUT_CLEARANCE,
                        by - boss / 2.0 - KEEPOUT_CLEARANCE, 0.0,
                        bx + boss / 2.0 + KEEPOUT_CLEARANCE,
                        by + boss / 2.0 + KEEPOUT_CLEARANCE, floor_t))
        )
        state.frame[f"{name}_{i}_x"] = bx
        state.frame[f"{name}_{i}_y"] = by
    state.frame[f"{name}_top"] = top


_register(RecipeOpDecl(
    name="boss_pattern",
    kind="feature",
    params={
        "sx": ("length", None), "sy": ("length", None),
        "cx": ("length", 0.0), "cy": ("length", 0.0),
        "boss": ("length", 7.0), "height": ("length", 6.0),
        "pilot_d": ("length", 4.0), "pilot_depth": ("length", 5.0),
    },
    validators=("topology.ribs_present", "topology.pockets_present"),
    apply=_boss_pattern,
    description="4 corner screw bosses with blind pilot bores (heatset/self-tap)",
))


def _port_cutout(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A device-jack opening through one shell wall, sized from the port
    table plus clearance."""
    state.require_base("port_cutout")
    f = state.frame
    if "shell_wall" not in f:
        raise RecipeError("port_cutout needs a rounded_box_shell base")
    port = p["port"]
    if port not in PORT_SIZES:
        raise RecipeError(f"unknown port {port!r}; known: {sorted(PORT_SIZES)}")
    w, h = (s + 2.0 * p["clearance"] for s in PORT_SIZES[port])
    off, z = p["offset"], p["z"]
    wall = f["shell_wall"]
    face = p["face"]
    if face in ("+y", "-y"):
        edge = f["outline_v1"] if face == "+y" else f["outline_v0"]
        y0, y1 = (edge - wall - 1.0, edge + 1.0) if face == "+y" else (edge - 1.0, edge + wall + 1.0)
        box = Box3(off - w / 2.0, y0, z - h / 2.0, off + w / 2.0, y1, z + h / 2.0)
    elif face in ("+x", "-x"):
        edge = f["outline_u1"] if face == "+x" else f["outline_u0"]
        x0, x1 = (edge - wall - 1.0, edge + 1.0) if face == "+x" else (edge - 1.0, edge + wall + 1.0)
        box = Box3(x0, off - w / 2.0, z - h / 2.0, x1, off + w / 2.0, z + h / 2.0)
    else:
        raise RecipeError(f"port face {face!r} not in (+x, -x, +y, -y)")
    state.cutboxes.append(CutBoxFeature(name=op_id or f"port_{port}", box=box))


_register(RecipeOpDecl(
    name="port_cutout",
    kind="feature",
    params={
        "port": ("choice", "usb_c"), "face": ("choice", "+y"),
        "offset": ("length", 0.0), "z": ("length", None),
        "clearance": ("length", 0.4),
    },
    validators=("form.cuts_respect_keepouts", "topology.cutout_present"),
    apply=_port_cutout,
    description="through-wall opening for a standard device jack",
))


def _bearing_seat(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Press/slip seat for a standard ball bearing: a pocket the bearing
    drops into from the top face, over a smaller through bore whose rim is
    the retaining lip the outer race sits on."""
    state.require_base("bearing_seat")
    des = p["bearing"]
    if des not in BEARINGS:
        raise RecipeError(f"unknown bearing {des!r}; known: {sorted(BEARINGS)}")
    od, bw, bore_d = BEARINGS[des]
    fit_delta = {"press": 0.0, "slip": 0.15}.get(p["fit"])
    if fit_delta is None:
        raise RecipeError(f"fit {p['fit']!r} not in (press, slip)")
    t = state.width
    if bw + 1.5 >= t:
        raise RecipeError(f"plate {t:g} too thin to seat a {des} ({bw:g} wide)")
    cx, cy = p["cx"], p["cy"]
    seat_d = od + fit_delta
    lip_inner_d = od - 2.0 * p["lip_w"]
    if lip_inner_d <= bore_d + 1.0:
        raise RecipeError("retaining lip would cover the inner race")
    name = op_id or f"seat_{des}"
    # Both cuts declared with open overshoots: the pocket opens into the
    # through bore (no false 'blind skin' expectations), and both voids are
    # probe-verified by bores_open; the lip ring gets its own probe. The
    # pocket span is INSET by the overshoot so the cutter's actual extent
    # (span grown by overshoot on each end) lands exactly on t-bw..t —
    # an overshooting cutter must never nibble the lip it seats on.
    state.bores.append(
        BoreFeature(name=f"{name}_pocket", axis="Z", center=(cx, cy, 0.0),
                    d=seat_d, span=(t - bw + 1.0, t), overshoot=(1.0, 1.0))
    )
    state.bores.append(
        BoreFeature(name=f"{name}_through", axis="Z", center=(cx, cy, 0.0),
                    d=lip_inner_d, span=(-0.5, t - bw + 0.5), overshoot=(1.0, 1.0))
    )
    # No explicit keepout region: the seat's own bores would trip
    # cuts_respect_keepouts against it. Field modifiers are still safe —
    # derive_keepouts turns every Z-bore into a circular keepout.
    state.frame.update({
        f"{name}_cx": cx, f"{name}_cy": cy,
        f"{name}_lip_r": (seat_d / 2.0 + lip_inner_d / 2.0) / 2.0,
        f"{name}_lip_z0": 0.0, f"{name}_lip_z1": t - bw,
        "bearing_seat_count": state.frame.get("bearing_seat_count", 0.0) + 1.0,
    })


_register(RecipeOpDecl(
    name="bearing_seat",
    kind="feature",
    params={
        "bearing": ("choice", "608"), "fit": ("choice", "press"),
        "cx": ("length", 0.0), "cy": ("length", 0.0),
        "lip_w": ("length", 1.5),
    },
    validators=("topology.bores_open", "topology.seat_lips_present"),
    apply=_bearing_seat,
    description="pocket + through bore + retaining lip for a standard bearing",
))


# -- features -----------------------------------------------------------------


def _hole_pattern(
    state: RecipeState, p: dict[str, Any], op_id: str, *, countersunk: bool,
    counterbore: bool = False,
) -> None:
    state.require_base("hole_pattern")
    kind = p["kind"]
    center = (p["cx"], p["cy"])
    count = int(round(p["count"]))
    if kind == "line":
        centers = line_centers(count, p["spacing"], center)
    elif kind == "bolt_circle":
        centers = bolt_circle_centers(count, p["bc_d"], center)
    else:
        raise RecipeError(f"hole pattern kind {kind!r} not in (line, bolt_circle)")
    screw = p["screw"]
    t = state.width
    # A stacked part (lid plate + welded plug) needs holes cut from the
    # STACK top through everything — z_top/through of 0 mean "the base".
    z_top = p["z_top"] if p["z_top"] > 1e-9 else t
    through = p["through"] if p["through"] > 1e-9 else z_top
    holes = holes_from_centers(centers, z_top, through, screw, p["cs_face"])
    if counterbore:
        holes = [
            HoleFeature(at=h.at, screw=h.screw, through=h.through,
                        countersink_face=h.countersink_face,
                        head_style="cylinder")
            for h in holes
        ]
    elif not countersunk:
        holes = [
            HoleFeature(at=h.at, screw=h.screw, through=h.through, countersink=False)
            for h in holes
        ]
    state.holes.extend(holes)
    head_r = screw_spec(screw)["head"] / 2.0
    name = op_id or "holes"
    for i, (hx, hy) in enumerate(centers):
        # Keepout spans the HOLE's z-extent, not the whole part — floor
        # screws in a box must not veto the interior cavity above them.
        state.regions.append(
            Region(
                f"{name}_{i}", RegionRole.FASTENER_KEEPOUT,
                Box3(hx - head_r - KEEPOUT_CLEARANCE, hy - head_r - KEEPOUT_CLEARANCE,
                     z_top - through,
                     hx + head_r + KEEPOUT_CLEARANCE, hy + head_r + KEEPOUT_CLEARANCE,
                     z_top),
            )
        )
        state.frame[f"{name}_{i}_x"] = hx
        state.frame[f"{name}_{i}_y"] = hy
    state.frame["screw_head_r"] = head_r


_HOLE_PARAMS: dict[str, tuple[str, Any]] = {
    "kind": ("choice", "line"),
    "screw": ("choice", "M4"),
    "count": ("count", 2),
    "spacing": ("length", 30.0),
    "bc_d": ("length", 40.0),
    "cx": ("length", 0.0),
    "cy": ("length", 0.0),
    "cs_face": ("choice", "top"),
    "z_top": ("length", 0.0),
    "through": ("length", 0.0),
}

_register(RecipeOpDecl(
    name="hole_pattern",
    kind="feature",
    params=_HOLE_PARAMS,
    validators=(
        "form.min_web_between_holes",
        "form.holes_within_outline",
        "topology.screw_holes_open",
    ),
    apply=lambda s, p, i: _hole_pattern(s, p, i, countersunk=False),
    description="plain clearance holes (line / bolt circle)",
))

_register(RecipeOpDecl(
    name="countersunk_hole_pattern",
    kind="feature",
    params=_HOLE_PARAMS,
    validators=(
        "form.min_web_between_holes",
        "form.holes_within_outline",
        "topology.screw_holes_open",
        "topology.countersinks_present",
    ),
    apply=lambda s, p, i: _hole_pattern(s, p, i, countersunk=True),
    description="countersunk fastener holes; cs_face names where the head seats",
))


def _rounded_rect_cutout(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    state.require_base("rounded_rect_cutout")
    w, h = p["w"], p["h"]
    cx, cy = p["cx"], p["cy"]
    t = state.width
    state.cutboxes.append(
        CutBoxFeature(
            name=op_id or "cutout",
            box=Box3(cx - w / 2.0, cy - h / 2.0, -1.0,
                     cx + w / 2.0, cy + h / 2.0, t + 1.0),
        )
    )


_register(RecipeOpDecl(
    name="rounded_rect_cutout",
    kind="feature",
    params={
        "w": ("length", None), "h": ("length", None),
        "cx": ("length", 0.0), "cy": ("length", 0.0),
    },
    validators=("form.cuts_respect_keepouts", "topology.cutout_present"),
    apply=_rounded_rect_cutout,
    description="through rectangular cutout (v1: square corners)",
))


def _bore_pattern(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Plain-diameter vertical bores in a line / grid / bolt circle —
    the screwless cousin of hole_pattern (drainage, finger holes, vents).
    ``z_top``/``through`` of 0 mean "the part top" / "all the way through
    from z_top"; a partial ``through`` leaves a blind floor under the bore."""
    state.require_base("bore_pattern")
    kind = p["kind"]
    d = p["d"]
    if d <= 0.0:
        raise RecipeError("bore_pattern needs a positive diameter")
    center = (p["cx"], p["cy"])
    count = int(round(p["count"]))
    if kind == "line":
        centers = line_centers(count, p["spacing"], center)
    elif kind == "grid":
        nx, ny = int(round(p["nx"])), int(round(p["ny"]))
        dy = p["spacing_y"] if p["spacing_y"] > 1e-9 else p["spacing"]
        centers = grid_centers(nx, ny, p["spacing"], dy, center)
    elif kind == "bolt_circle":
        centers = bolt_circle_centers(count, p["bc_d"], center)
    else:
        raise RecipeError(
            f"bore pattern kind {kind!r} not in (line, grid, bolt_circle)")
    t = state.width
    z_top = p["z_top"] if p["z_top"] > 1e-9 else t
    through = p["through"] if p["through"] > 1e-9 else z_top
    pierces = through >= z_top - 1e-9
    name = op_id or "bores"
    for i, (bx, by) in enumerate(centers):
        state.bores.append(
            BoreFeature(
                name=f"{name}_{i}", axis="Z", d=d, center=(bx, by, 0.0),
                span=(z_top - through, z_top),
                # a blind bore keeps its floor: no bottom overshoot
                overshoot=(1.0 if pierces else 0.0, 1.0),
            )
        )
        state.frame[f"{name}_{i}_x"] = bx
        state.frame[f"{name}_{i}_y"] = by
    state.frame[f"{name}_d"] = d
    state.frame[f"{name}_count"] = float(len(centers))


_register(RecipeOpDecl(
    name="bore_pattern",
    kind="feature",
    params={
        "kind": ("choice", "line"),
        "d": ("length", 5.0),
        "count": ("count", 2),
        "nx": ("count", 2),
        "ny": ("count", 2),
        "spacing": ("length", 20.0),
        "spacing_y": ("length", 0.0),
        "bc_d": ("length", 40.0),
        "cx": ("length", 0.0),
        "cy": ("length", 0.0),
        "z_top": ("length", 0.0),
        "through": ("length", 0.0),
    },
    validators=("form.holes_within_outline", "topology.bores_open"),
    apply=_bore_pattern,
    description="plain vertical bores (line / grid / bolt circle) — "
                "drainage, finger holes, vents; no screw semantics",
))


