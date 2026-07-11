"""Revolve-family recipe ops — spool, plant pot, net pot: polyline
half-sections on the core ``profile_revolve`` kernel plus their
perforation fields (radial flange slots, circular mesh floor, vertical
wall-slot ring). Measurement contract lives in
:mod:`artifact_forge_ng.form.checks_pots`."""
from __future__ import annotations

import math
from typing import Any

from .part import BoreFeature, FieldFeature
from .profiles_revolve import loop_from_points
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from .section import Pt, SectionProfile
from ..product.archetype import RegionRole

SPOOL_CORD_MARGIN = 4.0    # flange must out-reach the barrel by this, mm
POT_TAPER_MAX_DEG = 30.0   # printable outward lean of a pot wall
SLOT_LIGAMENT_MIN = 2.0    # web between wall slots / tie slots, mm


def _revolve_section(pts: list[Pt]) -> SectionProfile:
    return SectionProfile(
        name="recipe_revolve",
        outer=loop_from_points(pts),
        plane="XZ",
        width_axis="Y",
    )


# -- spool_body ------------------------------------------------------------------


def _spool_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Cord spool: an H-profile revolve — two flanges joined by a barrel,
    one axial through bore (hang it on a rod, or bolt a handle through)."""
    if state.section is not None:
        raise RecipeError("spool_body must be the (single) base op")
    r_fl = p["flange_d"] / 2.0
    r_bar = p["barrel_d"] / 2.0
    r_bore = p["bore_d"] / 2.0
    fl_t, bar_l = p["flange_t"], p["barrel_l"]
    if r_fl < r_bar + SPOOL_CORD_MARGIN:
        raise RecipeError(
            f"flange Ø{2 * r_fl:g} must out-reach the barrel Ø{2 * r_bar:g} "
            f"by {SPOOL_CORD_MARGIN:g} per side — nothing holds the cord")
    if r_bar - r_bore < 2.0:
        raise RecipeError("barrel wall under 2 mm around the bore")
    if bar_l < 8.0:
        raise RecipeError("barrel under 8 mm holds no cord")
    total = 2.0 * fl_t + bar_l
    z1, z2 = fl_t, fl_t + bar_l

    pts = [
        Pt(r_bore, 0.0), Pt(r_fl, 0.0),      # bottom flange underside
        Pt(r_fl, z1),                          # bottom flange rim
        Pt(r_bar, z1),                         # flange top in to the barrel
        Pt(r_bar, z2),                         # barrel wall
        Pt(r_fl, z2),                          # top flange underside
        Pt(r_fl, total),                       # top flange rim
        Pt(r_bore, total),                     # top face in to the bore
    ]
    state.section = _revolve_section(pts)
    state.kind = "profile_revolve"
    state.width = 2.0 * r_fl

    name = op_id or "spool"
    state.regions.append(Region(
        f"{name}_flanges", RegionRole.MOUNTING_SURFACE,
        Box3(-r_fl, -r_fl, 0.0, r_fl, r_fl, total)))
    state.datums["axis"] = {"at": [0.0, 0.0, total / 2.0],
                            "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        axis_clear_r=r_bore, bore_d=2.0 * r_bore,
        flange_r=r_fl, barrel_r=r_bar,
        flange_t=fl_t, barrel_l=bar_l, spool_h=total,
        flange_margin=r_fl - r_bar,
        outline_outer_r=r_fl, outline_inner_r=r_bore,
        # the revolve cavity probe reads the cup convention:
        exit_r=r_bore, height=total,
    )


_register(RecipeOpDecl(
    name="spool_body",
    kind="base",
    params={
        "flange_d": ("length", None), "barrel_d": ("length", None),
        "barrel_l": ("length", None), "flange_t": ("length", 4.0),
        "bore_d": ("length", 8.0),
    },
    validators=(
        "form.spool_flanges_ok",
        "form.revolve_profile_clear_of_axis",
        "topology.revolve_cavity_open",
        "topology.single_connected_solid",
    ),
    apply=_spool_body,
    description="H-profile cord spool: two flanges + barrel + axial bore",
))


def _flange_slot_pattern(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Radial tie slots through a spool flange — the cord's start/finish
    anchors. Slots are explicit field polygons (free orientation in XY),
    ligament between neighbours is measured, not hoped."""
    state.require_base("flange_slot_pattern")
    f = state.frame
    if "flange_r" not in f:
        raise RecipeError("flange_slot_pattern needs a spool_body base")
    count = int(round(p["count"]))
    slot_w = p["slot_w"]
    which = p["flange"]
    r_fl, r_bar, fl_t, total = f["flange_r"], f["barrel_r"], f["flange_t"], f["spool_h"]
    r0 = p["r_inner"] if p["r_inner"] > 1e-9 else r_bar + 2.0
    r1 = r_fl - 2.0
    if count < 1:
        raise RecipeError("flange_slot_pattern needs count >= 1")
    if r1 - r0 < 4.0:
        raise RecipeError("flange too narrow for tie slots")
    gap_arc = 2.0 * math.pi * r0 / count - slot_w
    if gap_arc < SLOT_LIGAMENT_MIN:
        raise RecipeError(
            f"{count} slots of {slot_w:g} leave {gap_arc:.1f} mm ligament "
            f"at r={r0:g} (min {SLOT_LIGAMENT_MIN:g})")

    if which == "top":
        planes = [total]
    elif which == "bottom":
        planes = [fl_t]
    elif which == "both":
        planes = [total, fl_t]
    else:
        raise RecipeError(f"flange {which!r} not in (top, bottom, both)")

    half = slot_w / 2.0
    polys = []
    for k in range(count):
        ang = math.tau * k / count
        ca, sa = math.cos(ang), math.sin(ang)
        # radial rectangle: along the ray, slot_w across it
        nx, ny = -sa, ca
        polys.append((
            (r0 * ca - half * nx, r0 * sa - half * ny),
            (r1 * ca - half * nx, r1 * sa - half * ny),
            (r1 * ca + half * nx, r1 * sa + half * ny),
            (r0 * ca + half * nx, r0 * sa + half * ny),
        ))
    for plane_z in planes:
        state.fields.append(FieldFeature(
            plane_z=plane_z, centers=(), cell=slot_w, depth=fl_t + 1.0,
            pattern="slots", polygons=tuple(polys),
            min_ligament=SLOT_LIGAMENT_MIN,
        ))
    state.frame.update(
        tie_slot_count=float(count), tie_slot_w=slot_w,
        tie_slot_r0=r0, tie_slot_r1=r1, tie_slot_gap=gap_arc,
    )


_register(RecipeOpDecl(
    name="flange_slot_pattern",
    kind="feature",
    params={
        "count": ("count", 3), "slot_w": ("length", 4.0),
        "flange": ("choice", "top"), "r_inner": ("length", 0.0),
    },
    validators=(
        "form.min_ligament_ok",
        "form.field_cells_present",
        "topology.hex_field_present",
    ),
    apply=_flange_slot_pattern,
    description="radial cord tie slots through a spool flange",
))


# -- pot_body --------------------------------------------------------------------


def _taper_deg(r_bot: float, r_top: float, h: float) -> float:
    return math.degrees(math.atan2(r_top - r_bot, h))


def _pot_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Plant pot: a tapered vessel with a RAISED floor — the foot ring
    stands on the saucer/shelf, the drainage bores exit into open air
    under the floor, water never pools against the seat. Circular plan
    in v1 (revolve); a superellipse pot needs the loft kernel."""
    if state.section is not None:
        raise RecipeError("pot_body must be the (single) base op")
    r_top = p["top_d"] / 2.0
    r_bot = p["bottom_d"] / 2.0
    h, wall, floor_t = p["h"], p["wall"], p["floor_t"]
    raise_z = p["floor_raise"]
    if r_top < r_bot:
        raise RecipeError(
            "a pot must open upward (top_d >= bottom_d) — an undercut "
            "vessel traps its own root ball and its printed overhang")
    if wall < 1.6 or floor_t < 2.0:
        raise RecipeError("pot wall under 1.6 / floor under 2.0")
    if raise_z < 2.0:
        raise RecipeError(
            "floor_raise under 2 mm leaves no air gap for drainage")
    floor_top = raise_z + floor_t
    if floor_top + 10.0 > h:
        raise RecipeError("raised floor leaves under 10 mm of root volume")
    taper = _taper_deg(r_bot, r_top, h)
    if r_bot - wall < 8.0:
        raise RecipeError("foot ring too small — no floor to drain through")

    def r_out(z: float) -> float:
        return r_bot + (r_top - r_bot) * z / h

    pts = [
        Pt(r_bot - wall, 0.0), Pt(r_bot, 0.0),               # foot ring
        Pt(r_top, h),                                          # outer wall
        Pt(r_top - wall, h),                                   # rim
        Pt(r_out(floor_top) - wall, floor_top),                # inner wall
        Pt(0.0, floor_top),                                    # floor top
        Pt(0.0, raise_z),                                      # down the axis
        Pt(r_out(raise_z) - wall, raise_z),                    # floor underside
    ]
    state.section = _revolve_section(pts)
    state.kind = "profile_revolve"
    state.width = 2.0 * r_top

    name = op_id or "pot"
    state.regions.extend([
        Region(f"{name}_cavity", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(-r_top, -r_top, floor_top, r_top, r_top, h)),
        # tapered wall: real region, but NOT a field canvas —
        # cylindrical_z_mapping_v1 is constant-radius only
        Region(f"{name}_outer_shell", RegionRole.AESTHETIC_LIGHTENING,
               Box3(-r_top, -r_top, 0.0, r_top, r_top, h)),
    ])
    state.datums["axis"] = {"at": [0.0, 0.0, h / 2.0],
                            "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        pot_r_top=r_top, pot_r_bottom=r_bot, pot_h=h, pot_wall=wall,
        pot_taper_deg=taper,
        pot_floor_z0=raise_z, pot_floor_top=floor_top,
        pot_inner_r_floor=r_out(floor_top) - wall,
        # bore webs measured on the floor disc
        outline_outer_r=r_out(floor_top) - wall,
    )


_register(RecipeOpDecl(
    name="pot_body",
    kind="base",
    params={
        "top_d": ("length", None), "bottom_d": ("length", None),
        "h": ("length", None), "wall": ("length", 2.4),
        "floor_t": ("length", 3.0), "floor_raise": ("length", 6.0),
    },
    validators=(
        "form.pot_taper_ok",
        "form.pot_floor_drains",
        "topology.single_connected_solid",
    ),
    apply=_pot_body,
    description="tapered plant pot with a raised drainage floor over a "
                "standing foot ring",
))


# -- net_pot_body + grid_floor + wall_slot_ring -----------------------------------


def _net_pot_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Hydroponic net pot: a thin tapered cup with a hanging flange at the
    rim. The floor is thin and SOLID here — grid_floor opens it, and
    wall_slot_ring opens the walls; the body only promises the shape."""
    if state.section is not None:
        raise RecipeError("net_pot_body must be the (single) base op")
    r_top = p["top_d"] / 2.0
    r_bot = p["bottom_d"] / 2.0
    h, wall, floor_t = p["h"], p["wall"], p["floor_t"]
    r_flange = r_top + p["flange_w"]
    flange_t = p["flange_t"]
    if r_top < r_bot + 1.0:
        raise RecipeError("a net pot must taper (top_d > bottom_d) to "
                          "slip into its hole and release its root plug")
    if wall < 1.2 or floor_t < 1.2:
        raise RecipeError("net pot wall/floor under 1.2 mm")
    if p["flange_w"] < 2.0:
        raise RecipeError("flange under 2 mm cannot hang the pot")
    if flange_t + 2.0 > h:
        raise RecipeError("flange eats the whole cup")
    taper = _taper_deg(r_bot, r_top, h)

    def r_out(z: float) -> float:
        return r_bot + (r_top - r_bot) * z / h

    z_fl = h - flange_t
    pts = [
        Pt(0.0, 0.0), Pt(r_bot, 0.0),          # floor underside
        Pt(r_out(z_fl), z_fl),                   # outer wall to the flange
        Pt(r_flange, z_fl),                      # flange underside
        Pt(r_flange, h),                         # flange rim
        Pt(r_top - wall, h),                     # flange top in to the cavity
        Pt(r_out(floor_t) - wall, floor_t),      # inner wall
        Pt(0.0, floor_t),                        # floor top to the axis
    ]
    state.section = _revolve_section(pts)
    state.kind = "profile_revolve"
    state.width = 2.0 * r_flange

    name = op_id or "netpot"
    state.regions.append(Region(
        f"{name}_flange", RegionRole.MOUNTING_SURFACE,
        Box3(-r_flange, -r_flange, z_fl, r_flange, r_flange, h)))
    state.datums["axis"] = {"at": [0.0, 0.0, h / 2.0],
                            "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        pot_r_top=r_top, pot_r_bottom=r_bot, pot_h=h, pot_wall=wall,
        pot_taper_deg=taper,
        net_flange_r=r_flange, net_flange_t=flange_t, net_rim_z=h,
        net_floor_t=floor_t,
        net_floor_r=r_out(floor_t) - wall,
        outline_outer_r=r_out(floor_t) - wall,
    )


_register(RecipeOpDecl(
    name="net_pot_body",
    kind="base",
    params={
        "top_d": ("length", None), "bottom_d": ("length", None),
        "h": ("length", None), "wall": ("length", 1.6),
        "floor_t": ("length", 1.6),
        "flange_w": ("length", 4.0), "flange_t": ("length", 2.4),
    },
    validators=(
        "form.pot_taper_ok",
        "topology.single_connected_solid",
    ),
    apply=_net_pot_body,
    description="thin tapered hydroponic cup with a hanging rim flange "
                "(grid_floor / wall_slot_ring open it up)",
))


def _grid_floor(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Square through-cells across a CIRCULAR floor disc — the net pot's
    root mesh. Cells are kept only where they fit inside the disc minus
    the margin; the open-area ratio is published and checked."""
    state.require_base("grid_floor")
    f = state.frame
    if "net_floor_r" not in f:
        raise RecipeError("grid_floor needs a net_pot_body base")
    cell, rib, margin = p["cell"], p["rib"], p["margin"]
    floor_r, floor_t = f["net_floor_r"], f["net_floor_t"]
    if rib < 1.0:
        raise RecipeError("mesh rib under 1 mm")
    r_keep = floor_r - margin
    if r_keep < cell:
        raise RecipeError("floor too small for a single mesh cell")
    pitch = cell + rib
    n = int((2.0 * r_keep) // pitch) + 1
    half = cell / 2.0
    reach = r_keep - half * math.sqrt(2.0)  # cell corner stays inside
    polys = []
    start = -(n - 1) * pitch / 2.0
    for i in range(n):
        for j in range(n):
            cx, cy = start + i * pitch, start + j * pitch
            if math.hypot(cx, cy) <= reach:
                polys.append((
                    (cx - half, cy - half), (cx + half, cy - half),
                    (cx + half, cy + half), (cx - half, cy + half),
                ))
    if not polys:
        raise RecipeError("no mesh cell fits the floor disc")
    state.fields.append(FieldFeature(
        plane_z=floor_t, centers=(), cell=cell, depth=floor_t + 1.0,
        pattern="slots", polygons=tuple(polys), min_ligament=rib,
    ))
    open_area = len(polys) * cell * cell
    disc_area = math.pi * floor_r * floor_r
    state.frame.update(
        floor_mesh_cell=cell, floor_mesh_rib=rib,
        floor_open_ratio=open_area / disc_area,
        floor_mesh_cells=float(len(polys)),
    )


_register(RecipeOpDecl(
    name="grid_floor",
    kind="feature",
    params={
        "cell": ("length", 6.0), "rib": ("length", 1.4),
        "margin": ("length", 2.0),
    },
    validators=(
        "form.floor_open_area_ok",
        "form.min_ligament_ok",
        "form.field_cells_present",
        "topology.hex_field_present",
    ),
    apply=_grid_floor,
    description="square through-mesh across the circular net pot floor",
))


def _wall_slot_ring(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """N vertical slots around the tapered wall (cylindrical field
    mapping): slot positions are computed at the band's mid-height
    radius, the radial cutters overshoot the taper so every slot pierces
    the wall at every height. Slots stop below the flange and above the
    floor — the ring check measures the published band."""
    state.require_base("wall_slot_ring")
    f = state.frame
    if "net_rim_z" not in f:
        raise RecipeError("wall_slot_ring needs a net_pot_body base")
    count = int(round(p["count"]))
    slot_w = p["slot_w"]
    r_top, r_bot = f["pot_r_top"], f["pot_r_bottom"]
    h, wall = f["pot_h"], f["pot_wall"]
    floor_t, flange_t = f["net_floor_t"], f["net_flange_t"]
    z0 = floor_t + p["floor_margin"]
    z1 = h - flange_t - p["rim_margin"]
    if z1 - z0 < 6.0:
        raise RecipeError("wall band under 6 mm tall — no room for slots")
    if count < 3:
        raise RecipeError("wall_slot_ring needs at least 3 slots")

    def r_out(z: float) -> float:
        return r_bot + (r_top - r_bot) * z / h

    z_mid = (z0 + z1) / 2.0
    r_mid = r_out(z_mid) - wall / 2.0
    gap_arc = 2.0 * math.pi * r_mid / count - slot_w
    if gap_arc < SLOT_LIGAMENT_MIN:
        raise RecipeError(
            f"{count} slots of {slot_w:g} leave {gap_arc:.1f} mm ligament "
            f"(min {SLOT_LIGAMENT_MIN:g})")
    r_outer_max = r_out(z1)
    r_inner_min = r_out(z0) - wall
    depth = (r_outer_max - r_inner_min) + 1.0

    circumference = 2.0 * math.pi * r_mid
    polys = []
    for k in range(count):
        a = circumference * k / count
        polys.append((
            (a - slot_w / 2.0, z0), (a + slot_w / 2.0, z0),
            (a + slot_w / 2.0, z1), (a - slot_w / 2.0, z1),
        ))
    state.fields.append(FieldFeature(
        plane_z=z1, centers=(), cell=slot_w, depth=depth,
        pattern="slots", polygons=tuple(polys),
        min_ligament=SLOT_LIGAMENT_MIN,
        mapping="cylindrical", cyl_center=(0.0, 0.0),
        cyl_r=r_mid, cyl_r_outer=r_outer_max + 0.5, cyl_z0=0.0,
    ))
    state.frame.update(
        wall_slot_count=float(count), wall_slot_w=slot_w,
        wall_slot_z0=z0, wall_slot_z1=z1, wall_slot_gap=gap_arc,
    )


_register(RecipeOpDecl(
    name="wall_slot_ring",
    kind="feature",
    params={
        "count": ("count", 8), "slot_w": ("length", 4.0),
        "floor_margin": ("length", 3.0), "rim_margin": ("length", 3.0),
    },
    validators=(
        "form.wall_slots_ok",
        "form.min_ligament_ok",
        "topology.hex_field_present",
    ),
    apply=_wall_slot_ring,
    description="vertical aeration/root slots around the tapered net pot "
                "wall (cylindrical field mapping)",
))

# -- foot_body -------------------------------------------------------------------

FOOT_PRESS_BAND = (0.1, 0.5)   # diametral spigot-into-tube interference, mm
FOOT_ENGAGE_K = 0.6            # spigot length >= k * tube inner diameter


def _foot_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Press-fit furniture foot: a revolved pad with a chamfered spigot
    that presses INTO a tube leg (the user measures the tube's inner
    diameter — the spigot adds the interference), and a shallow recess
    in the pad underside for a glued TPU disc. Prints pad-down: spigot
    up, recess rings the first layer — support-free by construction."""
    if state.section is not None:
        raise RecipeError("foot_body must be the (single) base op")
    r_pad = p["pad_d"] / 2.0
    pad_t = p["pad_t"]
    tube_id = p["tube_id"]
    press = p["press"]
    spigot_l = (p["spigot_l"] if p["spigot_l"] > 1e-9
                else FOOT_ENGAGE_K * tube_id + 4.0)
    recess_t = p["pad_recess_t"]
    lo, hi = FOOT_PRESS_BAND
    if not lo <= press <= hi:
        raise RecipeError(
            f"press {press:g} outside [{lo:g}, {hi:g}] — a loose spigot "
            "drops out, an over-pressed one splits the tube or the print")
    spigot_d = tube_id + press
    r_spigot = spigot_d / 2.0
    if r_spigot + 2.0 > r_pad:
        raise RecipeError(
            f"pad Ø{2 * r_pad:g} leaves no shoulder around the "
            f"Ø{spigot_d:g} spigot (needs 2 mm per side)")
    if spigot_l < FOOT_ENGAGE_K * tube_id:
        raise RecipeError(
            f"spigot {spigot_l:g} shorter than {FOOT_ENGAGE_K:g}x tube "
            f"bore ({FOOT_ENGAGE_K * tube_id:g}) — the foot rocks out")
    if recess_t >= pad_t - 1.2:
        raise RecipeError("TPU recess leaves no pad skin")
    r_recess = (p["pad_recess_d"] if p["pad_recess_d"] > 1e-9
                else p["pad_d"] - 8.0) / 2.0
    if r_recess + 2.0 > r_pad:
        raise RecipeError("TPU recess runs into the pad rim")
    ch = min(1.2, spigot_l * 0.2)
    top = pad_t + spigot_l

    pts = [
        Pt(0.0, 0.0), Pt(r_pad, 0.0),                # pad underside
        Pt(r_pad, pad_t),                              # pad rim
        Pt(r_spigot, pad_t),                           # shoulder
        Pt(r_spigot, top - ch), Pt(r_spigot - ch, top),  # spigot + lead-in
        Pt(0.0, top),
    ]
    state.section = _revolve_section(pts)
    state.kind = "profile_revolve"
    state.width = 2.0 * r_pad

    name = op_id or "foot"
    # the glued TPU disc's land — a shallow blind recess in the underside
    state.bores.append(BoreFeature(
        name=f"{name}_pad_recess", axis="Z", d=2.0 * r_recess,
        center=(0.0, 0.0, 0.0), span=(0.0, recess_t), overshoot=(1.0, 0.0)))
    state.regions.append(Region(
        f"{name}_pad", RegionRole.SOFT_CONTACT_SURFACE,
        Box3(-r_pad, -r_pad, 0.0, r_pad, r_pad, pad_t)))
    state.datums["tube_axis"] = {
        "at": [0.0, 0.0, top], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        foot_pad_r=r_pad, foot_pad_t=pad_t,
        foot_spigot_d=spigot_d, foot_spigot_l=spigot_l,
        foot_tube_id=tube_id, foot_press=press,
        foot_recess_r=r_recess, foot_recess_t=recess_t,
        outline_outer_r=r_pad,
    )


_register(RecipeOpDecl(
    name="foot_body",
    kind="base",
    params={
        "pad_d": ("length", None),
        "pad_t": ("length", 8.0),
        "tube_id": ("length", None),
        "press": ("length", 0.25),
        "spigot_l": ("length", 0.0),
        "pad_recess_d": ("length", 0.0),
        "pad_recess_t": ("length", 0.8),
    },
    validators=(
        "form.foot_press_fit_ok",
        "topology.bores_open",
        "topology.pockets_present",
        "topology.single_connected_solid",
    ),
    apply=_foot_body,
    description="press-fit furniture foot: pad + chamfered spigot into a "
                "tube leg + TPU disc recess in the underside",
))
