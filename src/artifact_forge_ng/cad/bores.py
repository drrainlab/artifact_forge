"""Axis-aligned cylinder and box cuts — the CAD side of BoreFeature and
CutBoxFeature — plus the sloped U-channel cutter (ChannelCutFeature), the
one deliberately non-axis-aligned subtraction in the kernel. Placement was
decided (and keepout-checked) at the IR level; this module only cuts, with
the revert-if-fragmenting discipline.
"""

from __future__ import annotations

import math

import cadquery as cq

from ..form.part import BoreFeature, ChannelCutFeature, CutBoxFeature
from .booleans import cut_keep_solid

_AXIS_PLANES = {"X": "YZ", "Y": "XZ", "Z": "XY"}
_AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}
#: cadquery's named "XZ" plane has normal -Y — extrude NEGATIVE to go +Y
#: (the same trap as extrude_section_profile; one convention, one fix).
_AXIS_SIGN = {"X": 1.0, "Y": -1.0, "Z": 1.0}


def cut_bore(body: cq.Workplane, bore: BoreFeature) -> tuple[cq.Workplane, bool]:
    idx = _AXIS_INDEX[bore.axis]
    origin = list(bore.center)
    lo = bore.span[0] - bore.overshoot[0]
    hi = bore.span[1] + bore.overshoot[1]
    origin[idx] = lo
    length = hi - lo
    cutter = (
        cq.Workplane(_AXIS_PLANES[bore.axis], origin=tuple(origin))
        .circle(bore.d / 2.0)
        .extrude(_AXIS_SIGN[bore.axis] * length)
    )
    return cut_keep_solid(body, cutter)


def _u_wire(wp: cq.Workplane, half_w: float, depth: float, r: float) -> cq.Workplane:
    """One closed U cross-section on an XZ workplane: local u = world X
    (offset from the channel centerline), local v = world Z (0 at z_top).
    Opens 2 mm ABOVE the top face so the boolean never leaves a skin.
    Bottom corners are quarter-rounds built with threePointArc — the arc
    midpoint is computed from the fillet center, so there is no radius-sign
    ambiguity to get backwards on a flipped plane."""
    if r < 0.05:
        return (
            wp.moveTo(-half_w, 2.0)
            .lineTo(-half_w, -depth)
            .lineTo(half_w, -depth)
            .lineTo(half_w, 2.0)
            .close()
        )
    k = r / math.sqrt(2.0)
    left_mid = (-(half_w - r) - k, -(depth - r) - k)
    right_mid = ((half_w - r) + k, -(depth - r) - k)
    return (
        wp.moveTo(-half_w, 2.0)
        .lineTo(-half_w, -(depth - r))
        .threePointArc(left_mid, (-(half_w - r), -depth))
        .lineTo(half_w - r, -depth)
        .threePointArc(right_mid, (half_w, -(depth - r)))
        .lineTo(half_w, 2.0)
        .close()
    )


def cut_channel(
    body: cq.Workplane, ch: ChannelCutFeature, overshoot: float = 1.0
) -> tuple[cq.Workplane, bool]:
    """Cut the sloped open U-channel: a ruled loft between two U wires at
    the (overshot) inlet and outlet stations. The overshoot pushes the
    cutter through both end faces — the channel is open by construction —
    and the depths are extrapolated along the same line, so the floor
    slope is exact all the way through."""
    s = 1.0 if ch.y1 > ch.y0 else -1.0
    ya = ch.y0 - s * overshoot
    yb = ch.y1 + s * overshoot
    da = ch.depth_at(ya)
    db = ch.depth_at(yb)
    if min(da, db) <= ch.bottom_r + 1e-6:
        # The extrapolated shallow end would lose its floor radius — the IR
        # checks own this band; refuse to build garbage.
        return body, False
    half_w = ch.width / 2.0
    # cadquery's named "XZ" plane has normal -Y: a positive workplane offset
    # moves toward -Y, so the second station sits at offset (ya - yb).
    wp = cq.Workplane("XZ", origin=(ch.center_x, ya, ch.z_top))
    wp = _u_wire(wp, half_w, da, ch.bottom_r)
    wp = wp.workplane(offset=ya - yb)
    wp = _u_wire(wp, half_w, db, ch.bottom_r)
    try:
        cutter = wp.loft(ruled=True, combine=False)
    except Exception:  # noqa: BLE001 — OCC raises anything
        return body, False
    return cut_keep_solid(body, cutter)


def cut_box(body: cq.Workplane, cut: CutBoxFeature) -> tuple[cq.Workplane, bool]:
    b = cut.box
    cutter = (
        cq.Workplane("XY", origin=((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2, b.z0))
        .rect(b.x1 - b.x0, b.y1 - b.y0)
        .extrude(b.z1 - b.z0)
    )
    return cut_keep_solid(body, cutter)
