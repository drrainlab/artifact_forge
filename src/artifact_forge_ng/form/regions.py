"""Semantic regions — named, role-tagged zones every modifier and validator
must locate features through. Nothing cuts 'somewhere on the part'; it cuts
a region, and keepout regions veto cuts at the IR level.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..product.archetype import RegionRole
from .section import Pt

INF = math.inf


@dataclass(frozen=True)
class Rect2D:
    u0: float
    v0: float
    u1: float
    v1: float

    def __post_init__(self) -> None:
        if self.u0 > self.u1 or self.v0 > self.v1:
            raise ValueError(f"degenerate rect {self}")

    @property
    def width(self) -> float:
        return self.u1 - self.u0

    @property
    def height(self) -> float:
        return self.v1 - self.v0

    def shrunk(self, margin: float) -> "Rect2D":
        if self.width <= 2 * margin or self.height <= 2 * margin:
            # Collapses to a zero rect at the centre — callers treat an
            # empty window as "nothing fits", not an error.
            cu, cv = (self.u0 + self.u1) / 2, (self.v0 + self.v1) / 2
            return Rect2D(cu, cv, cu, cv)
        return Rect2D(
            self.u0 + margin, self.v0 + margin, self.u1 - margin, self.v1 - margin
        )

    def contains(self, p: Pt) -> bool:
        return self.u0 - 1e-9 <= p.u <= self.u1 + 1e-9 and (
            self.v0 - 1e-9 <= p.v <= self.v1 + 1e-9
        )

    def distance(self, p: Pt) -> float:
        du = max(self.u0 - p.u, 0.0, p.u - self.u1)
        dv = max(self.v0 - p.v, 0.0, p.v - self.v1)
        return math.hypot(du, dv)


@dataclass(frozen=True)
class Circle2D:
    center: Pt
    r: float

    def contains(self, p: Pt) -> bool:
        return p.dist(self.center) <= self.r + 1e-9

    def distance(self, p: Pt) -> float:
        return max(0.0, p.dist(self.center) - self.r)


Shape2D = Rect2D | Circle2D


@dataclass(frozen=True)
class Region2D:
    """A tagged zone in a 2D working plane (a section, or a plate face)."""

    name: str
    role: RegionRole
    shape: Shape2D
    #: Extra separation cuts must keep from this region's boundary.
    clearance: float = 0.0


@dataclass(frozen=True)
class Box3:
    """Part-frame AABB; open sides use +-inf."""

    x0: float = -INF
    y0: float = -INF
    z0: float = -INF
    x1: float = INF
    y1: float = INF
    z1: float = INF

    def contains(self, x: float, y: float, z: float) -> bool:
        return (
            self.x0 - 1e-9 <= x <= self.x1 + 1e-9
            and self.y0 - 1e-9 <= y <= self.y1 + 1e-9
            and self.z0 - 1e-9 <= z <= self.z1 + 1e-9
        )

    @property
    def finite(self) -> bool:
        return all(
            math.isfinite(c)
            for c in (self.x0, self.y0, self.z0, self.x1, self.y1, self.z1)
        )


@dataclass(frozen=True)
class Region:
    """A semantic region in the part frame."""

    name: str
    role: RegionRole
    box: Box3
