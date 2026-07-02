"""Section-profile IR — exact line/arc segment chains, stdlib only.

A profile is a closed loop of tagged :class:`LineSeg`/:class:`ArcSeg`
segments in the section plane's 2D coordinates ``(u, v)``. Exactness is the
point: mouth gaps and lip lengths are read from segment parameters, not from
a mesh, so Form-IR validation needs no CAD kernel and has no tolerance
fuzz. Architectural rule: importing ``artifact_forge_ng.form`` must never
load cadquery (enforced by a test).

Frame convention (one place — every probe, region and datum goes through
:func:`plane_mapping`): the flagship uses plane ``YZ`` with ``width_axis X``,
so ``u = Y`` (mouth opens toward +u) and ``v = Z`` (flange underside at
``v = 0``, hook hangs below at ``v < 0``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterator, Sequence

TOL = 1e-6


@dataclass(frozen=True)
class Pt:
    u: float
    v: float

    def __add__(self, other: "Pt") -> "Pt":
        return Pt(self.u + other.u, self.v + other.v)

    def __sub__(self, other: "Pt") -> "Pt":
        return Pt(self.u - other.u, self.v - other.v)

    def scaled(self, k: float) -> "Pt":
        return Pt(self.u * k, self.v * k)

    def norm(self) -> float:
        return math.hypot(self.u, self.v)

    def dist(self, other: "Pt") -> float:
        return (self - other).norm()

    def unit(self) -> "Pt":
        n = self.norm()
        if n < TOL:
            raise ValueError("cannot normalize a zero vector")
        return Pt(self.u / n, self.v / n)

    def dot(self, other: "Pt") -> float:
        return self.u * other.u + self.v * other.v

    def cross(self, other: "Pt") -> float:
        return self.u * other.v - self.v * other.u

    def perp(self) -> "Pt":
        """Rotate +90 degrees (CCW)."""
        return Pt(-self.v, self.u)


@dataclass(frozen=True)
class LineSeg:
    a: Pt
    b: Pt
    tags: frozenset[str] = frozenset()

    @property
    def length(self) -> float:
        return self.a.dist(self.b)

    def tangent_at_start(self) -> Pt:
        return (self.b - self.a).unit()

    def tangent_at_end(self) -> Pt:
        return (self.b - self.a).unit()

    def point_at(self, t: float) -> Pt:
        return Pt(
            self.a.u + (self.b.u - self.a.u) * t,
            self.a.v + (self.b.v - self.a.v) * t,
        )

    def reversed(self) -> "LineSeg":
        return LineSeg(self.b, self.a, self.tags)

    def with_tags(self, *extra: str) -> "LineSeg":
        return replace(self, tags=self.tags | frozenset(extra))


@dataclass(frozen=True)
class ArcSeg:
    """Circular arc from ``a`` to ``b`` around ``center``; ``ccw`` gives the
    sweep direction. Endpoint radii must agree at construction."""

    a: Pt
    b: Pt
    center: Pt
    ccw: bool
    tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        ra, rb = self.a.dist(self.center), self.b.dist(self.center)
        if abs(ra - rb) > 1e-4 * max(ra, 1.0):
            raise ValueError(
                f"arc endpoint radii differ: {ra:.6f} vs {rb:.6f} (center {self.center})"
            )

    @property
    def radius(self) -> float:
        return self.a.dist(self.center)

    @property
    def start_angle(self) -> float:
        d = self.a - self.center
        return math.atan2(d.v, d.u)

    @property
    def end_angle(self) -> float:
        d = self.b - self.center
        return math.atan2(d.v, d.u)

    @property
    def sweep(self) -> float:
        """Signed sweep angle in (0, 2*pi]; positive if ccw."""
        delta = self.end_angle - self.start_angle
        if self.ccw:
            while delta <= TOL:
                delta += math.tau
        else:
            while delta >= -TOL:
                delta -= math.tau
        return delta

    @property
    def length(self) -> float:
        return abs(self.sweep) * self.radius

    def point_at(self, t: float) -> Pt:
        ang = self.start_angle + self.sweep * t
        return Pt(
            self.center.u + self.radius * math.cos(ang),
            self.center.v + self.radius * math.sin(ang),
        )

    def _tangent(self, angle: float) -> Pt:
        t = Pt(-math.sin(angle), math.cos(angle))
        return t if self.ccw else t.scaled(-1.0)

    def tangent_at_start(self) -> Pt:
        return self._tangent(self.start_angle)

    def tangent_at_end(self) -> Pt:
        return self._tangent(self.end_angle)

    def midpoint(self) -> Pt:
        return self.point_at(0.5)

    def reversed(self) -> "ArcSeg":
        return ArcSeg(self.b, self.a, self.center, not self.ccw, self.tags)

    def with_tags(self, *extra: str) -> "ArcSeg":
        return replace(self, tags=self.tags | frozenset(extra))


Seg = LineSeg | ArcSeg


def _segment_area(seg: Seg) -> float:
    """Signed-area contribution: chord shoelace + circular-segment bulge."""
    chord = (seg.a.u * seg.b.v - seg.b.u * seg.a.v) / 2.0
    if isinstance(seg, LineSeg):
        return chord
    sweep = seg.sweep
    r = seg.radius
    bulge = (r * r / 2.0) * (sweep - math.sin(sweep))
    return chord + bulge


class ProfileLoop:
    """A closed, connected chain of segments, stored CCW (positive area).

    Construction validates closure (each segment starts where the previous
    ended, and the last ends at the first) and auto-reverses a CW input.
    Simplicity (no self-intersection) is checked by the form validators,
    not here — a validator failure is a Finding, not a crash.
    """

    def __init__(self, segments: Sequence[Seg]) -> None:
        segments = list(segments)
        if len(segments) < 2:
            raise ValueError("a loop needs at least two segments")
        for prev, cur in zip(segments, segments[1:] + segments[:1]):
            if prev.b.dist(cur.a) > 1e-4:
                raise ValueError(
                    f"loop not closed: segment ends at ({prev.b.u:.4f},{prev.b.v:.4f}) "
                    f"but next starts at ({cur.a.u:.4f},{cur.a.v:.4f})"
                )
        if sum(_segment_area(s) for s in segments) < 0:
            segments = [s.reversed() for s in reversed(segments)]
        self.segments: list[Seg] = segments

    def area(self) -> float:
        return sum(_segment_area(s) for s in self.segments)

    def perimeter(self) -> float:
        return sum(s.length for s in self.segments)

    def bbox(self) -> tuple[Pt, Pt]:
        us: list[float] = []
        vs: list[float] = []
        for s in self.segments:
            us.extend((s.a.u, s.b.u))
            vs.extend((s.a.v, s.b.v))
            if isinstance(s, ArcSeg):
                # Include any quadrant extreme the sweep passes through —
                # endpoint sampling misses the true top/bottom of wide arcs.
                start, sweep = s.start_angle, s.sweep
                for k in range(-4, 9):
                    ang = k * math.pi / 2.0
                    delta = ang - start
                    if sweep >= 0 and 0.0 <= delta <= sweep:
                        hit = True
                    elif sweep < 0 and sweep <= delta <= 0.0:
                        hit = True
                    else:
                        hit = False
                    if hit:
                        us.append(s.center.u + s.radius * math.cos(ang))
                        vs.append(s.center.v + s.radius * math.sin(ang))
        return Pt(min(us), min(vs)), Pt(max(us), max(vs))

    def tagged(self, tag: str) -> list[Seg]:
        return [s for s in self.segments if tag in s.tags]

    def joints(self) -> Iterator[tuple[Seg, Seg]]:
        yield from zip(self.segments, self.segments[1:] + self.segments[:1])

    def sample(self, per_segment: int = 8) -> list[Pt]:
        pts: list[Pt] = []
        for s in self.segments:
            for i in range(per_segment):
                pts.append(s.point_at(i / per_segment))
        return pts

    def centroid(self, per_segment: int = 24) -> Pt:
        """Area centroid of the loop, computed on a sampled polygon —
        a documented approximation (arcs as chords), plenty for checks
        that carry a millimetre-scale safety margin."""
        pts = self.sample(per_segment)
        area2 = 0.0
        cu = 0.0
        cv = 0.0
        for p, q in zip(pts, pts[1:] + pts[:1]):
            cross = p.u * q.v - q.u * p.v
            area2 += cross
            cu += (p.u + q.u) * cross
            cv += (p.v + q.v) * cross
        if abs(area2) < TOL:
            raise ValueError("degenerate loop: zero area")
        return Pt(cu / (3.0 * area2), cv / (3.0 * area2))


@dataclass(frozen=True)
class SideOpenObroundCavity:
    """Analytic record of the side-open cavity — the mouth is NOT a hole
    loop (it merges with the outside), so measurements live here."""

    center: Pt
    bundle_d: float
    clearance: float
    mouth_gap: float
    mouth_dir: tuple[float, float] = (1.0, 0.0)

    @property
    def r_cavity(self) -> float:
        return self.bundle_d / 2.0 + self.clearance


@dataclass
class SectionProfile:
    name: str
    outer: ProfileLoop
    plane: str = "YZ"
    width_axis: str = "X"
    voids: list[ProfileLoop] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)


_MAPPINGS: dict[tuple[str, str], Callable[[float, float, float], tuple[float, float, float]]] = {
    ("YZ", "X"): lambda u, v, w: (w, u, v),
    ("XZ", "Y"): lambda u, v, w: (u, w, v),
    ("XY", "Z"): lambda u, v, w: (u, v, w),
}


def plane_mapping(
    plane: str, width_axis: str
) -> Callable[[float, float, float], tuple[float, float, float]]:
    """The ONE conversion from section coords ``(u, v)`` + width offset ``w``
    to part-frame ``(x, y, z)``. Every region, probe and datum goes through
    this — hand-mapped axes are exactly the v1 bug class this kills."""
    try:
        return _MAPPINGS[(plane, width_axis)]
    except KeyError:
        raise ValueError(
            f"unsupported plane/width_axis pair ({plane!r}, {width_axis!r}); "
            f"supported: {sorted(_MAPPINGS)}"
        ) from None
