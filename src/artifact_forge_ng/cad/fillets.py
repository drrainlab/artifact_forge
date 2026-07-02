"""Safe fillets — ported v1 ``_safe_fillet_v2`` discipline with region-box
edge selection instead of string selectors (string selectors were a v1
axis-bug vector).
"""

from __future__ import annotations

import cadquery as cq

from ..form.regions import Box3


def edges_in_box(wp: cq.Workplane, zone: Box3) -> list[cq.occ_impl.shapes.Edge]:
    """Edges whose center sits inside the part-frame box."""
    picked = []
    for edge in wp.edges().vals():
        c = edge.Center()
        if zone.contains(c.x, c.y, c.z):
            picked.append(edge)
    return picked


def safe_fillet_edges(
    body: cq.Workplane,
    edges: list,
    radius: float,
    min_length: float = 0.0,
) -> tuple[cq.Workplane, bool]:
    """Fillet the given edges, keeping the result only if it stays ONE valid
    solid (the v1 discipline — never silently ship a degenerate fillet)."""
    try:
        if min_length > 0:
            edges = [e for e in edges if e.Length() > min_length]
        if not edges:
            return body, False
        result = body.newObject(edges).fillet(radius)
        solids = result.solids().vals()
        if len(solids) == 1 and solids[0].isValid():
            return result, True
    except Exception:
        pass
    return body, False


def safe_fillet_ladder(
    body: cq.Workplane,
    zone: Box3,
    radii: tuple[float, ...],
    min_length: float = 0.0,
) -> tuple[cq.Workplane, float | None]:
    """Try each radius in turn (largest first); return (body, applied_radius).
    All-skipped is a WARN for the caller, not a crash — a missing blend is a
    style defect, a broken solid is a product defect."""
    for r in radii:
        if r < 0.2:
            continue
        edges = edges_in_box(body, zone)
        result, ok = safe_fillet_edges(body, edges, r, min_length)
        if ok:
            return result, r
    return body, None
