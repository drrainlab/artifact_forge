"""Recipe ops — the composable geometry builders behind ``form.type:
recipe``. A recipe archetype lists ordered op invocations in YAML and needs
NO Python of its own; each op honors the builder contract:

    geometry contribution  +  semantic regions  +  frame keys  +  validators

The ``validators`` an op declares are MANDATORY for any archetype using it —
the catalog loader refuses a recipe that does not subscribe to them, so a
builder can never ship geometry its checks won't measure (the honesty rule
applied to composition). Op names bind fail-fast at catalog load, exactly
like check names; an op present in YAML but absent here is a CatalogError,
never a silent skip.

Everything in this module is CAD-free: ops emit Form IR only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import math

from ..core.fasteners import screw_spec
from .part import BoreFeature, CutBoxFeature, HoleFeature, PinFeature, PlateFeature, RibFeature
from .patterns import bolt_circle_centers, holes_from_centers, line_centers
from .profiles_plate import rounded_rect_loop
from .regions import Box3, Region
from .section import SectionProfile
from ..product.archetype import RegionRole

KEEPOUT_CLEARANCE = 2.0

#: Port openings (w, h) in mm, before clearance — the common device jacks.
PORT_SIZES: dict[str, tuple[float, float]] = {
    "usb_c": (9.2, 3.4),
    "micro_usb": (8.0, 3.0),
    "usb_a": (13.4, 5.8),
    "hdmi": (15.4, 6.1),
    "audio_35": (6.5, 6.5),
    "sd": (24.5, 3.0),
    "barrel_55": (6.5, 6.5),
}

#: Deep-groove ball bearings: designation -> (OD, width, bore).
BEARINGS: dict[str, tuple[float, float, float]] = {
    "608": (22.0, 7.0, 8.0),
    "625": (16.0, 5.0, 5.0),
    "6001": (28.0, 8.0, 12.0),
}


class RecipeError(ValueError):
    pass


@dataclass
class RecipeState:
    """What the ops build up, in invocation order. The first op must be a
    BASE (it creates the primary solid's section); features attach after."""

    section: SectionProfile | None = None
    width: float = 0.0
    holes: list[HoleFeature] = field(default_factory=list)
    cutboxes: list[CutBoxFeature] = field(default_factory=list)
    bores: list[BoreFeature] = field(default_factory=list)
    ribs: list[RibFeature] = field(default_factory=list)
    plates: list[PlateFeature] = field(default_factory=list)
    pins: list[PinFeature] = field(default_factory=list)
    fields: list[Any] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    frame: dict[str, float] = field(default_factory=dict)
    datums: dict[str, dict[str, Any]] = field(default_factory=dict)

    def require_base(self, op: str) -> None:
        if self.section is None:
            raise RecipeError(f"op {op!r} needs a base solid — put a base op first")


@dataclass(frozen=True)
class RecipeOpDecl:
    name: str
    kind: str  # "base" | "feature"
    #: name -> (value type for the value grammar, default or None=required).
    #: type "choice" passes strings through untouched.
    params: dict[str, tuple[str, Any]]
    #: Checks every archetype using this op MUST subscribe to.
    validators: tuple[str, ...]
    apply: Callable[[RecipeState, dict[str, Any], str], None]
    description: str = ""


RECIPE_OPS: dict[str, RecipeOpDecl] = {}


def _register(decl: RecipeOpDecl) -> None:
    RECIPE_OPS[decl.name] = decl


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
    """Blind pockets sized for heatset inserts, entered from the top face."""
    state.require_base("heatset_insert_pocket")
    spec = screw_spec(p["screw"])
    t = state.width
    depth = p["depth"]
    if depth >= t - 0.8:
        raise RecipeError("heatset pocket would pierce the plate")
    sx = p["spacing"] / 2.0
    name = op_id or "inserts"
    for i, px in enumerate((p["cx"] - sx, p["cx"] + sx)):
        state.bores.append(
            BoreFeature(
                name=f"{name}_{i}", axis="Z", center=(px, p["cy"], 0.0),
                d=spec["heatset"], span=(t - depth, t), overshoot=(0.0, 1.0),
            )
        )
        state.frame[f"{name}_{i}_x"] = px
        state.frame[f"{name}_{i}_y"] = p["cy"]


_register(RecipeOpDecl(
    name="heatset_insert_pocket",
    kind="feature",
    params={
        "screw": ("choice", "M3"), "depth": ("length", 5.0),
        "spacing": ("length", None), "cx": ("length", 0.0),
        "cy": ("length", 0.0),
    },
    validators=("topology.pockets_present",),
    apply=_heatset_insert_pocket,
    description="blind pockets sized from the heatset table, pair along X",
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
    """Receiver windows through the +-X shell walls for a snap lid."""
    state.require_base("snap_window_pair")
    f = state.frame
    if "shell_wall" not in f:
        raise RecipeError("snap_window_pair needs a rounded_box_shell base")
    w_win, h_win, off = p["w"], p["h"], p["top_offset"]
    h_shell = f["shell_h"]
    name = op_id or "snap_window"
    for i, (x0, x1) in enumerate((
        (f["outline_u0"] - 1.0, f["outline_u0"] + f["shell_wall"] + 1.0),
        (f["outline_u1"] - f["shell_wall"] - 1.0, f["outline_u1"] + 1.0),
    )):
        state.cutboxes.append(CutBoxFeature(
            name=f"{name}_{i}",
            box=Box3(x0, -w_win / 2.0, h_shell - off - h_win,
                     x1, w_win / 2.0, h_shell - off),
        ))
    state.frame[f"{name}_w"] = w_win
    state.frame[f"{name}_h"] = h_win
    state.frame[f"{name}_top_offset"] = off


_register(RecipeOpDecl(
    name="snap_window_pair",
    kind="feature",
    params={
        "w": ("length", 8.8), "h": ("length", 3.8),
        "top_offset": ("length", 6.0),
    },
    validators=("form.cuts_respect_keepouts", "topology.cutout_present"),
    apply=_snap_window_pair,
    description="through-wall receiver windows on both X walls",
))
