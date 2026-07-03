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

from ..core.fasteners import screw_spec
from .part import CutBoxFeature, HoleFeature
from .patterns import bolt_circle_centers, holes_from_centers, line_centers
from .profiles_plate import rounded_rect_loop
from .regions import Box3, Region
from .section import SectionProfile
from ..product.archetype import RegionRole

KEEPOUT_CLEARANCE = 2.0


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
    regions: list[Region] = field(default_factory=list)
    frame: dict[str, float] = field(default_factory=dict)

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


# -- features -----------------------------------------------------------------


def _hole_pattern(
    state: RecipeState, p: dict[str, Any], op_id: str, *, countersunk: bool
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
    holes = holes_from_centers(centers, t, t, screw, p["cs_face"])
    if not countersunk:
        holes = [
            HoleFeature(at=h.at, screw=h.screw, through=h.through, countersink=False)
            for h in holes
        ]
    state.holes.extend(holes)
    head_r = screw_spec(screw)["head"] / 2.0
    name = op_id or "holes"
    for i, (hx, hy) in enumerate(centers):
        state.regions.append(
            Region(
                f"{name}_{i}", RegionRole.FASTENER_KEEPOUT,
                Box3(hx - head_r - KEEPOUT_CLEARANCE, hy - head_r - KEEPOUT_CLEARANCE,
                     0.0,
                     hx + head_r + KEEPOUT_CLEARANCE, hy + head_r + KEEPOUT_CLEARANCE,
                     t),
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
