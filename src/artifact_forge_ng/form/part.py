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

    ``roof``: a HORIZONTAL bore (axis X/Y) printed as-modeled has
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
    #: Declared coaxial bore INSIDE the pin (a socket arm's barrel): the
    #: pin is a tube by design, so the presence probe measures its WALL
    #: instead of a solid core. The bore itself is a separate BoreFeature.
    bore_d: float = 0.0

    def __post_init__(self) -> None:
        if self.d <= 0 or self.length <= 0:
            raise ValueError(f"PinFeature {self.name!r} needs positive d/length")
        if self.axis not in ("X", "Y", "Z"):
            raise ValueError(f"PinFeature {self.name!r} axis must be X/Y/Z")
        if self.bore_d < 0 or self.bore_d >= self.d:
            raise ValueError(f"PinFeature {self.name!r} bore_d must stay inside d")

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
class TextReliefFeature:
    """Text rendered as geometry on a HORIZONTAL face: raised (emboss)
    or sunk (engrave) glyphs, optionally mirrored — a stamp die must
    read backwards so its impression reads forwards. v1 scope: one
    bundled font, horizontal faces only, in-plane rotation allowed.
    Glyph outlines come from OCC's font engine at compile time; the IR
    carries the text plus a conservative footprint estimate so the
    analytic checks stay CAD-free."""

    name: str
    text: str
    at: tuple[float, float]      # anchor (center) on the face, world XY
    plane_z: float               # the host face the relief grows from / sinks into
    size: float                  # cap height, mm
    depth: float                 # relief height (emboss) / cut depth (engrave)
    mode: str = "emboss"         # "emboss" | "engrave"
    mirror: bool = False         # stamps: mirrored so the impression reads
    rotate_deg: float = 0.0      # in-plane rotation about the anchor
    #: "up" = relief on a top face (+Z), "down" = on a bottom face (-Z):
    #: a stamp die carries its glyphs under the body and PRINTS face-down
    #: on the bed — the crispest first-layer text there is.
    direction: str = "up"
    #: Explicit relief polygons in LOCAL mm around the anchor (an SVG
    #: path already flattened at the IR level). When non-empty they ARE
    #: the relief and ``text`` is just the display label.
    polygons: tuple[tuple[tuple[float, float], ...], ...] = ()

    def __post_init__(self) -> None:
        if not self.polygons and not self.text.strip():
            raise ValueError(f"TextReliefFeature {self.name!r} needs text")
        if self.size <= 0 or self.depth <= 0:
            raise ValueError(f"TextReliefFeature {self.name!r} needs positive size/depth")
        if self.mode not in ("emboss", "engrave"):
            raise ValueError(f"TextReliefFeature {self.name!r} mode must be emboss/engrave")
        if self.direction not in ("up", "down"):
            raise ValueError(f"TextReliefFeature {self.name!r} direction must be up/down")

    def footprint(self) -> tuple[float, float]:
        """Conservative (w, h) of the rendered relief — the keepout/probe
        band. Polygons measure their own bbox; text estimates from the
        bundled font (~0.6 cap heights per glyph advance)."""
        if self.polygons:
            xs = [x for poly in self.polygons for x, _ in poly]
            ys = [y for poly in self.polygons for _, y in poly]
            return (max(xs) - min(xs) + 2.0, max(ys) - min(ys) + 2.0)
        return (max(1, len(self.text)) * self.size * 0.72 + self.size,
                self.size * 1.5)


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    import math

    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n < 1e-9:
        raise ValueError("direction must be a non-zero vector")
    return (v[0] / n, v[1] / n, v[2] / n)


@dataclass(frozen=True)
class AngledBoreFeature:
    """A cylindrical cut along an ARBITRARY direction — the oriented
    kernel's first half. ``start`` is the OPEN end (the mouth); the far
    end is blind. Probed by the same swept-cylinder path machinery as
    the axis-aligned BoreFeature (duck-typed: name / d / path())."""

    name: str
    start: tuple[float, float, float]   # the mouth (open end)
    direction: tuple[float, float, float]  # into the material; normalized
    d: float
    length: float

    def __post_init__(self) -> None:
        if self.d <= 0 or self.length <= 0:
            raise ValueError(f"AngledBoreFeature {self.name!r} needs positive d/length")
        object.__setattr__(self, "direction", _normalize(self.direction))

    @property
    def axis(self) -> str:
        # foreign iterators (hole webs, keepout math) filter on axis —
        # an angled bore is never one of X/Y/Z
        return "ANGLED"

    def bbox(self) -> Box3:
        sx, sy, sz = self.start
        ex, ey, ez = (sx + self.direction[0] * self.length,
                      sy + self.direction[1] * self.length,
                      sz + self.direction[2] * self.length)
        r = self.d / 2.0
        return Box3(min(sx, ex) - r, min(sy, ey) - r, min(sz, ez) - r,
                    max(sx, ex) + r, max(sy, ey) + r, max(sz, ez) + r)

    def path(self, probe_overshoot: float = 1.0) -> list[tuple[float, float, float]]:
        sx, sy, sz = self.start
        dx, dy, dz = self.direction
        # open at the mouth (overshoot out), inset before the blind end
        lo = -probe_overshoot
        hi = self.length - 0.4
        return [
            (sx + dx * lo, sy + dy * lo, sz + dz * lo),
            (sx + dx * hi, sy + dy * hi, sz + dz * hi),
        ]


@dataclass(frozen=True)
class AngledPinFeature:
    """An ADDITIVE cylinder along an ARBITRARY direction (a connector's
    diagonal arm barrel). Duck-typed against PinFeature for the presence
    probe: start_point / end_point / length / d / bore_d."""

    name: str
    start: tuple[float, float, float]
    direction: tuple[float, float, float]
    d: float
    length: float
    bore_d: float = 0.0

    def __post_init__(self) -> None:
        if self.d <= 0 or self.length <= 0:
            raise ValueError(f"AngledPinFeature {self.name!r} needs positive d/length")
        if self.bore_d < 0 or self.bore_d >= self.d:
            raise ValueError(f"AngledPinFeature {self.name!r} bore_d must stay inside d")
        object.__setattr__(self, "direction", _normalize(self.direction))

    @property
    def axis(self) -> str:
        return "ANGLED"

    def start_point(self) -> tuple[float, float, float]:
        return self.start

    def end_point(self) -> tuple[float, float, float]:
        sx, sy, sz = self.start
        dx, dy, dz = self.direction
        return (sx + dx * self.length, sy + dy * self.length, sz + dz * self.length)


@dataclass(frozen=True)
class PolyLoftFeature:
    """A ruled loft between two horizontal polygon sections — the
    section_loft kernel (a superellipse pot's wall cannot revolve). Both
    polygons must share the point count so the ruling is deterministic;
    ``cut=True`` subtracts (a cavity) instead of adding. Additive lofts
    form the base body when ``PartForm.kind == "section_loft"``."""

    name: str
    z0: float
    z1: float
    bottom: tuple[tuple[float, float], ...]
    top: tuple[tuple[float, float], ...]
    cut: bool = False

    def __post_init__(self) -> None:
        if self.z1 <= self.z0 + 1e-9:
            raise ValueError(f"PolyLoftFeature {self.name!r}: z1 must sit above z0")
        if len(self.bottom) < 3 or len(self.top) < 3:
            raise ValueError(f"PolyLoftFeature {self.name!r} needs real polygons")
        if len(self.bottom) != len(self.top):
            raise ValueError(
                f"PolyLoftFeature {self.name!r}: sections must share the "
                "point count (deterministic ruling)")


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
    This is the kernel's first floor that slopes in BOTH X and Y
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
    text_reliefs: list[TextReliefFeature] = field(default_factory=list)
    poly_lofts: list[PolyLoftFeature] = field(default_factory=list)
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
