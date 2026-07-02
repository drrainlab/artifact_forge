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
    if not field.centers:
        return body, False
    # polygon() takes the circumscribed diameter; cell is across-flats.
    circum_d = field.cell * 2.0 / math.sqrt(3.0)
    cutter = (
        cq.Workplane("XY", origin=(0, 0, field.plane_z + 1.0))
        .pushPoints(list(field.centers))
        .polygon(6, circum_d)
        .extrude(-(field.depth + 2.0))
    )
    return cut_keep_solid(body, cutter)
