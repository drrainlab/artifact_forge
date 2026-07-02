"""Fastener holes — vertical clearance bores with conical countersinks.

Cone construction ported from v1 ``_countersink_screw_holes`` with the axis
remapped to Z (NG frame: screw axis is always Z). Per-hole best-effort:
a cut that would fragment the body is reverted, not shipped.
"""

from __future__ import annotations

import cadquery as cq

from ..core.fasteners import FDM_CLEARANCE, screw_spec
from ..form.part import HoleFeature
from .booleans import cut_keep_solid


def cut_countersunk_hole(
    body: cq.Workplane, hole: HoleFeature
) -> tuple[cq.Workplane, bool, bool]:
    """Returns (body, bored, countersunk)."""
    spec = screw_spec(hole.screw)
    x, y, z_top = hole.at
    bore_d = spec["clear"] + FDM_CLEARANCE
    bore = (
        cq.Workplane("XY", origin=(x, y, z_top + 1.0))
        .circle(bore_d / 2.0)
        .extrude(-(hole.through + 2.0))
    )
    body, bored = cut_keep_solid(body, bore)
    if not bored or not hole.countersink:
        return body, bored, False
    head_r = spec["head"] / 2.0
    cs_depth = min(2.0, hole.through * 0.4)
    if hole.countersink_face == "bottom":
        # Screw head seats on the underside; the desk-side face stays flat.
        apex, direction = cq.Vector(x, y, z_top - hole.through), cq.Vector(0, 0, 1)
    else:
        apex, direction = cq.Vector(x, y, z_top), cq.Vector(0, 0, -1)
    cone = cq.Solid.makeCone(head_r + 0.3, 0.5, cs_depth, apex, direction)
    body, sunk = cut_keep_solid(body, cq.Workplane(obj=cone))
    return body, bored, sunk
