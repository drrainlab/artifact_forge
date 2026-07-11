"""SVG path data -> relief polygons, at the IR level (svgelements is
pure python — no CAD here). Deliberate v1 scope, guarded loudly:

* every subpath must be CLOSED (an open stroke has no printable area);
* subpaths must not nest — a nested subpath is a HOLE (the counter of an
  ``O``), and hole subtraction waits for its own iteration;
* curves are flattened by arc-length sampling AFTER scaling, so the
  chord error stays visually irrelevant at any size.

The min-width of every polygon (true narrow dimension across any edge
normal — the same math the field probe uses) is returned so the
printable-stroke check measures, never hopes."""
from __future__ import annotations

import math

from svgelements import Close, Line, Move, Path

from .recipe_ops_core import RecipeError

#: flattening step along a curve, mm (after scaling)
FLATTEN_STEP = 0.4
MIN_POLY_AREA = 0.5  # mm² — anything smaller is path noise, not a shape

Polygon = tuple[tuple[float, float], ...]


def _poly_area(poly: Polygon) -> float:
    a = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


def _signed_area(poly: Polygon) -> float:
    a = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        a += x0 * y1 - x1 * y0
    return a / 2.0


def _ray_segment_t(ox: float, oy: float, dx: float, dy: float,
                   x0: float, y0: float, x1: float, y1: float) -> float | None:
    """Distance t >= 0 along the ray (o + t*d) to the segment, or None."""
    ex, ey = x1 - x0, y1 - y0
    denom = dx * ey - dy * ex
    if abs(denom) < 1e-12:
        return None
    t = ((x0 - ox) * ey - (y0 - oy) * ex) / denom
    u = ((x0 - ox) * dy - (y0 - oy) * dx) / denom
    if t > 1e-6 and -1e-9 <= u <= 1.0 + 1e-9:
        return t
    return None


def _poly_min_width(poly: Polygon) -> float:
    """LOCAL thickness of the polygon: from every edge midpoint, cast a
    ray along the inward normal and take the nearest boundary hit. The
    edge-normal-extent shortcut is only honest for CONVEX shapes — a
    concave arrow's shaft would slip past it."""
    n = len(poly)
    ccw = _signed_area(poly) > 0.0
    best = math.inf
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        edge_l = math.hypot(ex, ey)
        if edge_l < 1e-9:
            continue
        # inward normal: left of travel for CCW, right for CW
        nx, ny = (-ey / edge_l, ex / edge_l) if ccw else (ey / edge_l, -ex / edge_l)
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        nearest = math.inf
        for j in range(n):
            if j == i:
                continue
            hit = _ray_segment_t(mx, my, nx, ny,
                                 poly[j][0], poly[j][1],
                                 poly[(j + 1) % n][0], poly[(j + 1) % n][1])
            if hit is not None and hit < nearest:
                nearest = hit
        if nearest < best:
            best = nearest
    return 0.0 if best is math.inf else best


def _point_in_poly(pt: tuple[float, float], poly: Polygon) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            t = (y - y0) / (y1 - y0)
            if x < x0 + t * (x1 - x0):
                inside = not inside
    return inside


def svg_path_to_polygons(
    path_data: str, target_w: float
) -> tuple[tuple[Polygon, ...], float]:
    """Parse SVG path data, flatten to polygons, scale uniformly so the
    combined bounding box is ``target_w`` wide, center on the origin.
    Returns (polygons, min_width_across_all)."""
    try:
        path = Path(path_data)
    except Exception as exc:  # noqa: BLE001 — svgelements raises plain errors
        raise RecipeError(f"svg path did not parse: {exc}") from exc
    if len(path) == 0:
        raise RecipeError("svg path is empty")

    # -- split into subpaths and flatten (in raw SVG units first) ---------
    raw_polys: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    closed = False
    for seg in path:
        if isinstance(seg, Move):
            if current:
                raise RecipeError(
                    "svg subpath is OPEN — every subpath must close (Z) "
                    "to bound a printable area")
            current = []
            closed = False
            continue
        if isinstance(seg, Close):
            closed = True
            if len(current) >= 3:
                raw_polys.append(current)
            current = []
            continue
        if isinstance(seg, Line):
            pts = [seg.end]
        else:
            # curve: flatten by arc length (raw units; rescaled below the
            # sampling stays dense enough because we scale uniformly)
            length = seg.length(error=1e-3)
            n = max(4, int(math.ceil(length / FLATTEN_STEP)))
            pts = [seg.point(k / n) for k in range(1, n + 1)]
        if not current and hasattr(seg, "start") and seg.start is not None:
            current.append((float(seg.start.x), float(seg.start.y)))
        current.extend((float(p.x), float(p.y)) for p in pts)
    if current and not closed:
        raise RecipeError(
            "svg subpath is OPEN — every subpath must close (Z) to bound "
            "a printable area")
    if not raw_polys:
        raise RecipeError("svg path produced no closed subpaths")

    # -- normalize: uniform scale to target width, centered ---------------
    xs = [x for poly in raw_polys for x, _ in poly]
    ys = [y for poly in raw_polys for _, y in poly]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if w < 1e-9 or h < 1e-9:
        raise RecipeError("svg path is degenerate (zero-size bbox)")
    scale = target_w / w
    cx = (max(xs) + min(xs)) / 2.0
    cy = (max(ys) + min(ys)) / 2.0
    # SVG y grows DOWN — flip it so the relief reads the way the file does
    polys: list[Polygon] = []
    for raw in raw_polys:
        poly = tuple(((x - cx) * scale, -(y - cy) * scale) for x, y in raw)
        if _poly_area(poly) < MIN_POLY_AREA:
            raise RecipeError(
                f"svg subpath collapses to {_poly_area(poly):.2f} mm² at "
                f"{target_w:g} mm wide — path noise, not a shape")
        polys.append(poly)

    # -- holes are a later iteration: refuse nesting loudly ---------------
    for i, a in enumerate(polys):
        ca = (sum(p[0] for p in a) / len(a), sum(p[1] for p in a) / len(a))
        for j, b in enumerate(polys):
            if i != j and _point_in_poly(ca, b):
                raise RecipeError(
                    "svg subpaths NEST — holes (an O's counter) are not "
                    "supported in v1; use hole-free outlines")

    min_width = min(_poly_min_width(p) for p in polys)
    return tuple(polys), min_width
