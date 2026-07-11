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
    FunnelCutFeature,
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
    funnel_cuts: list[FunnelCutFeature] = field(default_factory=list)
    bores: list[BoreFeature] = field(default_factory=list)
    ribs: list[RibFeature] = field(default_factory=list)
    plates: list[PlateFeature] = field(default_factory=list)
    pins: list[PinFeature] = field(default_factory=list)
    fields: list[Any] = field(default_factory=list)
    text_reliefs: list[Any] = field(default_factory=list)
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


