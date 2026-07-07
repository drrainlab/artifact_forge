"""Fastener holes — vertical clearance bores with conical countersinks.

Cone construction ported from v1 ``_countersink_screw_holes`` with the axis
remapped to Z (NG frame: screw axis is always Z). Per-hole best-effort:
a cut that would fragment the body is reverted, not shipped.

All cutter dimensions come from :func:`core.fasteners.hole_cut_dims` — the
same numbers the implicit-skin SDF hard cuts use, so the BRep and mesh
paths cannot drift apart.
"""

from __future__ import annotations

import cadquery as cq

from ..core.fasteners import hole_cut_dims
from ..form.part import HoleFeature
from .booleans import cut_keep_solid


def cut_countersunk_hole(
    body: cq.Workplane, hole: HoleFeature
) -> tuple[cq.Workplane, bool, bool]:
    """Returns (body, bored, countersunk)."""
    dims = hole_cut_dims(hole.screw, hole.through, hole.head_style)
    x, y, z_top = hole.at
    bore = (
        cq.Workplane("XY", origin=(x, y, z_top + 1.0))
        .circle(dims["bore_d"] / 2.0)
        .extrude(-(hole.through + 2.0))
    )
    body, bored = cut_keep_solid(body, bore)
    if not bored or not hole.countersink:
        return body, bored, False
    if hole.head_style == "cylinder":
        # Counterbore: a flat-bottomed cylindrical recess for a socket-cap
        # head — depth swallows the head, never more than half the stock.
        cb_depth = dims["cb_depth"]
        if hole.countersink_face == "bottom":
            z_start = z_top - hole.through - 1.0
            cutter = (
                cq.Workplane("XY", origin=(x, y, z_start))
                .circle(dims["seat_r"])
                .extrude(cb_depth + 1.0)
            )
        else:
            cutter = (
                cq.Workplane("XY", origin=(x, y, z_top + 1.0))
                .circle(dims["seat_r"])
                .extrude(-(cb_depth + 1.0))
            )
        body, sunk = cut_keep_solid(body, cutter)
        return body, bored, sunk
    cs_depth = dims["cs_depth"]
    if hole.countersink_face == "bottom":
        # Screw head seats on the underside; the desk-side face stays flat.
        apex, direction = cq.Vector(x, y, z_top - hole.through), cq.Vector(0, 0, 1)
    else:
        apex, direction = cq.Vector(x, y, z_top), cq.Vector(0, 0, -1)
    cone = cq.Solid.makeCone(dims["seat_r"], dims["cs_tip_r"], cs_depth, apex, direction)
    body, sunk = cut_keep_solid(body, cq.Workplane(obj=cone))
    return body, bored, sunk
