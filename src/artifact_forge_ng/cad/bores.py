"""Axis-aligned cylinder and box cuts — the CAD side of BoreFeature and
CutBoxFeature. Placement was decided (and keepout-checked) at the IR level;
this module only cuts, with the revert-if-fragmenting discipline.
"""

from __future__ import annotations

import cadquery as cq

from ..form.part import BoreFeature, CutBoxFeature
from .booleans import cut_keep_solid

_AXIS_PLANES = {"X": "YZ", "Y": "XZ", "Z": "XY"}
_AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}


def cut_bore(body: cq.Workplane, bore: BoreFeature) -> tuple[cq.Workplane, bool]:
    idx = _AXIS_INDEX[bore.axis]
    origin = list(bore.center)
    origin[idx] = bore.span[0] - 1.0
    length = (bore.span[1] + 1.0) - (bore.span[0] - 1.0)
    cutter = (
        cq.Workplane(_AXIS_PLANES[bore.axis], origin=tuple(origin))
        .circle(bore.d / 2.0)
        .extrude(length)
    )
    return cut_keep_solid(body, cutter)


def cut_box(body: cq.Workplane, cut: CutBoxFeature) -> tuple[cq.Workplane, bool]:
    b = cut.box
    cutter = (
        cq.Workplane("XY", origin=((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2, b.z0))
        .rect(b.x1 - b.x0, b.y1 - b.y0)
        .extrude(b.z1 - b.z0)
    )
    return cut_keep_solid(body, cutter)
