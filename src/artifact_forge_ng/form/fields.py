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
    """Staggered hex-grid centers filling ``window``, CENTERED on it.
    ``cell`` is the hexagon across-flats size; ``wall_gap`` the web left
    between cells.

    The lattice is anchored on the window CENTER, not a corner — a
    corner-anchored grid dumps the whole leftover margin on one side, so a
    symmetric part prints with a visibly off-center pattern (the wall tool
    mount lesson). Rows ±j share the same stagger parity and every row is
    centered in u, so a symmetric window yields a mirror-symmetric pattern
    in BOTH axes by construction."""
    if window.width <= 0 or window.height <= 0:
        return []
    pitch = cell + wall_gap
    if pitch <= 0:
        return []
    row_pitch = pitch * 0.87  # staggered rows (v1 constant)
    mid_u = (window.u0 + window.u1) / 2.0
    mid_v = (window.v0 + window.v1) / 2.0
    half_w = window.width / 2.0
    # As many rows as the corner grid would fit, as a stack CENTERED on the
    # window: odd counts give strict (u,−v) point symmetry, even counts a
    # mid-gap-symmetric stack (strict point symmetry is impossible for an
    # even staggered stack without collapsing the hex packing).
    n_rows = int((window.height + 1e-9) // row_pitch) + 1
    mid_j = (n_rows - 1) / 2.0
    centers: list[tuple[float, float]] = []
    for j in range(n_rows):
        v = mid_v + (j - mid_j) * row_pitch
        # stagger parity anchored on the middle row, so mirror rows of an
        # odd stack share their u-pattern
        if (j - (n_rows - 1) // 2) % 2 == 0:
            cols = int((half_w + 1e-9) // pitch)
            us = [mid_u + i * pitch for i in range(-cols, cols + 1)]
        else:
            # staggered row: symmetric pairs at ±(i + 0.5) * pitch
            us = []
            i = 0
            while (i + 0.5) * pitch <= half_w + 1e-9:
                us.extend((mid_u - (i + 0.5) * pitch, mid_u + (i + 0.5) * pitch))
                i += 1
        centers.extend((u, v) for u in sorted(us))
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
