"""PartForm — the complete Form IR of one part: everything the CAD compiler
consumes and everything the validators measure, in one serializable-shaped
object. ``compile_part`` never invents positions: holes, field windows,
blend zones and datums all come from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .regions import Box3, Rect2D, Region, Region2D
from .section import SectionProfile
from .style import SurfaceStyle


@dataclass(frozen=True)
class PlateFeature:
    """A rounded-rectangle plate in the XY plane (the flange)."""

    name: str
    x0: float
    y0: float
    x1: float
    y1: float
    z_bottom: float
    thickness: float
    corner_r: float = 2.0

    @property
    def z_top(self) -> float:
        return self.z_bottom + self.thickness


@dataclass(frozen=True)
class HoleFeature:
    """A vertical fastener hole through a plate, axis -Z from the top face.

    ``countersink_face`` names where the screw HEAD seats: for an under-desk
    part the screw enters from below, so the recess belongs on the bottom
    face — the desk-side face must stay flat.
    """

    at: tuple[float, float, float]  # top-face center (x, y, z_top)
    screw: str
    through: float  # cut depth
    countersink: bool = True
    countersink_face: str = "bottom"  # "bottom" | "top"


@dataclass(frozen=True)
class FieldFeature:
    """A resolved perforation field: explicit cell centers, already
    filtered against every keepout — countable, checkable, no guessing."""

    plane_z: float  # top face z the cells are cut from
    centers: tuple[tuple[float, float], ...]
    cell: float  # hexagon across-flats size
    depth: float
    pattern: str = "hex"
    window: Rect2D | None = None
    keepouts: tuple[Region2D, ...] = ()


@dataclass(frozen=True)
class BlendDirective:
    """A 3D-only blend: edges inside ``zone`` get ``radius``, with the
    safe-fillet ladder as fallback."""

    zone: Box3
    radius: float
    fallback_ladder: tuple[float, ...] = ()


@dataclass
class PartForm:
    name: str
    params: dict[str, float]
    frame: dict[str, float]
    section: SectionProfile
    width: float
    style: SurfaceStyle
    plates: list[PlateFeature] = field(default_factory=list)
    holes: list[HoleFeature] = field(default_factory=list)
    fields: list[FieldFeature] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    blends: list[BlendDirective] = field(default_factory=list)
    datums: dict[str, dict[str, Any]] = field(default_factory=dict)

    def region(self, name: str) -> Region | None:
        for r in self.regions:
            if r.name == name:
                return r
        return None
