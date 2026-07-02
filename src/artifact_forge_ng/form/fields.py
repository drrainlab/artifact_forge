"""Perforation fields with keepouts — resolved at the IR level.

Hex centers are computed in 2D (ported from v1 ``featurespec._pattern_centers``
hex staggering) and filtered against keepout regions BEFORE any geometry is
cut, so "no cell touches a screw zone" is a countable IR assertion, not a
hope about boolean ops.
"""

from __future__ import annotations

import math

from .part import FieldFeature
from .regions import Rect2D, Region2D
from .section import Pt


def hex_field_centers(
    window: Rect2D, cell: float, wall_gap: float
) -> list[tuple[float, float]]:
    """Staggered hex-grid centers filling ``window``. ``cell`` is the
    hexagon across-flats size; ``wall_gap`` the web left between cells."""
    if window.width <= 0 or window.height <= 0:
        return []
    pitch = cell + wall_gap
    if pitch <= 0:
        return []
    row_pitch = pitch * 0.87  # staggered rows (v1 constant)
    centers: list[tuple[float, float]] = []
    row = 0
    v = window.v0
    while v <= window.v1 + 1e-9:
        offset = pitch / 2.0 if row % 2 else 0.0
        u = window.u0 + offset
        while u <= window.u1 + 1e-9:
            centers.append((u, v))
            u += pitch
        v += row_pitch
        row += 1
    return centers


def apply_field_with_keepouts(
    window: Rect2D,
    keepouts: list[Region2D],
    cell: float,
    wall_gap: float,
    margin: float,
    plane_z: float,
    depth: float,
) -> FieldFeature:
    """Hex field over ``window`` minus ``keepouts``. A cell survives only if
    its circumcircle clears every keepout by that keepout's clearance."""
    inner = window.shrunk(margin)
    r_hex = cell / math.sqrt(3.0)  # circumradius of the across-flats hexagon
    kept: list[tuple[float, float]] = []
    for cu, cv in hex_field_centers(inner, cell, wall_gap):
        p = Pt(cu, cv)
        if not inner.contains(p):
            continue
        if all(k.shape.distance(p) > r_hex + k.clearance for k in keepouts):
            kept.append((cu, cv))
    return FieldFeature(
        plane_z=plane_z,
        centers=tuple(kept),
        cell=cell,
        depth=depth,
        pattern="hex",
        window=window,
        keepouts=tuple(keepouts),
        min_ligament=wall_gap,
    )
