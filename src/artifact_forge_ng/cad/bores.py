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


def cut_box(body: cq.Workplane, cut: CutBoxFeature) -> tuple[cq.Workplane, bool]:
    b = cut.box
    cutter = (
        cq.Workplane("XY", origin=((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2, b.z0))
        .rect(b.x1 - b.x0, b.y1 - b.y0)
        .extrude(b.z1 - b.z0)
    )
    return cut_keep_solid(body, cutter)
