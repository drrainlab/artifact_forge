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
    # the boss-top mating plane — a heatset_insert_pattern port lands here
    state.datums[f"{name}_top"] = {
        "at": [cx, cy, top], "rotate": [0.0, 0.0, 0.0]}


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


def _strap_slot_pair_plate(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A paired webbing slot through a plate — the strap threads down one
    slot, under the center bar, up the other. Publishes the strap_center
    datum a strap_slot_pair interface binds to (the plate cousin of the
    clamp-only cord_slot_pair)."""
    state.require_base("strap_slot_pair_plate")
    f = state.frame
    if "outline_u0" not in f:
        raise RecipeError("strap_slot_pair_plate needs a rounded_plate base")
    strap_w = p["strap_w"]
    slot_gap = p["slot_gap"]
    bridge_w = p["bridge_w"]
    cx, cy = p["cx"], p["cy"]
    t = state.width
    if bridge_w < 6.0:
        raise RecipeError(f"bridge {bridge_w:g} under 6 mm snaps under load")
    slot_h = strap_w + 2.0
    if cy - slot_h / 2.0 < f["outline_v0"] + 2.0 or \
            cy + slot_h / 2.0 > f["outline_v1"] - 2.0:
        raise RecipeError(
            f"strap slots ({slot_h:g} tall) run past the plate edge")
    name = op_id or "strap"
    off = (bridge_w + slot_gap) / 2.0
    for tag, sx in (("a", cx - off), ("b", cx + off)):
        state.cutboxes.append(CutBoxFeature(
            name=f"{name}_slot_{tag}",
            box=Box3(sx - slot_gap / 2.0, cy - slot_h / 2.0, -1.0,
                     sx + slot_gap / 2.0, cy + slot_h / 2.0, t + 1.0)))
    state.datums[f"{name}_center"] = {
        "at": [cx, cy, t], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update({
        f"{name}_w": strap_w,
        f"{name}_slot_gap": slot_gap,
        f"{name}_bridge_w": bridge_w,
    })


_register(RecipeOpDecl(
    name="strap_slot_pair_plate",
    kind="feature",
    params={
        "strap_w": ("length", 25.0),
        "slot_gap": ("length", 4.0),
        "bridge_w": ("length", 10.0),
        "cx": ("length", 0.0),
        "cy": ("length", 0.0),
    },
    validators=("form.cuts_respect_keepouts", "topology.cutout_present"),
    apply=_strap_slot_pair_plate,
    description="paired webbing slots through a plate + the strap_center "
                "datum a strap_slot_pair port binds to",
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


#: Battery cell nominal MAX diameters and lengths (mm) — the pocket adds
#: fit_clearance on top; the length is reference data for holder sizing.
CELLS: dict[str, tuple[float, float]] = {
    "18650": (18.6, 65.0),
    "21700": (21.4, 70.0),
    "aa": (14.5, 50.5),
    "aaa": (10.5, 44.5),
    "cr123": (17.0, 34.5),
}

#: Retention bite band: mouth must be this much narrower than the cell —
#: less slips, more won't snap in without cracking the lip.
CELL_LIP_BITE_BAND = (0.6, 2.5)
CELL_WEB_MIN = 2.5


def _cell_pocket_grid(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """N x M grid of blind cylindrical battery pockets with a retaining
    mouth lip (the cell snaps past it) and a contact slot through the
    floor under each cell (tab access / spot-weld / spring contact).
    Electrical contacts stay external hardware — this op owns the honest
    mechanics of holding the cell."""
    state.require_base("cell_pocket_grid")
    cell = p["cell"]
    if cell not in CELLS:
        raise RecipeError(f"unknown cell {cell!r}; known: {sorted(CELLS)}")
    cell_d, cell_len = CELLS[cell]
    nx, ny = int(round(p["nx"])), int(round(p["ny"]))
    fit = p["fit_clearance"]
    lip_w, lip_h = p["lip_w"], p["lip_h"]
    depth = p["pocket_depth"]
    slot_w, slot_l = p["slot_w"], p["slot_l"]
    t = state.width
    if nx < 1 or ny < 1:
        raise RecipeError("cell_pocket_grid needs nx, ny >= 1")
    d_pocket = cell_d + fit
    d_mouth = d_pocket - 2.0 * lip_w
    bite = cell_d - d_mouth
    lo, hi = CELL_LIP_BITE_BAND
    if not lo <= bite <= hi:
        raise RecipeError(
            f"lip bite {bite:.2f} outside [{lo:g}, {hi:g}] — the cell "
            "either slips out or cracks the lip going in")
    if depth >= t - 1.2:
        raise RecipeError(f"pocket {depth:g} pierces the {t:g} block")
    if depth < lip_h + 4.0:
        raise RecipeError("pocket too shallow to hold a cell under its lip")
    if depth > cell_len:
        raise RecipeError(
            f"pocket {depth:g} deeper than the {cell} cell ({cell_len:g})")
    pitch = p["pitch"] if p["pitch"] > 1e-9 else d_pocket + CELL_WEB_MIN
    if pitch - d_pocket < CELL_WEB_MIN - 1e-9:
        raise RecipeError(
            f"pitch {pitch:g} leaves {pitch - d_pocket:.2f} web between "
            f"pockets (min {CELL_WEB_MIN:g})")
    if slot_w >= d_mouth:
        raise RecipeError("contact slot wider than the pocket mouth")

    name = op_id or "cells"
    centers = grid_centers(nx, ny, pitch, pitch, (p["cx"], p["cy"]))
    for i, (bx, by) in enumerate(centers):
        # The bearing-seat inset-span trick: both cutters declare OPEN
        # overshoots (the pocket opens into the mouth, the mouth into the
        # air — no false 'blind skin' expectations for the pocket probe),
        # and each span is inset by the overshoot so the ACTUAL cut lands
        # exactly on the intended band and never nibbles the lip ring.
        state.bores.append(BoreFeature(
            name=f"{name}_{i}", axis="Z", d=d_pocket,
            center=(bx, by, 0.0), span=(t - depth + 1.0, t - lip_h - 1.0),
            overshoot=(1.0, 1.0)))
        state.bores.append(BoreFeature(
            name=f"{name}_{i}_mouth", axis="Z", d=d_mouth,
            center=(bx, by, 0.0), span=(t - lip_h + 0.5, t),
            overshoot=(1.0, 1.0)))
        # contact slot through the floor under the cell
        state.cutboxes.append(CutBoxFeature(
            name=f"{name}_{i}_contact",
            box=Box3(bx - slot_w / 2.0, by - slot_l / 2.0, -1.0,
                     bx + slot_w / 2.0, by + slot_l / 2.0,
                     t - depth + 0.5)))
        state.frame[f"{name}_{i}_x"] = bx
        state.frame[f"{name}_{i}_y"] = by
        # the mouth lip ring, probed like a bearing-seat lip
        state.frame[f"{name}_{i}_cx"] = bx
        state.frame[f"{name}_{i}_cy"] = by
        state.frame[f"{name}_{i}_lip_r"] = (d_mouth + d_pocket) / 4.0
        state.frame[f"{name}_{i}_lip_z0"] = t - lip_h
        state.frame[f"{name}_{i}_lip_z1"] = t
    state.frame.update(
        cell_grid_nx=float(nx), cell_grid_ny=float(ny),
        cell_pitch=pitch, cell_d=cell_d, cell_pocket_d=d_pocket,
        cell_mouth_d=d_mouth, cell_lip_bite=bite, cell_lip_h=lip_h,
        cell_pocket_depth=depth, cell_len_ref=cell_len,
    )


_register(RecipeOpDecl(
    name="cell_pocket_grid",
    kind="feature",
    params={
        "cell": ("choice", "18650"),
        "nx": ("count", 2), "ny": ("count", 2),
        "pitch": ("length", 0.0),
        "fit_clearance": ("length", 0.4),
        "lip_w": ("length", 0.8), "lip_h": ("length", 1.2),
        "pocket_depth": ("length", 12.0),
        "slot_w": ("length", 4.0), "slot_l": ("length", 10.0),
        "cx": ("length", 0.0), "cy": ("length", 0.0),
    },
    validators=(
        "form.cell_lip_retains",
        "form.cell_grid_webs_ok",
        "form.cuts_respect_keepouts",
        "topology.bores_open",
        "topology.seat_lips_present",
        "topology.cutout_present",
    ),
    apply=_cell_pocket_grid,
    description="grid of blind battery pockets with retaining mouth lips "
                "and floor contact slots (cells from the CELLS table)",
))


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


