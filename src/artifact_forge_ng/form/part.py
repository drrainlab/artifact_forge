"""PartForm — the complete Form IR of one part: everything the CAD compiler
consumes and everything the validators measure, in one serializable-shaped
object. ``compile_part`` never invents positions: holes, field windows,
blend zones and datums all come from here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .exoskeleton.ir import ExoskeletonIR, ProfileSurfaceMap
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
    #: "cone" = countersink (flat-head), "cylinder" = counterbore
    #: (socket-cap head recess).
    head_style: str = "cone"


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
    #: Oriented field (a tilted face): cell coords are LOCAL (a, b); the
    #: local frame is a rotation about the +X axis by ``tilt_deg`` followed
    #: by a translation to ``origin``. None = legacy horizontal field.
    origin: tuple[float, float, float] | None = None
    tilt_deg: float = 0.0
    #: cylindrical_z_mapping_v1 — cells live on a Z-axis cylinder wall
    #: (a ring band, a cup skirt): local a = ARC LENGTH at cyl_r (the wall
    #: midline), b = height above cyl_z0, n = radial depth INWARD from the
    #: OUTER surface. Deliberate MVP limits: axis Z only, one seam, full
    #: 360 band, no periodic wrapping.
    mapping: str = "planar"  # "planar" | "cylindrical" | "profile_surface"
    cyl_center: tuple[float, float] = (0.0, 0.0)
    cyl_r: float = 0.0
    cyl_r_outer: float = 0.0
    cyl_z0: float = 0.0
    #: The developable surface when ``mapping == "profile_surface"`` — cell
    #: coords are then ``(s, x)`` unrolled from the section contour.
    surface: ProfileSurfaceMap | None = None

    def local_to_world(self, a: float, b: float, n: float = 0.0) -> tuple[float, float, float]:
        """Map local (a, b, n) — in-plane coords + offset ALONG the cut
        direction (into the material) — to world XYZ."""
        import math

        if self.mapping == "profile_surface" and self.surface is not None:
            return self.surface.to_world(a, b, n)
        if self.mapping == "cylindrical":
            theta = a / self.cyl_r
            r = self.cyl_r_outer - n
            cx, cy = self.cyl_center
            return (
                cx + r * math.cos(theta),
                cy + r * math.sin(theta),
                self.cyl_z0 + b,
            )
        if self.origin is None:
            return (a, b, self.plane_z - n)
        t = math.radians(self.tilt_deg)
        # local X -> world X; local Y -> (0, cos t, sin t);
        # local Z (cut direction, into material) -> (0, -sin t, cos t)
        ox, oy, oz = self.origin
        return (
            ox + a,
            oy + b * math.cos(t) - n * math.sin(t),
            oz + b * math.sin(t) + n * math.cos(t),
        )


@dataclass(frozen=True)
class BoreFeature:
    """An axis-aligned cylindrical cut (a wiring channel leg, a central
    bore, a blind pocket). ``span`` is the axis-coordinate range of the
    cut; ``overshoot`` extends the cutter past each span end — (1, 0) makes
    a blind pocket entered from the low end. Verification reuses the
    swept-cylinder channel probe along the same span.

    ``roof`` (VF-4.1): a HORIZONTAL bore (axis X/Y) printed as-modeled has
    a bridged circular ceiling; ``"teardrop"`` replaces the top quarter
    with two 45-degree tangent chords meeting at a peak d/2*sqrt(2) above
    center — self-supporting on FDM. The teardrop volume is a superset of
    the cylinder, so every swept-cylinder probe stays valid. Ignored for
    axis Z (a vertical bore has no ceiling)."""

    name: str
    axis: str  # "X" | "Y" | "Z"
    center: tuple[float, float, float]  # any point on the bore axis
    d: float
    span: tuple[float, float]
    overshoot: tuple[float, float] = (1.0, 1.0)
    roof: str = "round"  # "round" | "teardrop" (horizontal axes only)

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
class ChannelCutFeature:
    """An open U-channel cut from the top face: constant width, rounded
    bottom corners, floor sloping LINEARLY along the flow axis while the
    body stays level — the water rail's transient path. v1 limits: flow
    axis Y only, straight run, opens through both end faces (the cutter
    overshoots, so the water always has an exit by construction).

    ``y0`` is the inlet end, ``y1`` the outlet end; ``depth_start`` /
    ``depth_end`` are floor depths below ``z_top`` at those stations, and
    the slope is their linear interpolation (extrapolated through the
    overshoot so the floor plane is exact past the faces)."""

    name: str
    center_x: float
    y0: float  # inlet station on the flow axis
    y1: float  # outlet station (y0 != y1; either ordering is legal)
    z_top: float  # entry plane — the rail top face
    width: float
    depth_start: float  # floor depth at y0 (shallow, inlet)
    depth_end: float  # floor depth at y1 (deep, outlet)
    bottom_r: float = 1.2
    axis: str = "Y"

    def __post_init__(self) -> None:
        if self.axis != "Y":
            raise ValueError(f"ChannelCutFeature {self.name!r}: v1 supports axis Y only")
        if abs(self.y1 - self.y0) < 1e-9:
            raise ValueError(f"ChannelCutFeature {self.name!r} needs a nonzero flow span")
        if self.width <= 0 or self.depth_start <= 0 or self.depth_end <= 0:
            raise ValueError(f"ChannelCutFeature {self.name!r} needs positive width/depths")
        if self.bottom_r < 0 or 2.0 * self.bottom_r > self.width + 1e-9:
            raise ValueError(f"ChannelCutFeature {self.name!r}: bottom_r must fit the width")

    def depth_at(self, y: float) -> float:
        """Floor depth below z_top at station y — linear, extrapolates."""
        t = (y - self.y0) / (self.y1 - self.y0)
        return self.depth_start + t * (self.depth_end - self.depth_start)

    def floor_z_at(self, y: float) -> float:
        return self.z_top - self.depth_at(y)

    @property
    def slope_deg(self) -> float:
        import math

        rise = abs(self.depth_end - self.depth_start)
        run = abs(self.y1 - self.y0)
        return math.degrees(math.atan(rise / run))

    def centerline(self, lift: float = 1.0, stations: int = 9) -> list[tuple[float, float, float]]:
        """Sampled probe polyline offset ``lift`` above the floor — the
        water path itself (lift > 0) or the material beneath it (lift < 0)."""
        n = max(2, stations)
        ys = [self.y0 + k / (n - 1) * (self.y1 - self.y0) for k in range(n)]
        return [(self.center_x, y, self.floor_z_at(y) + lift) for y in ys]


@dataclass(frozen=True)
class FaceWindow:
    """An ORIENTED modifier canvas the builder declares for a region whose
    face is not horizontal (the phone stand's tilted back). Local frame:
    rotate about +X by ``tilt_deg``, translate to ``origin``; local (a, b)
    span the face, the cut direction is the face's inward normal.
    tilt_deg = 90 is a vertical face; 0 degenerates to a horizontal one."""

    origin: tuple[float, float, float]
    tilt_deg: float
    window: Rect2D  # in local (a, b)
    depth: float  # material thickness along the inward normal
    keepouts: tuple[Region2D, ...] = ()  # in local (a, b)
    #: False when the face exists but cannot take a flat field right now
    #: (e.g. the biomorphic bow curved it) — applicators fail honestly.
    usable: bool = True
    note: str = ""
    #: cylindrical_z_mapping_v1 (see FieldFeature): a Z-axis cylinder wall
    #: window; local a = arc length at cyl_r, b = height above cyl_z0.
    #: "profile_surface" (Bio-4M stage B): a developable section-sweep; local
    #: (a, b) = (s, x), keepouts/window in that unrolled frame.
    mapping: str = "planar"
    cyl_center: tuple[float, float] = (0.0, 0.0)
    cyl_r: float = 0.0
    cyl_r_outer: float = 0.0
    cyl_z0: float = 0.0
    #: The developable surface when ``mapping == "profile_surface"``.
    surface: ProfileSurfaceMap | None = None


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
class PinFeature:
    """An ADDITIVE alignment/press-fit pin: a cylinder welded onto a face,
    rising along ``axis`` from ``start``. The mating part receives it in a
    bore whose diameter is pin_d minus the declared interference —
    verified by the press-fit joints in the assembled pose.

    Legacy spelling (axis Z): ``at=(x, y)`` + ``z0``. Axis X/Y pins (a
    split part's butt-joint pins on an end face) give the full ``start``
    point instead."""

    name: str
    at: tuple[float, float]  # (x, y) of the pin axis for axis="Z"
    d: float
    z0: float  # weld start along the axis (should overlap the host)
    length: float
    axis: str = "Z"

    def __post_init__(self) -> None:
        if self.d <= 0 or self.length <= 0:
            raise ValueError(f"PinFeature {self.name!r} needs positive d/length")
        if self.axis not in ("X", "Y", "Z"):
            raise ValueError(f"PinFeature {self.name!r} axis must be X/Y/Z")

    def start_point(self) -> tuple[float, float, float]:
        """Axis-start in world coords: `at` holds the two off-axis coords
        in world order, z0 the axis coordinate."""
        a, b = self.at
        if self.axis == "Z":
            return (a, b, self.z0)
        if self.axis == "X":
            return (self.z0, a, b)
        return (a, self.z0, b)

    def end_point(self) -> tuple[float, float, float]:
        x, y, z = self.start_point()
        if self.axis == "Z":
            return (x, y, z + self.length)
        if self.axis == "X":
            return (x + self.length, y, z)
        return (x, y + self.length, z)


@dataclass(frozen=True)
class LoftFeature:
    """An ADDITIVE lofted beam: a rounded transition from a root rectangle
    to a tip rectangle along +Z (the tapered-arm builder). Welded onto the
    base like a rib; verified by ``topology.arm_reaches_tip`` — a loft that
    fell off or never made it to its tip is a missing arm, not a style
    defect."""

    name: str
    base_center: tuple[float, float]  # (x, y) of the root rectangle center
    z0: float
    length: float
    root: tuple[float, float]  # (l, w) at z0
    tip: tuple[float, float]  # (l, w) at z0 + length

    def __post_init__(self) -> None:
        if self.length <= 0:
            raise ValueError(f"LoftFeature {self.name!r} needs positive length")
        if self.tip[0] > self.root[0] + 1e-9 or self.tip[1] > self.root[1] + 1e-9:
            raise ValueError(
                f"LoftFeature {self.name!r} must taper (tip <= root) so the "
                "printed arm is self-supporting"
            )


@dataclass(frozen=True)
class BlendDirective:
    """A 3D-only blend: edges inside ``zone`` get ``radius``, with the
    safe-fillet ladder as fallback."""

    zone: Box3
    radius: float
    fallback_ladder: tuple[float, ...] = ()


@dataclass(frozen=True)
class FunnelCutFeature:
    """A downward-converging (possibly skewed) frustum SUBTRACTED from the
    body: a wide top opening ``top`` centred at ``top_center`` / ``z_top``
    tapers to a small bottom mouth ``bottom`` centred at ``bottom_center`` /
    ``z_bottom``. The bottom rectangle must lie WITHIN the top rectangle's
    XY footprint (so every wall slopes inward-and-down) and ``z_top`` sits
    above ``z_bottom``. Subtracting it carves a sloped floor that drains
    toward the mouth from every side — the collector's radial sump feed
    (VF-8). This is the kernel's first floor that slopes in BOTH X and Y
    (``ChannelCutFeature`` slopes along Y only); the offset centres let the
    mouth sit at a back-corner drain while the opening spans the tray. Built
    as a ruled loft (bottom rect → top rect), the channel cutter's mechanism."""

    name: str
    bottom_center: tuple[float, float]  # (x, y) of the mouth
    top_center: tuple[float, float]  # (x, y) of the opening
    z_top: float  # wide opening plane (the tray floor)
    z_bottom: float  # narrow mouth plane (the sump)
    top: tuple[float, float]  # (lx, ly) opening at z_top
    bottom: tuple[float, float]  # (lx, ly) mouth at z_bottom

    def __post_init__(self) -> None:
        if self.z_top <= self.z_bottom + 1e-9:
            raise ValueError(
                f"FunnelCutFeature {self.name!r}: z_top must sit above z_bottom")
        if self.bottom[0] <= 0.0 or self.bottom[1] <= 0.0:
            raise ValueError(
                f"FunnelCutFeature {self.name!r} needs a positive mouth")
        # the mouth footprint must be enclosed by the opening footprint
        bx0 = self.bottom_center[0] - self.bottom[0] / 2.0
        bx1 = self.bottom_center[0] + self.bottom[0] / 2.0
        by0 = self.bottom_center[1] - self.bottom[1] / 2.0
        by1 = self.bottom_center[1] + self.bottom[1] / 2.0
        tx0 = self.top_center[0] - self.top[0] / 2.0
        tx1 = self.top_center[0] + self.top[0] / 2.0
        ty0 = self.top_center[1] - self.top[1] / 2.0
        ty1 = self.top_center[1] + self.top[1] / 2.0
        if not (tx0 - 1e-9 <= bx0 and bx1 <= tx1 + 1e-9
                and ty0 - 1e-9 <= by0 and by1 <= ty1 + 1e-9):
            raise ValueError(
                f"FunnelCutFeature {self.name!r} must CONVERGE downward — the "
                "mouth must lie within the opening footprint")

    @property
    def depth(self) -> float:
        return self.z_top - self.z_bottom


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
    #: How the part should sit on the print bed. "as_modeled" exports in the
    #: part frame; "side_profile" bakes a rotation into the export so the
    #: SECTION lies on the bed and the extrusion axis (X) points up — a
    #: constant-section extrusion printed this way has zero overhangs by
    #: construction. Validators always measure in the part frame; only the
    #: exported STL/STEP are rotated.
    print_orientation: str = "as_modeled"
    plates: list[PlateFeature] = field(default_factory=list)
    holes: list[HoleFeature] = field(default_factory=list)
    bores: list[BoreFeature] = field(default_factory=list)
    cutboxes: list[CutBoxFeature] = field(default_factory=list)
    channels: list[ChannelCutFeature] = field(default_factory=list)
    funnel_cuts: list[FunnelCutFeature] = field(default_factory=list)
    ribs: list[RibFeature] = field(default_factory=list)
    lofts: list[LoftFeature] = field(default_factory=list)
    pins: list[PinFeature] = field(default_factory=list)
    fields: list[FieldFeature] = field(default_factory=list)
    #: Oriented modifier canvases, keyed by the region name they serve.
    windows: dict[str, FaceWindow] = field(default_factory=dict)
    regions: list[Region] = field(default_factory=list)
    blends: list[BlendDirective] = field(default_factory=list)
    datums: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Bio-2 exoskeleton intent (rib graph + organic windows + masks) —
    #: attached by apply_biomorphic_exoskeleton, measured by the
    #: form.rib_* checks, materialized in CAD by Bio-3.
    exoskeleton: ExoskeletonIR | None = None

    def region(self, name: str) -> Region | None:
        for r in self.regions:
            if r.name == name:
                return r
        return None
