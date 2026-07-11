"""Helical thread solids for ThreadFeature — OCC helix + profile sweep.
The printable truncated 60-degree form: ridge/groove depth = 0.6*pitch,
crest flattened to a third of the pitch. External ridges WELD onto the
stud core; internal grooves CUT out from the bore wall."""
from __future__ import annotations

import cadquery as cq

from ..form.part import ThreadFeature


def build_thread_solid(tr: ThreadFeature) -> cq.Workplane:
    """The helical ridge (external) or groove cutter (internal),
    positioned in world coordinates."""
    depth = tr.depth
    p = tr.pitch
    if tr.internal:
        # groove: rides the bore wall, cutting outward
        r_path = tr.major_d / 2.0 - depth  # the bore wall radius
        direction = 1.0                     # outward
    else:
        # ridge: rides the stud core, welding outward
        r_path = tr.core_r
        direction = 1.0
    helix = cq.Wire.makeHelix(
        p, tr.length, r_path, lefthand=(tr.handed == "left"))
    # truncated triangle in the (radial, axial) plane at the helix start
    # (+X): base 0.75p tall on the path radius, crest flat p/4
    base_h = 0.375 * p
    crest_h = 0.125 * p
    # the base sinks 0.3 into the host (weld interpenetration for the
    # external ridge; harmless void overlap for the internal cutter)
    profile = (
        cq.Workplane("XZ", origin=(r_path, 0, 0))
        .polyline([
            (-direction * 0.3, -base_h),
            (direction * depth, -crest_h),
            (direction * depth, crest_h),
            (-direction * 0.3, base_h),
        ])
        .close()
    )
    swept = profile.sweep(cq.Workplane(obj=helix), isFrenet=True)
    return swept.translate((tr.at[0], tr.at[1], tr.z0))
