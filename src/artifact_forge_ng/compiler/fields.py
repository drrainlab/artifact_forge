"""Cut a resolved perforation field — one compound cutter, one cut,
reverted whole if the body would fragment. Centers were already filtered
against keepouts at the IR level; this module never decides placement.
"""

from __future__ import annotations

import math

import cadquery as cq

from ..form.part import FieldFeature
from ..cad.booleans import cut_keep_solid


def _orient(cutter: cq.Workplane, field: FieldFeature) -> cq.Workplane:
    """Place a locally-built cutter into the world: rotate about +X by the
    field's tilt, then translate to its origin. Horizontal fields pass
    through untouched (they were built at plane_z already)."""
    if field.origin is None:
        return cutter
    if abs(field.tilt_deg) > 1e-9:
        cutter = cutter.rotate((0, 0, 0), (1, 0, 0), field.tilt_deg)
    return cutter.translate(field.origin)


def _cut_cylindrical_field(
    body: cq.Workplane, field: FieldFeature
) -> tuple[cq.Workplane, bool]:
    """cylindrical_z_mapping_v1: each cell polygon (local a=arc, b=height)
    is built FLAT in the tangent plane of its own centroid and extruded
    RADIALLY through the wall. The chord-vs-arc flattening error is bounded
    at the IR level (cells must stay small next to the radius)."""
    cx, cy = field.cyl_center
    r_out = field.cyl_r_outer
    depth = field.depth + 2.0
    cutter: cq.Workplane | None = None
    polys = list(field.polygons)
    if field.centers and field.pattern == "round":
        # round cells become short cylinders along the radial direction
        for a, b in field.centers:
            theta = a / field.cyl_r
            piece = (
                cq.Workplane("YZ", origin=(r_out + 1.0, 0.0, 0.0))
                .circle(field.cell / 2.0)
                .extrude(-depth)
                .translate((0, 0, field.cyl_z0 + b))
                .rotate((0, 0, 0), (0, 0, 1), math.degrees(theta))
                .translate((cx, cy, 0))
            )
            cutter = piece if cutter is None else cutter.union(piece)
    for poly in polys:
        ca = sum(p[0] for p in poly) / len(poly)
        theta = ca / field.cyl_r
        # polygon in the tangent plane: local x = (a - ca) (chord approx),
        # local y = b; built on the YZ plane at x = r_out+1, extruded inward
        wp = cq.Workplane("YZ", origin=(r_out + 1.0, 0.0, 0.0))
        pts = [((p[0] - ca), field.cyl_z0 + p[1]) for p in poly]
        wp = wp.moveTo(*pts[0])
        for pt in pts[1:]:
            wp = wp.lineTo(*pt)
        piece = (
            wp.close().extrude(-depth)
            .rotate((0, 0, 0), (0, 0, 1), math.degrees(theta))
            .translate((cx, cy, 0))
        )
        cutter = piece if cutter is None else cutter.union(piece)
    if cutter is None:
        return body, False
    return cut_keep_solid(body, cutter)


def cut_field(body: cq.Workplane, field: FieldFeature) -> tuple[cq.Workplane, bool]:
    if not field.centers and not field.polygons:
        return body, False
    if field.mapping == "cylindrical":
        return _cut_cylindrical_field(body, field)
    depth = field.depth + (2.0 if field.depth > 2.0 else 1.0)
    # Oriented fields build in the LOCAL frame: cells in the local XY plane
    # at z=0, cut along +Z (the inward normal after rotation); horizontal
    # fields keep the legacy plane_z / cut-down convention.
    oriented = field.origin is not None
    z_start = -1.0 if oriented else field.plane_z + 1.0
    extrude_by = (depth + 1.0) if oriented else -(depth + 1.0)
    cutter: cq.Workplane | None = None
    if field.centers and field.pattern == "round":
        # Circular cells (phyllotaxis etc.): the circle of diameter `cell`
        # is exactly the hexagon's inscribed circle, so every hex-based
        # ligament measure stays conservative for round cutters.
        for cx, cy in field.centers:
            piece = (
                cq.Workplane("XY", origin=(cx, cy, z_start))
                .circle(field.cell / 2.0)
                .extrude(extrude_by)
            )
            cutter = piece if cutter is None else cutter.union(piece)
    elif field.centers:
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
            wp = cq.Workplane("XY", origin=(0, 0, z_start)).moveTo(
                cx + vertices[0][0], cy + vertices[0][1]
            )
            for vx, vy in vertices[1:]:
                wp = wp.lineTo(cx + vx, cy + vy)
            piece = wp.close().extrude(extrude_by)
            cutter = piece if cutter is None else cutter.union(piece)
    for poly in field.polygons:
        wp = cq.Workplane("XY", origin=(0, 0, z_start)).moveTo(*poly[0])
        for pt in poly[1:]:
            wp = wp.lineTo(*pt)
        piece = wp.close().extrude(extrude_by)
        cutter = piece if cutter is None else cutter.union(piece)
    if cutter is None:
        return body, False
    return cut_keep_solid(body, _orient(cutter, field))
