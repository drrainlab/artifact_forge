"""Cut a resolved perforation field — one compound cutter, one cut,
reverted whole if the body would fragment. Centers were already filtered
against keepouts at the IR level; this module never decides placement.
"""

from __future__ import annotations

import math

import cadquery as cq

from ..form.part import FieldFeature
from ..cad.booleans import cut_keep_solid


def cut_field(body: cq.Workplane, field: FieldFeature) -> tuple[cq.Workplane, bool]:
    if not field.centers and not field.polygons:
        return body, False
    depth = field.depth + (2.0 if field.depth > 2.0 else 1.0)
    cutter: cq.Workplane | None = None
    if field.centers:
        # Hexagons FLAT-TO-FLAT along the row axis (vertices at 30+60k
        # degrees): cadquery's polygon() is pointy-right, which faces
        # vertices at row neighbours and thins the webs to ~half the
        # declared gap — caught by form.min_ligament_ok.
        r_hex = field.cell / math.sqrt(3.0)
        vertices = [
            (r_hex * math.cos(math.radians(30 + 60 * k)),
             r_hex * math.sin(math.radians(30 + 60 * k)))
            for k in range(6)
        ]
        for cx, cy in field.centers:
            wp = cq.Workplane("XY", origin=(0, 0, field.plane_z + 1.0)).moveTo(
                cx + vertices[0][0], cy + vertices[0][1]
            )
            for vx, vy in vertices[1:]:
                wp = wp.lineTo(cx + vx, cy + vy)
            piece = wp.close().extrude(-(depth + 1.0))
            cutter = piece if cutter is None else cutter.union(piece)
    for poly in field.polygons:
        wp = cq.Workplane("XY", origin=(0, 0, field.plane_z + 1.0)).moveTo(*poly[0])
        for pt in poly[1:]:
            wp = wp.lineTo(*pt)
        piece = wp.close().extrude(-(depth + 1.0))
        cutter = piece if cutter is None else cutter.union(piece)
    if cutter is None:
        return body, False
    return cut_keep_solid(body, cutter)
