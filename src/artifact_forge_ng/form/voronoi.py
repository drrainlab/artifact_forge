"""Voronoi lightening fields — stdlib only, deterministic by construction.

The seed is an explicit parameter: the same YAML always yields the same
cells (a product instance is a reproducible artifact, not a dice roll).
Cells are built by half-plane clipping (a Voronoi cell inside a convex
window is convex), relaxed by a few Lloyd iterations for even sizing, then
shrunk inward by half the ligament so the webs between cells are a
GUARANTEED minimum width, not an emergent accident.
"""

from __future__ import annotations

import math
import random

from .regions import Rect2D, Region2D
from .section import Pt

Poly = list[tuple[float, float]]


def _clip_halfplane(poly: Poly, a: tuple[float, float], b: tuple[float, float]) -> Poly:
    """Keep the side of the bisector closer to ``a`` (Sutherland-Hodgman)."""
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    nx, ny = b[0] - a[0], b[1] - a[1]  # outward normal (toward b)

    def inside(p: tuple[float, float]) -> bool:
        return (p[0] - mx) * nx + (p[1] - my) * ny <= 0.0

    def intersect(p: tuple[float, float], q: tuple[float, float]) -> tuple[float, float]:
        dp = (p[0] - mx) * nx + (p[1] - my) * ny
        dq = (q[0] - mx) * nx + (q[1] - my) * ny
        t = dp / (dp - dq)
        return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

    out: Poly = []
    for p, q in zip(poly, poly[1:] + poly[:1]):
        p_in, q_in = inside(p), inside(q)
        if p_in:
            out.append(p)
            if not q_in:
                out.append(intersect(p, q))
        elif q_in:
            out.append(intersect(p, q))
    return out


def _cell(site: tuple[float, float], sites: list[tuple[float, float]], window: Rect2D) -> Poly:
    poly: Poly = [
        (window.u0, window.v0),
        (window.u1, window.v0),
        (window.u1, window.v1),
        (window.u0, window.v1),
    ]
    for other in sites:
        if other == site:
            continue
        poly = _clip_halfplane(poly, site, other)
        if len(poly) < 3:
            return []
    return poly


def _centroid(poly: Poly) -> tuple[float, float]:
    area2 = cx = cy = 0.0
    for p, q in zip(poly, poly[1:] + poly[:1]):
        cross = p[0] * q[1] - q[0] * p[1]
        area2 += cross
        cx += (p[0] + q[0]) * cross
        cy += (p[1] + q[1]) * cross
    if abs(area2) < 1e-12:
        return poly[0]
    return (cx / (3.0 * area2), cy / (3.0 * area2))


def _area(poly: Poly) -> float:
    return abs(
        sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1]))
    ) / 2.0


def _shrink_convex(poly: Poly, inset: float) -> Poly:
    """Inward offset of a convex CCW polygon: clip by each edge moved
    inward along its normal."""
    if _signed_area(poly) < 0:
        poly = poly[::-1]
    out = list(poly)
    for p, q in zip(poly, poly[1:] + poly[:1]):
        ex, ey = q[0] - p[0], q[1] - p[1]
        length = math.hypot(ex, ey)
        if length < 1e-9:
            continue
        # inward normal for CCW is left of the edge
        nx, ny = -ey / length, ex / length
        px, py = p[0] + nx * inset, p[1] + ny * inset
        out = _clip_line(out, (px, py), (nx, ny))
        if len(out) < 3:
            return []
    return out


def _signed_area(poly: Poly) -> float:
    return sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1])) / 2.0


def _clip_line(poly: Poly, point: tuple[float, float], normal: tuple[float, float]) -> Poly:
    """Keep the half-plane (x - point) . normal >= 0."""

    def side(p: tuple[float, float]) -> float:
        return (p[0] - point[0]) * normal[0] + (p[1] - point[1]) * normal[1]

    out: Poly = []
    for p, q in zip(poly, poly[1:] + poly[:1]):
        sp, sq = side(p), side(q)
        if sp >= 0:
            out.append(p)
            if sq < 0:
                t = sp / (sp - sq)
                out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        elif sq >= 0:
            t = sp / (sp - sq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def chaikin(poly: Poly, iterations: int = 2) -> Poly:
    """Chaikin corner cutting on a closed polygon — each pass replaces every
    vertex with two points at 1/4 and 3/4 of its edges, turning a convex
    cell into an organic rounded blob. Cutting only moves the boundary
    INWARD from corners, so ligaments and keepout clearances can only grow."""
    out = list(poly)
    for _ in range(max(0, iterations)):
        smoothed: Poly = []
        for p, q in zip(out, out[1:] + out[:1]):
            smoothed.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            smoothed.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        out = smoothed
    return out


def _poly_clear_of_keepout(poly: Poly, keepout: Region2D) -> bool:
    samples: list[Pt] = []
    for p, q in zip(poly, poly[1:] + poly[:1]):
        for t in (0.0, 0.5):
            samples.append(Pt(p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return all(
        keepout.shape.distance(s) > keepout.clearance - 1e-9
        and not keepout.shape.contains(s)
        for s in samples
    )


def voronoi_cells_for_sites(
    sites: list[tuple[float, float]],
    window: Rect2D,
    keepouts: list[Region2D],
    *,
    min_ligament: float,
    min_cell_area: float = 12.0,
    corner_smooth: int = 2,
) -> list[Poly]:
    """The cell pipeline for FIXED sites (no Lloyd relaxation): half-plane
    Voronoi cell per site inside ``window``, shrunk for the ligament,
    area/keepout filtered, Chaikin-smoothed. :func:`voronoi_cells` relaxes
    its random sites first and then runs exactly this; the exoskeleton
    windows (form/exoskeleton/windows.py) feed rib-graph nodes straight in."""
    out: list[Poly] = []
    for site in sites:
        cell = _cell(site, sites, window)
        if len(cell) < 3:
            continue
        shrunk = _shrink_convex(cell, min_ligament / 2.0)
        if len(shrunk) < 3 or _area(shrunk) < min_cell_area:
            continue
        if all(_poly_clear_of_keepout(shrunk, k) for k in keepouts):
            out.append(chaikin(shrunk, corner_smooth))
    return out


def voronoi_cells(
    window: Rect2D,
    keepouts: list[Region2D],
    *,
    seed: int,
    sites: int,
    min_ligament: float,
    edge_margin: float,
    relax_iterations: int = 2,
    min_cell_area: float | None = None,
    corner_smooth: int = 2,
    init: str = "grid",
) -> list[Poly]:
    """Deterministic relaxed Voronoi cells, shrunk for the ligament,
    filtered against keepouts and Chaikin-smoothed into organic blobs.

    Two rules keep a pattern field COVERING its window instead of
    clustering (the ring-band lesson — "more voronoi" used to make the
    band sparser):

    - ``init="grid"`` starts the sites on a jittered grid sized so cells
      are near-square: uniform-random starts leave sliver cells that die
      in the ligament shrink, and every dead cell is a bald patch on the
      part. ``init="random"`` keeps the uniform scatter — the bone-window
      look, and the survivor when keepout masks eat most of the window
      (a grid dies in lockstep where a scatter finds the free pockets);
    - ``min_cell_area=None`` scales the sliver filter to the pattern
      itself — a fraction of the MEAN cell area (window / sites), clamped
      to [4.0, 12.0]. The old absolute 12.0 silently dropped most cells
      on a narrow band, so asking for more sites made the pattern SPARSER.
    """
    inner = window.shrunk(edge_margin)
    if inner.width <= 0 or inner.height <= 0:
        return []
    n_sites = max(3, sites)
    if min_cell_area is None:
        mean_area = inner.width * inner.height / n_sites
        min_cell_area = min(12.0, max(4.0, 0.3 * mean_area))
    rng = random.Random(seed)
    if init == "random":
        points = [
            (rng.uniform(inner.u0, inner.u1), rng.uniform(inner.v0, inner.v1))
            for _ in range(n_sites)
        ]
    else:
        cell_side = math.sqrt(inner.width * inner.height / n_sites)
        rows = max(1, round(inner.height / cell_side))
        cols = max(1, math.ceil(n_sites / rows))
        du, dv = inner.width / cols, inner.height / rows
        points = [
            (
                inner.u0 + (k % cols + 0.5 + rng.uniform(-0.35, 0.35)) * du,
                inner.v0 + (k // cols + 0.5 + rng.uniform(-0.35, 0.35)) * dv,
            )
            for k in range(n_sites)
        ]
    for _ in range(max(0, relax_iterations)):
        cells = [_cell(s, points, inner) for s in points]
        points = [
            _centroid(c) if len(c) >= 3 else s for s, c in zip(points, cells)
        ]
    return voronoi_cells_for_sites(
        points,
        inner,
        keepouts,
        min_ligament=min_ligament,
        min_cell_area=min_cell_area,
        corner_smooth=corner_smooth,
    )


def min_polygon_gap(polys: list[Poly], cap: float = 1e9) -> float:
    """Minimum edge-sample distance between distinct polygons — the
    validator's measurement of the actual ligament."""
    best = cap
    sampled: list[list[Pt]] = []
    for poly in polys:
        pts: list[Pt] = []
        for p, q in zip(poly, poly[1:] + poly[:1]):
            for t in (0.0, 0.25, 0.5, 0.75):
                pts.append(Pt(p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        sampled.append(pts)
    for i in range(len(sampled)):
        for j in range(i + 1, len(sampled)):
            for a in sampled[i]:
                for b in sampled[j]:
                    d = a.dist(b)
                    if d < best:
                        best = d
    return best
