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
    """A resolved perforation field, already filtered against every keepout
    — countable, checkable, no guessing. Two cell spellings: hex/slot
    ``centers`` (uniform cutter per center) or explicit ``polygons``
    (voronoi and friends; convex, one cutter per polygon)."""

    plane_z: float  # top face z the cells are cut from
    centers: tuple[tuple[float, float], ...]
    cell: float  # hexagon across-flats size (centers mode)
    depth: float
    pattern: str = "hex"
    window: Rect2D | None = None
    keepouts: tuple[Region2D, ...] = ()
    #: Explicit convex cell polygons in (x, y); used when pattern="voronoi"
    #: or "slots". Vertices are final — the ligament shrink already happened.
    polygons: tuple[tuple[tuple[float, float], ...], ...] = ()
    #: Guaranteed minimum web between cells (validated, not hoped).
    min_ligament: float = 0.0


@dataclass(frozen=True)
class BoreFeature:
    """An axis-aligned cylindrical cut (a wiring channel leg, a central
    bore, a blind pocket). ``span`` is the axis-coordinate range of the
    cut; ``overshoot`` extends the cutter past each span end — (1, 0) makes
    a blind pocket entered from the low end. Verification reuses the
    swept-cylinder channel probe along the same span."""

    name: str
    axis: str  # "X" | "Y" | "Z"
    center: tuple[float, float, float]  # any point on the bore axis
    d: float
    span: tuple[float, float]
    overshoot: tuple[float, float] = (1.0, 1.0)

    def path(self, probe_overshoot: float = 1.0) -> list[tuple[float, float, float]]:
        """The probe polyline along the bore. A blind end (overshoot 0) is
        probed slightly SHORT of the floor so the probe measures the pocket,
        not the material beneath it."""
        x, y, z = self.center
        lo = self.span[0] - (probe_overshoot if self.overshoot[0] > 0 else -0.4)
        hi = self.span[1] + (probe_overshoot if self.overshoot[1] > 0 else -0.4)
        if self.axis == "X":
            return [(lo, y, z), (hi, y, z)]
        if self.axis == "Y":
            return [(x, lo, z), (x, hi, z)]
        return [(x, y, lo), (x, y, hi)]


@dataclass(frozen=True)
class CutBoxFeature:
    """An axis-aligned box cut (a charging cutout, a notch). The box must be
    finite; keepout respect is validated at the IR level before any CAD."""

    name: str
    box: Box3

    def __post_init__(self) -> None:
        if not self.box.finite:
            raise ValueError(f"CutBoxFeature {self.name!r} box must be finite")


@dataclass(frozen=True)
class RibFeature:
    """An ADDITIVE bar welded onto a face — the additive half of the
    modifier kernel (stiffening ribs, bosses). The box is the rib's full
    extent; it must overlap its host by the weld rule and is verified
    present by a solid-fraction probe."""

    name: str
    box: Box3

    def __post_init__(self) -> None:
        if not self.box.finite:
            raise ValueError(f"RibFeature {self.name!r} box must be finite")


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
    #: How the section becomes a solid: "section_extrude" | "profile_revolve".
    kind: str = "section_extrude"
    plates: list[PlateFeature] = field(default_factory=list)
    holes: list[HoleFeature] = field(default_factory=list)
    bores: list[BoreFeature] = field(default_factory=list)
    cutboxes: list[CutBoxFeature] = field(default_factory=list)
    ribs: list[RibFeature] = field(default_factory=list)
    fields: list[FieldFeature] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    blends: list[BlendDirective] = field(default_factory=list)
    datums: dict[str, dict[str, Any]] = field(default_factory=dict)

    def region(self, name: str) -> Region | None:
        for r in self.regions:
            if r.name == name:
                return r
        return None
