"""SVG path data -> relief polygons, at the IR level (svgelements is
pure python — no CAD here). Deliberate scope, guarded loudly:

* every subpath must be CLOSED (an open stroke has no printable area);
* nesting is EVEN-ODD: a subpath inside an outline is a HOLE (the
  counter of an ``O``), a subpath inside a hole is an island again —
  each hole is grouped with its immediate parent outline;
* curves are flattened by arc-length sampling AFTER scaling, so the
  chord error stays visually irrelevant at any size.

The min-width across the motif (outline strokes, hole openings, the web
between a hole and its outline, the web between sibling holes — the same
ray math the field probe uses) is returned so the printable-stroke check
measures, never hopes."""
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


def _bbox_overlap(a: Polygon, b: Polygon) -> bool:
    ax0 = min(x for x, _ in a); ax1 = max(x for x, _ in a)
    ay0 = min(y for _, y in a); ay1 = max(y for _, y in a)
    bx0 = min(x for x, _ in b); bx1 = max(x for x, _ in b)
    by0 = min(y for _, y in b); by1 = max(y for _, y in b)
    return ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1


def _pt_segment_dist(px: float, py: float, x0: float, y0: float,
                     x1: float, y1: float) -> float:
    ex, ey = x1 - x0, y1 - y0
    ll = ex * ex + ey * ey
    if ll < 1e-18:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * ex + (py - y0) * ey) / ll))
    return math.hypot(px - (x0 + t * ex), py - (y0 + t * ey))


def _poly_gap(a: Polygon, b: Polygon) -> float:
    """Minimum boundary-to-boundary distance between two disjoint
    polygons — edge sample points of each against the segments of the
    other (the web the printer must actually lay down)."""
    best = math.inf
    for src, dst in ((a, b), (b, a)):
        m = len(dst)
        for p, q in zip(src, src[1:] + src[:1]):
            for t in (0.0, 0.25, 0.5, 0.75):
                px, py = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
                for j in range(m):
                    d = _pt_segment_dist(px, py, dst[j][0], dst[j][1],
                                         dst[(j + 1) % m][0], dst[(j + 1) % m][1])
                    if d < best:
                        best = d
    return best


def _closest_boundary_pair(
    a: Polygon, b: Polygon
) -> tuple[tuple[float, float], tuple[float, float]]:
    """The closest boundary points between two disjoint polygons —
    returned as ``(point_on_a, point_on_b)``. Sample points of each
    boundary are projected onto the other's segments (same sampling as
    the ``_poly_gap`` web measure, so a bridge lands exactly across the
    measured narrowest web)."""
    best = math.inf
    pa = a[0]
    pb = b[0]
    for src, dst, flip in ((a, b, False), (b, a, True)):
        m = len(dst)
        for p, q in zip(src, src[1:] + src[:1]):
            for t in (0.0, 0.25, 0.5, 0.75):
                px, py = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
                for j in range(m):
                    x0, y0 = dst[j]
                    x1, y1 = dst[(j + 1) % m]
                    ex, ey = x1 - x0, y1 - y0
                    ll = ex * ex + ey * ey
                    if ll < 1e-18:
                        qx, qy = x0, y0
                    else:
                        tt = max(0.0, min(1.0, ((px - x0) * ex
                                                + (py - y0) * ey) / ll))
                        qx, qy = x0 + tt * ex, y0 + tt * ey
                    d = math.hypot(px - qx, py - qy)
                    if d < best:
                        best = d
                        pa, pb = ((qx, qy), (px, py)) if flip \
                            else ((px, py), (qx, qy))
    return pa, pb


def stencil_bridges(
    outlines: tuple[Polygon, ...],
    holes: tuple[tuple[int, Polygon], ...],
    bridge_w: float,
) -> tuple[tuple[int, Polygon], ...]:
    """One stencil bridge per enclosed hole region: a ``bridge_w``-wide
    rectangle across the parent outline's ink at the NARROWEST place,
    overshot past both boundaries — subtracted from the cutter, it
    leaves a solid tab that keeps the hole region attached to the plate.
    Deterministic pure geometry; the honesty probes (single connected
    solid) remain the judge of the built part."""
    bridges: list[tuple[int, Polygon]] = []
    for parent, hole in holes:
        ph, po = _closest_boundary_pair(hole, outlines[parent])
        ux, uy = po[0] - ph[0], po[1] - ph[1]
        norm = math.hypot(ux, uy)
        if norm < 1e-9:
            # touching boundaries — aim outward from the hole centroid
            cx = sum(x for x, _ in hole) / len(hole)
            cy = sum(y for _, y in hole) / len(hole)
            ux, uy = ph[0] - cx, ph[1] - cy
            norm = math.hypot(ux, uy) or 1.0
        ux, uy = ux / norm, uy / norm
        overshoot = 0.8
        sx, sy = ph[0] - ux * overshoot, ph[1] - uy * overshoot
        tx, ty = po[0] + ux * overshoot, po[1] + uy * overshoot
        nx, ny = -uy * bridge_w / 2.0, ux * bridge_w / 2.0
        bridges.append((parent, (
            (sx + nx, sy + ny), (tx + nx, ty + ny),
            (tx - nx, ty - ny), (sx - nx, sy - ny),
        )))
    return tuple(bridges)


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


def flatten_subpaths(path: Path) -> list[list[tuple[float, float]]]:
    """Split an svgelements Path into CLOSED subpaths flattened to
    polylines in raw SVG units (curves sampled by arc length). Shared by
    the relief op and the layer flattener — the guards are identical."""
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
    return raw_polys


def classify_even_odd(
    polys: list[Polygon],
) -> tuple[list[Polygon], list[tuple[int, Polygon]]]:
    """Even-odd nesting of NON-crossing polygons: even depth = outline,
    odd depth = hole tied to its immediate parent outline. Containment
    is tested with a VERTEX of the candidate: it lies on its own
    boundary but strictly inside any genuine container (an interior
    point would land in the very hole we are trying to classify)."""
    containers: list[list[int]] = [
        [j for j, b in enumerate(polys)
         if i != j and _point_in_poly(polys[i][0], b)]
        for i in range(len(polys))
    ]
    depth = [len(c) for c in containers]
    outline_idx = [i for i, d in enumerate(depth) if d % 2 == 0]
    outlines = [polys[i] for i in outline_idx]
    remap = {orig: new for new, orig in enumerate(outline_idx)}
    holes: list[tuple[int, Polygon]] = []
    for i, d in enumerate(depth):
        if d % 2 == 0:
            continue
        # immediate parent = the deepest containing polygon; even-odd
        # guarantees it is an outline one level up
        parent = max(containers[i], key=lambda j: depth[j])
        if depth[parent] != d - 1:
            raise RecipeError(
                "svg subpaths OVERLAP — boundaries must nest cleanly "
                "(even-odd), partial overlaps do not bound an area")
        holes.append((remap[parent], polys[i]))
    return outlines, holes


def svg_path_to_polygons(
    path_data: str, target_w: float
) -> tuple[tuple[Polygon, ...], tuple[tuple[int, Polygon], ...], float]:
    """Parse SVG path data, flatten to polygons, scale uniformly so the
    combined bounding box is ``target_w`` wide, center on the origin.
    Nesting is classified even-odd: returns ``(outlines, holes,
    min_width)`` where each hole is ``(parent_outline_index, polygon)``
    and min_width covers strokes, hole openings and every web."""
    try:
        path = Path(path_data)
    except Exception as exc:  # noqa: BLE001 — svgelements raises plain errors
        raise RecipeError(f"svg path did not parse: {exc}") from exc
    if len(path) == 0:
        raise RecipeError("svg path is empty")

    raw_polys = flatten_subpaths(path)
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

    # -- refuse CROSSING boundaries before classifying nesting ------------
    # layered color art (fills painted over each other) is not a stamp
    # motif: even-odd would cut the fish out of its background. Mixed
    # vertex containment (some of A's vertices in B, some out) = crossing.
    for i, a in enumerate(polys):
        for j in range(i + 1, len(polys)):
            b = polys[j]
            if not _bbox_overlap(a, b):
                continue
            for src, dst in ((a, b), (b, a)):
                stride = max(1, len(src) // 32)
                inside = [_point_in_poly(p, dst) for p in src[::stride]]
                if any(inside) and not all(inside):
                    raise RecipeError(
                        "svg subpaths OVERLAP — layered fills painted over "
                        "each other do not bound a single area; flatten the "
                        "layers to a union in your editor (Inkscape: Path → "
                        "Union, Figma: Flatten) or export one layer")

    outlines, holes = classify_even_odd(polys)

    # min width is the narrowest thing the printer must resolve: outline
    # strokes, hole OPENINGS (a counter that fuses shut), the web between
    # a hole and its outline, and the web between sibling holes
    widths = [_poly_min_width(p) for p in polys]
    for parent, hole in holes:
        widths.append(_poly_gap(hole, outlines[parent]))
    for k in range(len(holes)):
        for m in range(k + 1, len(holes)):
            if holes[k][0] == holes[m][0]:
                widths.append(_poly_gap(holes[k][1], holes[m][1]))
    return tuple(outlines), tuple(holes), min(widths)


#: a narrow hole LARGER than this is real art, not a hatch sliver —
#: refuse instead of merging it away
MAX_SLIVER_AREA = 25.0  # mm²


def import_svg_path(
    path_data: str, target_w: float, *, floor: float = 0.0
) -> tuple[str, dict[str, int]]:
    """Import-time canonicalization of traced art — the strict relief
    guard stays as-is, the importer cleans and REPORTS (nothing dropped
    silently):

    - subpaths below ``MIN_POLY_AREA`` at the target width are specks
      (Inkscape trace debris) — dropped, counted as ``dropped_specks``;
    - with ``floor`` > 0, HOLES narrower than the printable floor and
      smaller than ``MAX_SLIVER_AREA`` are hatch slivers — two ink
      strokes that nearly touch. The nozzle would fuse them anyway;
      merging them here is explicit, counted as ``merged_hatch_gaps``.
      A LARGE narrow hole is left alone — that is real art, and the
      printability check will judge it honestly.

    Curves come back flattened to polylines (the same canonical form the
    layer flattener emits)."""
    try:
        path = Path(path_data)
    except Exception as exc:  # noqa: BLE001 — svgelements raises plain errors
        raise RecipeError(f"svg path did not parse: {exc}") from exc
    raw_polys = flatten_subpaths(path)
    if not raw_polys:
        raise RecipeError("svg path produced no closed subpaths")
    xs = [x for poly in raw_polys for x, _ in poly]
    w = max(xs) - min(xs)
    if w < 1e-9:
        raise RecipeError("svg path is degenerate (zero-size bbox)")
    scale = target_w / w

    scaled = [tuple((x * scale, y * scale) for x, y in poly)
              for poly in raw_polys]
    kept = [i for i, poly in enumerate(scaled)
            if _poly_area(poly) >= MIN_POLY_AREA]
    dropped_specks = len(raw_polys) - len(kept)
    if not kept:
        raise RecipeError(
            f"every svg subpath collapses below {MIN_POLY_AREA} mm² at "
            f"{target_w:g} mm wide — the art is too fine for this size")

    merged = 0
    if floor > 0.0:
        depth = {i: sum(1 for j in kept if i != j
                        and _point_in_poly(scaled[i][0], scaled[j]))
                 for i in kept}
        slivers = set()
        for i in kept:
            if depth[i] % 2 == 0:
                continue                       # outline, never dropped
            poly = scaled[i]
            if (_poly_min_width(poly) < floor
                    and _poly_area(poly) < MAX_SLIVER_AREA
                    and not any(_point_in_poly(scaled[j][0], poly)
                                for j in kept if j != i)):
                slivers.add(i)                 # nothing nests inside it
        merged = len(slivers)
        kept = [i for i in kept if i not in slivers]

    cleaned = " ".join(
        "M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in raw_polys[i]) + " Z"
        for i in kept)
    return cleaned, {"dropped_specks": dropped_specks,
                     "merged_hatch_gaps": merged}
