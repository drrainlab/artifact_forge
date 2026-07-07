"""Organic windows between the ribs — the DUAL of the rib graph, with an
EXPLICIT clipping guarantee.

The naive "windows = Voronoi cells of the graph nodes" is geometrically
inverted: node-cell borders are the perpendicular bisectors of the Gabriel
edges, so the ribs would run cell-center to cell-center THROUGH the
windows. The correct construction is the dual: window candidate sites are
the FACE centers of the rib graph — the Voronoi VERTICES of the node set —
so each window grows in the open face between ribs, not around a node.

Duality alone still proves nothing, so the guarantee is measured-in, not
hoped-for: every window polygon is CLIPPED against every nearby rib
segment at clearance ``edge_radius + min_ligament/2`` (halfplane clip on
the segment's supporting line, keeping the polygon-centroid side;
conservative over-cut beyond the segment ends is accepted). The
``form.windows_inside_safe_regions`` check re-measures exactly this
distance on the final vertices.

The cell pipeline reuses form/voronoi's fixed-site helper
(:func:`voronoi_cells_for_sites`)."""

from __future__ import annotations

import math
from typing import Sequence

from ..regions import Rect2D, Region2D
from ..section import Pt
from ..voronoi import (
    _area,
    _cell,
    _centroid,
    _clip_line,
    chaikin,
    voronoi_cells_for_sites,
)
from .ir import RibGraph
from .masks import point_clear, poly_clear
from .substrate import SubstrateForm

#: Cells smaller than this after clip+scale are visual noise, not windows.
MIN_CELL_AREA = 12.0
#: Face-site dedupe grid (mm) — Voronoi vertices closer than this are one.
FACE_GRID = 0.1
#: Face sites must sit at least this far inside the window rim.
FACE_EDGE_MARGIN = 1.0


def _face_sites(
    nodes_xy: list[tuple[float, float]],
    window: Rect2D,
    masks: Sequence[Region2D],
) -> list[tuple[float, float]]:
    """Voronoi VERTICES of the node set inside the window: run the raw
    per-node cell clip (no shrink) and collect every resulting polygon
    vertex, deduped on a 0.1mm grid, dropped when outside the shrunken
    window or inside a mask. These are the rib-graph face centers — the
    only places a window may grow."""
    inner = window.shrunk(FACE_EDGE_MARGIN)
    if inner.width <= 0 or inner.height <= 0:
        return []
    seen: dict[tuple[float, float], None] = {}
    for site in nodes_xy:
        for x, y in _cell(site, nodes_xy, window):
            seen.setdefault((round(x, 1), round(y, 1)), None)
    out: list[tuple[float, float]] = []
    for p in sorted(seen):
        if inner.contains(Pt(p[0], p[1])) and point_clear(p, masks):
            out.append(p)
    return out


def _seg_point_dist(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-18:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _orient(px, py, qx, qy, rx, ry) -> float:
    return (qx - px) * (ry - py) - (qy - py) * (rx - px)


def _segs_intersect(p1, q1, p2, q2) -> bool:
    d1 = _orient(*p2, *q2, *p1)
    d2 = _orient(*p2, *q2, *q1)
    d3 = _orient(*p1, *q1, *p2)
    d4 = _orient(*p1, *q1, *q2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _poly_seg_dist(
    poly: Sequence[tuple[float, float]],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """Exact min distance between a polygon boundary and segment ab
    (0.0 when they cross)."""
    best = math.inf
    for p, q in zip(poly, list(poly[1:]) + [poly[0]]):
        if _segs_intersect(p, q, a, b):
            return 0.0
        best = min(
            best,
            _seg_point_dist(p, a, b),
            _seg_point_dist(q, a, b),
            _seg_point_dist(a, p, q),
            _seg_point_dist(b, p, q),
        )
    return best


def _clip_rib_clearance(
    poly: list[tuple[float, float]],
    a: tuple[float, float],
    b: tuple[float, float],
    clearance: float,
) -> list[tuple[float, float]]:
    """Clip the polygon by the halfplane at signed distance ``clearance``
    from the segment's SUPPORTING LINE, keeping the centroid's side. The
    over-cut beyond the segment ends is deliberate conservatism."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return poly
    nx, ny = -dy / length, dx / length
    cx, cy = _centroid(poly)
    side = (cx - a[0]) * nx + (cy - a[1]) * ny
    s = 1.0 if side >= 0 else -1.0
    anchor = (a[0] + s * clearance * nx, a[1] + s * clearance * ny)
    return _clip_line(poly, anchor, (s * nx, s * ny))


def organic_window_field(
    graph: RibGraph,
    substrate: SubstrateForm,
    masks: Sequence[Region2D],
    *,
    window_scale: float,
    min_ligament: float,
    corner_smooth: int = 2,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Window polygons in local (a, b): Voronoi cells of the rib-graph
    FACE centers (dual construction), ligament-shrunk in the shared
    pipeline, explicitly clipped to ``edge_radius + min_ligament/2``
    clearance from every rib segment, scaled about their centroids,
    Chaikin-smoothed, then filtered against the masks and the minimum
    area. Every survivor is FINAL — validators measure these exact
    vertices, including the rib clearance."""
    nodes_xy = [(n[0], n[1]) for n in graph.nodes]
    if len(nodes_xy) < 3:
        return ()
    sites = _face_sites(nodes_xy, substrate.window, masks)
    if len(sites) < 3:
        return ()
    # Ligament shrink + mask filter happen here; smoothing is deferred
    # until after the rib-clearance clip below.
    raw = voronoi_cells_for_sites(
        sites,
        substrate.window,
        list(masks),
        min_ligament=min_ligament,
        min_cell_area=1.0,
        corner_smooth=0,
    )
    radii = graph.edge_radius or tuple(0.0 for _ in graph.edges)
    segments = [
        (nodes_xy[i], nodes_xy[j], r + min_ligament / 2.0)
        for (i, j), r in zip(graph.edges, radii)
    ]
    out: list[tuple[tuple[float, float], ...]] = []
    for poly in raw:
        cell = list(poly)
        for a, b, clearance in segments:
            # bbox prefilter: the segment must be within reach at all
            lo_x = min(p[0] for p in cell) - clearance
            hi_x = max(p[0] for p in cell) + clearance
            lo_y = min(p[1] for p in cell) - clearance
            hi_y = max(p[1] for p in cell) + clearance
            if (max(a[0], b[0]) < lo_x or min(a[0], b[0]) > hi_x
                    or max(a[1], b[1]) < lo_y or min(a[1], b[1]) > hi_y):
                continue
            if _poly_seg_dist(cell, a, b) < clearance:
                cell = _clip_rib_clearance(cell, a, b, clearance)
                if len(cell) < 3:
                    break
        if len(cell) < 3:
            continue
        scx, scy = _centroid(cell)
        s = max(0.0, min(window_scale, 1.0))
        cell = [(scx + (x - scx) * s, scy + (y - scy) * s) for x, y in cell]
        cell = chaikin(cell, corner_smooth)
        if _area(cell) < MIN_CELL_AREA:
            continue
        if not poly_clear(cell, masks):
            continue
        out.append(tuple(cell))
    return tuple(out)
