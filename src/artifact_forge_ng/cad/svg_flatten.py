"""Layered SVG -> single stamp motif, via OCC booleans (CAD required).

A colored illustration is a PAINTER'S STACK: fills drawn over each
other, later elements covering earlier ones. A stamp die has exactly two
levels, so the stack is reduced by luminance — dark fills are INK
(fused into the relief), light fills are PAPER (cut out of it), in
document order. The background layer, being light or fully covered,
falls away by construction. Within one ``<path>`` element subpaths keep
their even-odd meaning (a glyph's counter stays a hole).

The result is post-processed honestly:

* boolean seam slivers are dropped (area < 0.1% of the biggest loop);
* near-coincident vertices are collapsed (sub-tolerance boolean noise);
* a morphological OPENING (erode + dilate of the outer boundary) removes
  necks and needles thinner than the printable floor at the target
  motif width — the printer could not resolve them anyway, and one
  sub-nozzle sliver would honestly fail the whole die.

This runs ONCE at import time (the cockpit's .svg picker); the product
YAML carries the flattened path data, so the IR pipeline stays CAD-free
and deterministic.
"""
from __future__ import annotations

import io
import math

from ..form.recipe_ops_core import RecipeError
from ..form.svg_path import classify_even_odd, flatten_subpaths

#: fills brighter than this (0..1 luminance) are PAPER, darker are INK
LUMINANCE_PAPER = 0.6
#: printable floor the opening is tuned to (emboss stroke floor, mm)
MIN_FEATURE_MM = 0.8
#: drop loops below this fraction of the biggest loop's area
SLIVER_FRACTION = 0.001


def _luminance(fill) -> float | None:
    """Perceptual luminance of an svgelements Color, or None for none."""
    if fill is None or getattr(fill, "value", None) is None:
        return None
    r = getattr(fill, "red", 0) or 0
    g = getattr(fill, "green", 0) or 0
    b = getattr(fill, "blue", 0) or 0
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _layers(svg_text: str) -> list[tuple[list[list[tuple[float, float]]], bool]]:
    """Paint layers in document order: (closed subpath polylines, is_ink).
    svgelements resolves transforms and styles while parsing."""
    from svgelements import SVG, Path as _Path

    try:
        doc = SVG.parse(io.StringIO(svg_text), reify=True)
    except Exception as exc:  # noqa: BLE001 — parser raises plain errors
        raise RecipeError(f"svg did not parse: {exc}") from exc
    layers = []
    for el in doc.elements():
        if not isinstance(el, _Path) or len(el) == 0:
            continue
        lum = _luminance(getattr(el, "fill", None))
        if lum is None:
            continue  # fill:none — stroke-only art carries no printable area
        polys = flatten_subpaths(el)
        if polys:
            layers.append((polys, lum < LUMINANCE_PAPER))
    if not layers:
        raise RecipeError(
            "svg has no filled <path> elements — convert shapes/strokes "
            "to filled paths in the editor")
    return layers


# -- OCC helpers (imported lazily: this module is only reachable when the
# CAD backend is on) ---------------------------------------------------------


def _dedupe(poly) -> list[tuple[float, float]]:
    """Drop coincident consecutive vertices AND the duplicated closing
    point — makePolygon(close=True) would turn either into a zero-length
    edge, and one degenerate edge is enough to derail an OCC boolean
    (the fish lost its whole head to this)."""
    out: list[tuple[float, float]] = []
    for p in poly:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    while len(out) > 1 and math.hypot(out[0][0] - out[-1][0],
                                      out[0][1] - out[-1][1]) < 1e-9:
        out.pop()
    return out


def _face_of(polys: list[list[tuple[float, float]]]):
    """One face per layer: subpaths classified even-odd WITHIN the layer,
    so a glyph exported as a single path keeps its counters. Winding is
    NORMALIZED (outer CCW, holes CW): a mirrored path arrives wound the
    other way, and extruding a reversed face yields an inside-out solid
    that FUSES like a subtraction — the fish lost both a fin and its
    head to that before this guard."""
    import cadquery as cq

    def _signed_area(poly) -> float:
        return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1)
                   in zip(poly, poly[1:] + poly[:1])) / 2.0

    def _wire(poly, ccw: bool):
        pts = _dedupe(poly)
        if (_signed_area(pts) > 0) != ccw:
            pts = pts[::-1]
        return cq.Wire.makePolygon(
            [cq.Vector(x, y, 0) for x, y in pts], close=True)

    as_tuples = [tuple((x, y) for x, y in p) for p in polys]
    outlines, holes = classify_even_odd(as_tuples)
    faces = []
    for i, outline in enumerate(outlines):
        inner = [_wire(h, ccw=False) for parent, h in holes if parent == i]
        faces.append(cq.Face.makeFromWires(_wire(outline, ccw=True), inner))
    return faces


def _prisms(faces):
    import cadquery as cq

    return [cq.Solid.extrudeLinear(f, cq.Vector(0, 0, 1.0)) for f in faces]


def _loops_of(faces) -> list[list[tuple[float, float]]]:
    """Ordered vertex loops of every wire — booleans return edges
    unordered, so they are chained by endpoint matching."""
    out = []
    for f in faces:
        for w in f.Wires():
            segs = []
            for e in w.Edges():
                a, b = e.startPoint(), e.endPoint()
                segs.append(((a.x, a.y), (b.x, b.y)))
            if not segs:
                continue
            loop = [segs[0][0], segs[0][1]]
            rest = segs[1:]
            while rest:
                tail = loop[-1]
                for k, (p, q) in enumerate(rest):
                    if math.hypot(p[0] - tail[0], p[1] - tail[1]) < 1e-6:
                        loop.append(q); rest.pop(k); break
                    if math.hypot(q[0] - tail[0], q[1] - tail[1]) < 1e-6:
                        loop.append(p); rest.pop(k); break
                else:
                    raise RecipeError(
                        "svg flatten produced an open boundary — the "
                        "layer geometry is too degenerate to union")
            if math.hypot(loop[0][0] - loop[-1][0],
                          loop[0][1] - loop[-1][1]) < 1e-6:
                loop.pop()
            out.append(loop)
    return out


def _area(lp) -> float:
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1)
                   in zip(lp, lp[1:] + lp[:1]))) / 2.0


def _simplify(lp, tol: float):
    out = [lp[0]]
    for p in lp[1:]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= tol:
            out.append(p)
    while len(out) > 1 and math.hypot(out[0][0] - out[-1][0],
                                      out[0][1] - out[-1][1]) < tol:
        out.pop()
    return out


def _offset_wire(wire, r: float):
    import cadquery as cq

    return (cq.Workplane("XY").add([wire]).toPending()
            .offset2D(r, "arc").wires().vals())


def _opened_bottom_faces(solid, open_r: float):
    """Morphological opening of every bottom face's OUTER boundary —
    holes stay untouched (their webs are measured, not silently eaten)."""
    import cadquery as cq

    bottom = [f for f in solid.Faces() if abs(f.Center().z) < 1e-6]
    if open_r <= 0:
        return bottom
    opened = []
    for f in bottom:
        outer = f.outerWire()
        inners = [w for w in f.Wires() if not w.isSame(outer)]
        try:
            for ew in _offset_wire(outer, -open_r):
                for ow in _offset_wire(ew, open_r):
                    opened.append(cq.Face.makeFromWires(ow, inners))
        except Exception:
            # offset can reject a pathological boundary — keep the
            # original face; the min-width check stays the honest gate
            opened.append(f)
    if not opened:
        return bottom
    solids = _prisms(opened)
    fused = solids[0]
    for s in solids[1:]:
        fused = fused.fuse(s)
    fused = fused.clean()
    return [f for f in fused.Faces() if abs(f.Center().z) < 1e-6]


def flatten_svg_layers(
    svg_text: str,
    motif_w: float = 60.0,
    min_feature: float = MIN_FEATURE_MM,
) -> tuple[str, dict]:
    """Reduce a layered SVG document to single-level stamp path data.
    Returns ``(path_data, info)`` — path data in the source coordinate
    frame (ready for the ``svg_path`` param), info for the UI: layer
    counts, ink/paper split, loops kept, opening radius used."""
    layers = _layers(svg_text)
    n_ink = sum(1 for _, ink in layers if ink)
    if n_ink == 0:
        raise RecipeError(
            "every filled path is lighter than the ink threshold — "
            "nothing would be raised on the die")

    xs = [x for polys, _ in layers for p in polys for x, _y in p]
    raw_w = max(xs) - min(xs)
    if raw_w < 1e-9:
        raise RecipeError("svg is degenerate (zero-size bbox)")
    scale = motif_w / raw_w
    # opening radius: kill necks below the printable floor at the target
    # size, with head-room so legit floor-wide features survive
    open_r = 0.45 * min_feature / scale

    shape = None
    for polys, is_ink in layers:
        faces = _face_of(polys)
        if not faces:
            continue
        for prism in _prisms(faces):
            if is_ink:
                shape = prism if shape is None else shape.fuse(prism)
            elif shape is not None:
                shape = shape.cut(prism)
    if shape is None:
        raise RecipeError("no ink layers produced any geometry")
    shape = shape.clean()

    faces = _opened_bottom_faces(shape, open_r)
    loops = [_simplify(lp, tol=max(0.5, open_r / 4.0))
             for lp in _loops_of(faces)]
    loops = [lp for lp in loops if len(lp) >= 3]
    if not loops:
        raise RecipeError(
            "flattening left no printable area — the art is thinner "
            f"than {min_feature:g} mm everywhere at {motif_w:g} mm wide")
    biggest = max(_area(lp) for lp in loops)
    kept = [lp for lp in loops if _area(lp) > SLIVER_FRACTION * biggest]

    path_data = " ".join(
        "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in lp) + " Z"
        for lp in kept
    )
    info = {
        "layers": len(layers),
        "ink_layers": n_ink,
        "paper_layers": len(layers) - n_ink,
        "loops": len(kept),
        "slivers_dropped": len(loops) - len(kept),
        "opening_r_mm": round(open_r * scale, 3),
        "motif_w_mm": motif_w,
    }
    return path_data, info
