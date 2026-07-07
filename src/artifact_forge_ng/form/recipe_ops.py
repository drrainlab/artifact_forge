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
from .part import (
    BoreFeature,
    ChannelCutFeature,
    CutBoxFeature,
    HoleFeature,
    PinFeature,
    PlateFeature,
    RibFeature,
)
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
    kind: str = "section_extrude"
    print_orientation: str = "as_modeled"
    holes: list[HoleFeature] = field(default_factory=list)
    cutboxes: list[CutBoxFeature] = field(default_factory=list)
    channels: list[ChannelCutFeature] = field(default_factory=list)
    bores: list[BoreFeature] = field(default_factory=list)
    ribs: list[RibFeature] = field(default_factory=list)
    plates: list[PlateFeature] = field(default_factory=list)
    pins: list[PinFeature] = field(default_factory=list)
    fields: list[Any] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    frame: dict[str, float] = field(default_factory=dict)
    datums: dict[str, dict[str, Any]] = field(default_factory=dict)
    windows: dict[str, Any] = field(default_factory=dict)

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


# -- wall_ring_mount ------------------------------------------------------------


def _wall_ring_mount(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Wall tool ring mount base: a wall flange fused with a C-ring saddle
    around a vertical tool axis, buttressed by gusset ribs. Model frame:
    Z = wall normal (wall at z=0), X = vertical along the wall = tool axis
    = extrusion axis, Y = horizontal. The base section (top view: flange
    strip + fused ring) extrudes x in [0, collar_h]; the taller flange
    continues above as a PlateFeature — anchors land there via a separate
    hole op. Prints upright ("side_profile"): everything rises from the
    section on the bed."""
    from .profiles_wallmount import WallRingParams, build_wall_ring_section
    from .style import MOLDED_UTILITY_PART

    if state.section is not None:
        raise RecipeError("wall_ring_mount must be the (single) base op")
    collar_h, flange_h = p["collar_h"], p["flange_h"]
    if collar_h + 24.0 > flange_h:
        raise RecipeError(
            f"flange_h {flange_h:g} leaves no anchor panel above the "
            f"collar (needs >= collar_h + 24)"
        )
    wp = WallRingParams(
        tool_d=p["tool_d"], clearance=p["clearance"], ring_wall=p["ring_wall"],
        capture_deg=p["capture_deg"], standoff=p["standoff"],
        flange_w=p["flange_w"], flange_t=p["flange_t"],
        flange_corner_r=p["flange_corner_r"],
    )
    try:
        profile, f = build_wall_ring_section(wp, MOLDED_UTILITY_PART)
    except ValueError as exc:
        raise RecipeError(f"wall_ring_mount: {exc}") from exc
    state.section = profile
    state.width = collar_h
    state.print_orientation = "side_profile"

    fw, t = p["flange_w"], p["flange_t"]
    s, r_i, r_o = f["saddle_cz"], f["saddle_r"], f["r_outer"]
    name = op_id or "body"
    state.plates.append(
        PlateFeature(
            name=f"{name}_flange",
            x0=0.0, y0=-fw / 2.0, x1=flange_h, y1=fw / 2.0,
            z_bottom=0.0, thickness=t, corner_r=p["flange_corner_r"],
        )
    )

    # Gusset ribs: two side buttresses welding the flange front to the ring
    # flank, provably clear of the saddle cavity (|y| > saddle_r). A center
    # rib under the ring belly is geometrically impossible in this family —
    # it needs the ring floated off the flange, which contradicts the
    # direct-fusion guard — so the count is fixed, not a parameter.
    rib_t = p["rib_t"]
    rib_y0 = r_i + 1.5
    if rib_y0 + rib_t > fw / 2.0 - 1.0:
        raise RecipeError(
            f"gusset ribs at |y| {rib_y0 + rib_t:.1f} stick past the flange "
            f"(flange_w/2 - 1 = {fw / 2.0 - 1.0:.1f})"
        )
    for i, side in enumerate((-1.0, 1.0)):
        lo, hi = side * (rib_y0 + rib_t), side * rib_y0
        state.ribs.append(
            RibFeature(
                name=f"{name}_rib_{i}",
                box=Box3(0.0, min(lo, hi), t - 0.6, collar_h, max(lo, hi), s),
            )
        )
    # Semantic regions — names match the archetype YAML region ids.
    state.regions.extend([
        Region("wall_flange", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -fw / 2.0, 0.0, flange_h, fw / 2.0, t)),
        Region("saddle_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -r_i, s - r_i, collar_h, r_i, s + r_i)),
        Region("retaining_lip", RegionRole.RETAINING_FLEXURE,
               Box3(0.0, -(r_o + 1.0), s, collar_h, r_o + 1.0, s + r_o + 1.0)),
        Region("load_rib_zone", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, -(r_o + 1.0), t - 1.0, collar_h, r_o + 1.0, s)),
        Region("flange_lightening", RegionRole.AESTHETIC_LIGHTENING,
               Box3(collar_h + 6.0, -(fw / 2.0 - 4.0), 0.0,
                    flange_h - 4.0, fw / 2.0 - 4.0, t)),
        # Reserved for v2 cylindrical/biomorphic mapping (ring axis is X;
        # field mapping is Z-axis-only today) — non-editable in the YAML.
        Region("outer_shell", RegionRole.AESTHETIC_LIGHTENING,
               Box3(0.0, -r_o, t, collar_h, r_o, s + r_o)),
    ])

    load_n = p["tool_mass_kg"] * 9.81
    state.frame.update(f)
    state.frame.update(
        collar_h=collar_h,
        flange_h=flange_h,
        # the plate outline the hole-web checks measure against:
        outline_u0=0.0, outline_v0=-fw / 2.0,
        outline_u1=flange_h, outline_v1=fw / 2.0,
        outline_corner_r=p["flange_corner_r"], plate_t=t,
        load_n_est=load_n,
        moment_nmm_est=load_n * p["safety_factor"] * p["standoff"],
    )
    state.datums["tool_axis"] = {
        "at": [collar_h / 2.0, 0.0, s], "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["mount_face"] = {
        "at": [flange_h / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="wall_ring_mount",
    kind="base",
    params={
        "tool_d": ("length", None), "clearance": ("length", 1.0),
        "ring_wall": ("length", 7.0), "collar_h": ("length", 30.0),
        "capture_deg": ("number", 220.0), "standoff": ("length", None),
        "flange_w": ("length", None), "flange_h": ("length", None),
        "flange_t": ("length", None), "flange_corner_r": ("length", 6.0),
        "rib_t": ("length", 3.0),
        "tool_mass_kg": ("number", 2.5), "safety_factor": ("number", 2.5),
    },
    validators=(
        "form.tool_saddle_radius_ok",
        "form.tool_clearance_ok",
        "form.retention_angle_ok",
        "form.mouth_gap_ok",
        "form.ribs_connect_saddle_to_flange",
        "form.anchor_wall_strength_unverified",
        "topology.tool_void_open",
        "topology.single_connected_solid",
        "topology.ribs_present",
    ),
    apply=_wall_ring_mount,
    description="wall flange + fused C-ring tool saddle + gusset ribs "
                "(tool axis = X, prints upright)",
))


# -- revolve_band + cylindrical_z_mapping_v1 ------------------------------------

#: MVP guard: a cell wider than this fraction of the wall-midline radius
#: distorts too much when flattened onto its tangent plane.
CYL_MAX_CELL_FRACTION = 0.6


def _revolve_band(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A revolved band — ring, bushing, washer, bracelet, sleeve. The
    half-section (XZ plane, +u side of the axis) is a rounded rectangle;
    the compiler revolves it 360 degrees. size_clearance is added to the
    bore because a band is a CONTACT part (a finger, a shaft): declared
    inner_d is the nominal fit, the frame records the effective bore.

    The outer wall is a field canvas: a cylindrical_z_mapping_v1 window
    (axis Z only, one seam, full 360 band) with the seam and both edges as
    explicit keepout regions — the pattern math stays honest and visible."""
    from .part import FaceWindow
    from .regions import Rect2D as _Rect2D

    if state.section is not None:
        raise RecipeError("revolve_band must be the (single) base op")
    inner_d, height, wall = p["inner_d"], p["height"], p["wall"]
    clearance = p["size_clearance"]
    if wall < 1.5:
        raise RecipeError(
            f"wall {wall:g} < 1.5 — too thin for a through-cut band"
        )
    inner_d_eff = inner_d + clearance
    inner_r = inner_d_eff / 2.0
    outer_r = inner_r + wall
    corner_r = min(p["corner_r"], wall * 0.45, height * 0.3)
    state.section = SectionProfile(
        name="recipe_revolve",
        outer=rounded_rect_loop(inner_r, 0.0, outer_r, height, corner_r),
        plane="XZ",
        width_axis="Y",
    )
    state.kind = "profile_revolve"
    state.width = 2.0 * outer_r  # reporting; the compiler revolves
    r_mid = (inner_r + outer_r) / 2.0
    seam = p["seam_keepout"]
    margin = p["edge_margin"]
    circumference = 2.0 * math.pi * r_mid
    if circumference - 2.0 * seam < 10.0 or height - 2.0 * margin < 2.0:
        raise RecipeError("band too small for a patterned window")
    name = op_id or "band"
    state.regions.extend([
        Region("band_outer_surface", RegionRole.AESTHETIC_LIGHTENING,
               Box3(-outer_r, -outer_r, 0.0, outer_r, outer_r, height)),
        Region("bore_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(-inner_r, -inner_r, 0.0, inner_r, inner_r, height)),
        # Edge and seam keepouts are REAL regions — the honesty/region
        # lenses show them, and the field math is checked against them.
        Region("top_edge_keepout", RegionRole.HIGH_STRESS_REGION,
               Box3(-outer_r, -outer_r, height - margin, outer_r, outer_r, height)),
        Region("bottom_edge_keepout", RegionRole.HIGH_STRESS_REGION,
               Box3(-outer_r, -outer_r, 0.0, outer_r, outer_r, margin)),
        Region("seam_keepout", RegionRole.HIGH_STRESS_REGION,
               Box3(r_mid - wall, -seam, 0.0, outer_r + 1.0, seam, height)),
    ])
    # The cylindrical window in LOCAL (arc, height) coords; the seam sits
    # at theta=0, so the window starts past it and ends before it wraps.
    state.datums["axis"] = {"at": [0.0, 0.0, height / 2.0], "rotate": [0.0, 0.0, 0.0]}
    window = _Rect2D(seam, margin, circumference - seam, height - margin)
    state.frame.update(
        inner_d=inner_d, inner_d_effective=inner_d_eff,
        inner_r=inner_r, outer_r=outer_r, wall=wall,
        band_h=height, band_z0=0.0, band_z1=height,
        cyl_r_mid=r_mid,
        # the revolve probes read these names (cup convention):
        exit_r=inner_r, height=height, axis_clear_r=inner_r,
    )
    state.windows["band_outer_surface"] = FaceWindow(
        origin=(0.0, 0.0, 0.0), tilt_deg=0.0,
        window=window, depth=wall,
        keepouts=(),
        mapping="cylindrical", cyl_center=(0.0, 0.0),
        cyl_r=r_mid, cyl_r_outer=outer_r, cyl_z0=0.0,
        note="cylindrical_z_mapping_v1: axis Z, one seam at theta=0",
    )


_register(RecipeOpDecl(
    name="revolve_band",
    kind="base",
    params={
        "inner_d": ("length", None), "height": ("length", None),
        "wall": ("length", 2.2), "corner_r": ("length", 0.8),
        "size_clearance": ("length", 0.25),
        "seam_keepout": ("length", 2.0), "edge_margin": ("length", 0.9),
    },
    validators=(
        "form.revolve_profile_clear_of_axis",
        "topology.revolve_cavity_open",
        "topology.single_connected_solid",
    ),
    apply=_revolve_band,
    description="revolved band (ring/bushing/washer/bracelet) with a "
                "cylindrical field canvas on the outer wall",
))


# -- split branch clamp (Bio-1, docs/BIOMORPHIC.md) ------------------------------


def _clamp_common(state: RecipeState, p: dict[str, Any]) -> Any:
    from .profiles_clamp import ClampHalfParams

    if state.section is not None:
        raise RecipeError("a clamp half must be the (single) base op")
    return ClampHalfParams(
        branch_d=p["branch_d"], gap=p["gap"], flange_t=p["flange_t"],
        bolt_y=p["bolt_y"], edge_m=p["edge_m"], wall=p["wall"],
        corner_r=p["corner_r"], land_angle=p["land_angle"],
        land_w=p["land_w"], pad_recess=p["pad_recess"],
        base_t=p.get("base_t", 8.0), top_t=p.get("top_t", 20.0),
        rail_w=p.get("rail_w", 20.0), rail_h=p.get("rail_h", 6.0),
        rail_angle=p.get("rail_angle", 10.0),
    )


def _clamp_finish(
    state: RecipeState, p: dict[str, Any], profile: Any, f: dict[str, float]
) -> None:
    """Shared tail of both halves: section, outline frame (in the Z-hole
    plane: x = extrusion axis, y = profile u), print orientation."""
    state.section = profile
    state.width = p["clamp_w"]
    state.kind = "section_extrude"
    state.print_orientation = "side_profile"
    state.frame.update(f)
    state.frame.update(
        outline_u0=0.0, outline_v0=-f["wing_u_out"],
        outline_u1=p["clamp_w"], outline_v1=f["wing_u_out"],
        outline_corner_r=0.0,
    )


def _clamp_bio_canvas(
    state: RecipeState, p: dict[str, Any], profile: Any, f: dict[str, float]
) -> None:
    """Publish the outer_shell as a developable ``profile_surface`` canvas
    (Bio-4M stage B) — the pattern of ``_revolve_band``'s cylindrical window,
    now the section unrolled along the extrusion. The bio applicator grows
    ribs + RECESSED organic windows there; a through-cut would breach the
    saddle, so the op computes ``safe_recess`` = the min wall from the canvas
    to the saddle circle minus a residual skin margin (the ONE internal
    feature sharing the base op's frame; the axial channel and cord slots sit
    farther out or are masked) and publishes it as FaceWindow.depth."""
    from .exoskeleton.profile_surface import profile_surface_canvas
    from .part import FaceWindow
    from .regions import Rect2D as _Rect2D, Region2D

    width = p["clamp_w"]
    canvas = profile_surface_canvas(profile.outer, width)
    surface = canvas.surface
    s0, s1 = canvas.s0, canvas.s1
    # seam MUST sit off the canvas (inside the mate/saddle block) — a rib
    # graph never crosses a discontinuity.
    if not (canvas.seam_s > s1 - 1e-6):
        raise RecipeError("profile_surface seam landed on the canvas")
    edge = 3.0
    win_s0, win_s1 = s0 + edge, s1 - edge
    x0, x1 = edge, width - edge
    if win_s1 <= win_s0 + 1.0 or x1 <= x0 + 1.0:
        return  # body too small for a bio skin — leave the region window-less
    window = _Rect2D(win_s0, x0, win_s1, x1)

    scz, sr = f["saddle_cz"], f["saddle_r"]
    wall_margin = p.get("window_wall", 1.2)
    min_wall = math.inf
    for s, (u, v) in zip(surface.s_breaks, surface.points):
        if s < s0 - 1e-9 or s > s1 + 1e-9:
            continue
        min_wall = min(min_wall, abs(math.hypot(u, v - scz) - sr))
    if not math.isfinite(min_wall):
        min_wall = wall_margin + 0.8
    safe_recess = max(0.8, min_wall - wall_margin)
    cap = p.get("window_depth", 0.0)
    if cap and cap > 0.0:
        safe_recess = min(safe_recess, cap)

    keepouts: list[Region2D] = []
    if canvas.rail_interval is not None:
        r_lo, r_hi = canvas.rail_interval
        k_lo, k_hi = max(win_s0, r_lo - 2.0), min(win_s1, r_hi + 2.0)
        if k_hi > k_lo + 1e-6:
            keepouts.append(Region2D(
                "rail_keepout", RegionRole.MOUNTING_SURFACE,
                _Rect2D(k_lo, x0, k_hi, x1)))

    state.windows["outer_shell"] = FaceWindow(
        origin=(0.0, 0.0, 0.0), tilt_deg=0.0,
        window=window, depth=safe_recess,
        keepouts=tuple(keepouts),
        mapping="profile_surface", surface=surface,
        note="profile_surface (Bio-4M stage B): developable section-sweep; "
             "organic windows are RECESSED (through-cuts would breach the "
             "saddle/channel)",
    )
    state.frame.update(
        skin_safe_recess=safe_recess,
        skin_canvas_s0=s0, skin_canvas_s1=s1,
        skin_canvas_span=s1 - s0, skin_seam_s=canvas.seam_s,
        skin_total_s=surface.total_s,
    )
    if p.get("skin_depth", 0.0):
        state.frame["skin_depth"] = p["skin_depth"]


def _clamp_half_lower(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Lower half of the split branch clamp: base slab, open saddle notch
    in the mating (top) edge, wing flanges carrying the bolt columns.

    The ``clamp_mate`` datum bakes the compression gap in: it sits at
    ``mate_z + gap`` — joints land datum-on-datum and cannot express an
    offset, so the LOWER half's datum carries the gap and the upper half
    (modeled mating-face-down, datum at v=0) poses with rotate [0,0,0]."""
    from .profiles_clamp import build_clamp_lower_profile

    cp = _clamp_common(state, p)
    try:
        profile, f = build_clamp_lower_profile(cp)
    except ValueError as exc:
        raise RecipeError(f"clamp_half_lower: {exc}") from exc
    _clamp_finish(state, p, profile, f)
    _clamp_bio_canvas(state, p, profile, f)
    w, mh = p["clamp_w"], f["saddle_mouth_half"]
    state.regions.extend([
        Region("saddle_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -mh, f["saddle_apex_v"] - p["pad_recess"],
                    w, mh, f["mate_z"])),
        Region("outer_shell", RegionRole.EXOSKELETON_PANEL,
               Box3(0.0, -f["body_half"], 0.0, w, f["body_half"], f["wing_v0"])),
    ])
    state.datums["clamp_mate"] = {
        "at": [w / 2.0, 0.0, f["mate_z"] + p["gap"]], "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["branch_axis"] = {
        "at": [w / 2.0, 0.0, f["saddle_cz"]], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="clamp_half_lower",
    kind="base",
    params={
        "branch_d": ("length", None), "clamp_w": ("length", None),
        "gap": ("length", 3.0), "base_t": ("length", 8.0),
        "flange_t": ("length", 10.0), "bolt_y": ("length", None),
        "edge_m": ("length", 10.0), "wall": ("length", 4.0),
        "corner_r": ("length", 2.5), "land_angle": ("angle", 50.0),
        "land_w": ("length", 14.0), "pad_recess": ("length", 1.2),
        "window_wall": ("length", 1.2), "window_depth": ("length", 0.0),
        "skin_depth": ("length", 0.0),
    },
    validators=(
        "form.saddle_geometry_ok",
        "form.pad_lands_present",
        "topology.cavity_open",
        "topology.single_connected_solid",
    ),
    apply=_clamp_half_lower,
    description="lower split-clamp half: open branch saddle + bolt wings "
                "(X = branch axis, prints on its section)",
))


def _clamp_half_upper(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Upper half, modeled MATING-FACE-DOWN (mating plane at v=0, saddle
    notch in the bottom edge, dovetail rail on top) — the assembly poses it
    with rotate [0,0,0], no flip needed. Its ``clamp_mate`` datum sits ON
    the mating plane; the gap is baked into the LOWER half's datum."""
    from .profiles_clamp import build_clamp_upper_profile

    cp = _clamp_common(state, p)
    try:
        profile, f = build_clamp_upper_profile(cp)
    except ValueError as exc:
        raise RecipeError(f"clamp_half_upper: {exc}") from exc
    _clamp_finish(state, p, profile, f)
    _clamp_bio_canvas(state, p, profile, f)
    w, mh = p["clamp_w"], f["saddle_mouth_half"]
    state.regions.extend([
        Region("saddle_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -mh, 0.0, w, mh, f["saddle_apex_v"] + p["pad_recess"])),
        Region("outer_shell", RegionRole.EXOSKELETON_PANEL,
               Box3(0.0, -f["body_half"], f["flange_t"],
                    w, f["body_half"], f["body_top_v"])),
        Region("rail_interface", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -f["rail_top_w"] / 2.0 - 1.0, f["rail_v0"],
                    w, f["rail_top_w"] / 2.0 + 1.0, f["rail_v1"] + 0.5)),
    ])
    state.datums["clamp_mate"] = {
        "at": [w / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["branch_axis"] = {
        "at": [w / 2.0, 0.0, f["saddle_cz"]], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="clamp_half_upper",
    kind="base",
    params={
        "branch_d": ("length", None), "clamp_w": ("length", None),
        "gap": ("length", 3.0), "flange_t": ("length", 10.0),
        "bolt_y": ("length", None), "edge_m": ("length", 10.0),
        "wall": ("length", 4.0), "corner_r": ("length", 2.5),
        "land_angle": ("angle", 50.0), "land_w": ("length", 14.0),
        "pad_recess": ("length", 1.2), "top_t": ("length", 20.0),
        "rail_w": ("length", 20.0), "rail_h": ("length", 6.0),
        "rail_angle": ("angle", 10.0),
        "window_wall": ("length", 1.2), "window_depth": ("length", 0.0),
        "skin_depth": ("length", 0.0),
    },
    validators=(
        "form.saddle_geometry_ok",
        "form.pad_lands_present",
        "topology.cavity_open",
        "topology.single_connected_solid",
        "form.dovetail_rail_profile",
        "topology.rail_present",
    ),
    apply=_clamp_half_upper,
    description="upper split-clamp half, mating-face-down: saddle + wings + "
                "male dovetail rail on top",
))


def _axial_channel(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A through cable channel along the extrusion (branch) axis, open at
    both ends — verified void end to end by topology.bores_open and placed
    clear of the saddle/rail by form.clamp_channel_clear."""
    state.require_base("axial_channel")
    name = op_id or "channel"
    state.bores.append(
        BoreFeature(
            name=name, axis="X", center=(0.0, p["y"], p["z"]),
            d=p["d"], span=(0.0, state.width), overshoot=(1.0, 1.0),
        )
    )
    state.frame.update(channel_z=p["z"], channel_y=p["y"], channel_d=p["d"])


_register(RecipeOpDecl(
    name="axial_channel",
    kind="feature",
    params={
        "d": ("length", 10.0), "y": ("length", 0.0), "z": ("length", None),
    },
    validators=("form.clamp_channel_clear", "topology.bores_open"),
    apply=_axial_channel,
    description="through cable channel along the extrusion axis, open both ends",
))


def _cord_slot_pair(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Two through slots near the saddle center (shock cord / zip tie for
    mounting) — they exit INTO the saddle void through the mating plane.
    cx = 0 means the width center; the keepout check keeps them honest
    around the bolt columns."""
    state.require_base("cord_slot_pair")
    mate_z = state.frame.get("mate_z")
    if mate_z is None:
        raise RecipeError("cord_slot_pair needs a clamp_half base (mate_z)")
    cx = p["cx"] if abs(p["cx"]) > 1e-9 else state.width / 2.0
    half_l, half_w = p["slot_l"] / 2.0, p["slot_w"] / 2.0
    name = op_id or "cord_slots"
    for i, sy in enumerate((-p["spacing"] / 2.0, p["spacing"] / 2.0)):
        state.cutboxes.append(
            CutBoxFeature(
                name=f"{name}_{i}",
                box=Box3(cx - half_l, sy - half_w, -1.0,
                         cx + half_l, sy + half_w, mate_z + 1.0),
            )
        )
        state.frame[f"{name}_{i}_v"] = sy
    state.frame[f"{name}_l"] = p["slot_l"]
    state.frame[f"{name}_w"] = p["slot_w"]


_register(RecipeOpDecl(
    name="cord_slot_pair",
    kind="feature",
    params={
        "slot_l": ("length", 8.0), "slot_w": ("length", 4.0),
        "spacing": ("length", None), "cx": ("length", 0.0),
    },
    validators=("form.cuts_respect_keepouts", "topology.cutout_present"),
    apply=_cord_slot_pair,
    description="through cord/tie slot pair exiting into the saddle void",
))


def _forearm_cuff_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Wearable forearm cuff (wave P2): open C-ring sized from body_fit,
    strap tabs at the mouth tips, three recessed TPU pad lands, payload
    snap-C on top — ONE constant section, printed on its profile.

    The ``outer_aesthetic_shell`` region is RESERVED for the bio skin: no
    profile_surface FaceWindow is published in v1 (mirror _clamp_bio_canvas
    here once the Bio-4M stage-B canvas lands for two-cavity sections)."""
    from .profiles_wearable import CuffParams, build_forearm_cuff_profile

    if state.section is not None:
        raise RecipeError("forearm_cuff_body must be the (single) base op")
    cp = CuffParams(
        arm_circumference=p["arm_circumference"],
        arm_clearance=p["arm_clearance"], wall=p["wall"],
        arm_capture_deg=p["arm_capture_deg"], land_angle=p["land_angle"],
        land_w=p["land_w"], pad_recess=p["pad_recess"],
        comfort_edge_r=p["comfort_edge_r"], tab_t=p["tab_t"],
        tab_len=p["tab_len"], payload_d=p["payload_d"],
        payload_clearance=p["payload_clearance"],
        payload_arc_deg=p["payload_arc_deg"], clip_wall=p["clip_wall"],
        neck_drop=p["neck_drop"], payload_mount=p["payload_mount"],
        groove_top_w=p["groove_top_w"], groove_bottom_w=p["groove_bottom_w"],
        groove_depth=p["groove_depth"], crown_wall=p["crown_wall"],
        crown_floor=p["crown_floor"],
    )
    try:
        profile, f = build_forearm_cuff_profile(cp)
    except ValueError as exc:
        raise RecipeError(f"forearm_cuff_body: {exc}") from exc
    w = p["cuff_l"]
    state.section = profile
    state.width = w
    state.kind = "section_extrude"
    state.print_orientation = "side_profile"
    state.frame.update(f)
    v_ext = max(f["tab_u_out"], f["arm_r_outer"])
    state.frame.update(
        outline_u0=0.0, outline_v0=-v_ext, outline_u1=w, outline_v1=v_ext,
        outline_corner_r=0.0,
    )
    r_ai, r_ao = f["arm_r_inner"], f["arm_r_outer"]
    socket = "socket_top_v" in f
    if socket:
        ch, v_ct = f["crown_half_w"], f["socket_top_v"]
        state.regions.extend([
            Region("arm_contact", RegionRole.BODY_CONTACT_SURFACE,
                   Box3(0.0, -r_ai, f["arm_mouth_tip_v"] + 2.0, w, r_ai, r_ai)),
            Region("strap_land_left", RegionRole.MOUNTING_SURFACE,
                   Box3(0.0, -f["tab_u_out"], f["tab_v_bot"],
                        w, -f["tab_u_x"] - 1.0, f["tab_v_top"])),
            Region("strap_land_right", RegionRole.MOUNTING_SURFACE,
                   Box3(0.0, f["tab_u_x"] + 1.0, f["tab_v_bot"],
                        w, f["tab_u_out"], f["tab_v_top"])),
            # The whole socket crown is an interface keepout: nothing may
            # cut into the walls that retain the adapter foot.
            Region("socket_crown", RegionRole.INTERFACE_KEEPOUT,
                   Box3(0.0, -ch, f["crown_shoulder_v"], w, ch, v_ct)),
            Region("outer_aesthetic_shell", RegionRole.EXOSKELETON_PANEL,
                   Box3(0.0, -r_ao, 0.0, w, r_ao, f["crown_shoulder_v"])),
        ])
        state.datums["arm_axis"] = {
            "at": [w / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0],
        }
        state.datums["payload_socket"] = {
            "at": [w / 2.0, 0.0, v_ct], "rotate": [0.0, 0.0, 0.0],
        }
        return
    r_pi, r_po = f["payload_r_inner"], f["payload_r_outer"]
    p_cv, n = f["payload_cv"], f["neck_half_w"]
    p_h = (360.0 - f["payload_arc_deg"]) / 2.0
    tip_u = r_pi * math.cos(math.radians(90.0 - p_h))
    tip_v = p_cv + r_pi * math.sin(math.radians(90.0 - p_h))
    tip_o = p_cv + r_po * math.sin(math.radians(90.0 - p_h))
    state.regions.extend([
        # The BODY_CONTACT keepout deliberately starts 2 mm ABOVE the mouth
        # tips: tabs and strap slots live at/below tip level, so the coarse
        # AABB never vetoes a legal strap cut; the precise circle guard is
        # form.strap_access_ok + the applicator's own check.
        Region("arm_contact", RegionRole.BODY_CONTACT_SURFACE,
               Box3(0.0, -r_ai, f["arm_mouth_tip_v"] + 2.0, w, r_ai, r_ai)),
        # Strap windows start OUTSIDE the ring wall (tab_u_x, the chord-
        # mouth junction) — the modifier can only pierce clear tab plate.
        Region("strap_land_left", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -f["tab_u_out"], f["tab_v_bot"],
                    w, -f["tab_u_x"] - 1.0, f["tab_v_top"])),
        Region("strap_land_right", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, f["tab_u_x"] + 1.0, f["tab_v_bot"],
                    w, f["tab_u_out"], f["tab_v_top"])),
        Region("payload_saddle", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -r_pi, p_cv - r_pi, w, r_pi, p_cv + r_pi)),
        Region("clip_flexure_left", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, -tip_u - 3.0, tip_v - 3.0, w, -tip_u + 3.0,
                    tip_o + 2.0)),
        Region("clip_flexure_right", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, tip_u - 3.0, tip_v - 3.0, w, tip_u + 3.0,
                    tip_o + 2.0)),
        Region("outer_aesthetic_shell", RegionRole.EXOSKELETON_PANEL,
               Box3(0.0, -r_ao, 0.0, w, r_ao,
                    math.sqrt(r_ao * r_ao - n * n))),
    ])
    state.datums["arm_axis"] = {
        "at": [w / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0],
    }
    state.datums["payload_axis"] = {
        "at": [w / 2.0, 0.0, p_cv], "rotate": [0.0, 0.0, 0.0],
    }


_register(RecipeOpDecl(
    name="forearm_cuff_body",
    kind="base",
    params={
        "arm_circumference": ("length", None), "cuff_l": ("length", None),
        "arm_clearance": ("length", 6.0), "wall": ("length", 4.0),
        "arm_capture_deg": ("angle", 240.0), "land_angle": ("angle", 45.0),
        "land_w": ("length", 14.0), "pad_recess": ("length", 1.5),
        "comfort_edge_r": ("length", 2.0), "tab_t": ("length", 4.0),
        "tab_len": ("length", 26.0), "payload_d": ("length", 25.0),
        "payload_clearance": ("length", 0.3),
        "payload_arc_deg": ("angle", 240.0), "clip_wall": ("length", 3.0),
        "neck_drop": ("length", 4.0), "payload_mount": ("choice", "snap_clip"),
        "groove_top_w": ("length", 12.0),
        "groove_bottom_w": ("length", 17.0),
        "groove_depth": ("length", 6.0), "crown_wall": ("length", 3.5),
        "crown_floor": ("length", 3.0),
    },
    validators=(
        "form.body_clearance_ok",
        "form.arm_mouth_dons_ok",
        "form.comfort_edge_radius_ok",
        "form.pad_recess_exists",
        "form.payload_mount_not_on_skin_side",
        "form.payload_retention_ok",
        "topology.cavity_open",
        "topology.payload_void_open",
        "topology.single_connected_solid",
    ),
    apply=_forearm_cuff_body,
    description="wearable forearm cuff: body_fit C-ring + strap tabs + "
                "TPU pad lands + payload snap-C (X = forearm axis, "
                "prints on its section)",
))

# Vertical Farm Pack ops live in their own module (this file is long
# enough); importing it runs its _register calls into the same registry.
from . import recipe_ops_water  # noqa: E402,F401


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
