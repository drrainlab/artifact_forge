"""Hole patterns — line / grid / bolt-circle center expansion plus the
analytic min-web checks, all at the IR level (stdlib only). Mirrors
``fields.py``: geometry decisions happen here, countable and checkable,
before any CAD.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.fasteners import FDM_CLEARANCE, screw_spec
from .part import HoleFeature
from .regions import Rect2D
from .section import Pt


def line_centers(
    count: int, spacing: float, center: tuple[float, float] = (0.0, 0.0), axis: str = "x"
) -> list[tuple[float, float]]:
    cx, cy = center
    if count <= 1:
        return [(cx, cy)]
    span = spacing * (count - 1)
    out = []
    for i in range(count):
        offset = -span / 2.0 + i * spacing
        out.append((cx + offset, cy) if axis == "x" else (cx, cy + offset))
    return out


def grid_centers(
    nx: int, ny: int, dx: float, dy: float, center: tuple[float, float] = (0.0, 0.0)
) -> list[tuple[float, float]]:
    cx, cy = center
    x0, y0 = cx - dx * (nx - 1) / 2.0, cy - dy * (ny - 1) / 2.0
    return [(x0 + i * dx, y0 + j * dy) for j in range(ny) for i in range(nx)]


def bolt_circle_centers(
    count: int,
    circle_d: float,
    center: tuple[float, float] = (0.0, 0.0),
    start_deg: float = 0.0,
) -> list[tuple[float, float]]:
    cx, cy = center
    r = circle_d / 2.0
    out = []
    for i in range(count):
        ang = math.radians(start_deg) + i * math.tau / count
        out.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return out


def holes_from_centers(
    centers: list[tuple[float, float]],
    z_top: float,
    through: float,
    screw: str,
    countersink_face: str = "top",
) -> list[HoleFeature]:
    return [
        HoleFeature(
            at=(x, y, z_top),
            screw=screw,
            through=through,
            countersink_face=countersink_face,
        )
        for x, y in centers
    ]


def hole_keep_radius(hole: HoleFeature) -> float:
    """Effective material-eating radius: the countersink head circle wins
    over the bare bore when present."""
    spec = screw_spec(hole.screw)
    bore_r = spec["clear"] / 2.0 + FDM_CLEARANCE / 2.0
    if hole.countersink:
        return max(bore_r, spec["head"] / 2.0 + 0.3)
    return bore_r


@dataclass(frozen=True)
class CircleOutline:
    """An annular plate outline: outer radius and optional inner bore."""

    center: tuple[float, float]
    outer_r: float
    inner_r: float = 0.0

    def edge_distance(self, p: Pt) -> float:
        d = math.hypot(p.u - self.center[0], p.v - self.center[1])
        dist_outer = self.outer_r - d
        dist_inner = (d - self.inner_r) if self.inner_r > 0 else math.inf
        return min(dist_outer, dist_inner)


@dataclass(frozen=True)
class RectOutline:
    rect: Rect2D
    corner_r: float = 0.0

    def edge_distance(self, p: Pt) -> float:
        r = self.rect
        base = min(p.u - r.u0, r.u1 - p.u, p.v - r.v0, r.v1 - p.v)
        if self.corner_r <= 0:
            return base
        # In a corner quadrant the true boundary is the corner arc:
        # distance = corner_r - distance_to_arc_center.
        quadrants = (
            (r.u0 + self.corner_r, r.v0 + self.corner_r,
             p.u < r.u0 + self.corner_r and p.v < r.v0 + self.corner_r),
            (r.u1 - self.corner_r, r.v0 + self.corner_r,
             p.u > r.u1 - self.corner_r and p.v < r.v0 + self.corner_r),
            (r.u0 + self.corner_r, r.v1 - self.corner_r,
             p.u < r.u0 + self.corner_r and p.v > r.v1 - self.corner_r),
            (r.u1 - self.corner_r, r.v1 - self.corner_r,
             p.u > r.u1 - self.corner_r and p.v > r.v1 - self.corner_r),
        )
        for cu, cv, inside in quadrants:
            if inside:
                return self.corner_r - math.hypot(p.u - cu, p.v - cv)
        return base


Outline = CircleOutline | RectOutline


def min_web_violations(
    holes: list[HoleFeature],
    outline: Outline,
    min_web: float,
    extra_keep_circles: tuple[tuple[float, float, float], ...] = (),
) -> list[str]:
    """Every pair of holes (and every hole vs the outline, and vs extra
    keep circles like a central bore) must keep ``min_web`` of material."""
    problems: list[str] = []
    entries = [
        (Pt(h.at[0], h.at[1]), hole_keep_radius(h), f"hole@({h.at[0]:.1f},{h.at[1]:.1f})")
        for h in holes
    ]
    entries.extend(
        (Pt(x, y), r, f"bore@({x:.1f},{y:.1f})") for x, y, r in extra_keep_circles
    )
    for i in range(len(entries)):
        p1, r1, n1 = entries[i]
        for j in range(i + 1, len(entries)):
            p2, r2, n2 = entries[j]
            web = p1.dist(p2) - r1 - r2
            if web < min_web - 1e-9:
                problems.append(f"{n1} and {n2}: web {web:.2f} < {min_web:g}")
    for p, r, n in entries:
        edge = outline.edge_distance(p) - r
        if edge < min_web - 1e-9:
            problems.append(f"{n}: edge web {edge:.2f} < {min_web:g}")
    return problems
