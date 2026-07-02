"""Section profile -> CadQuery wire -> solid.

Arcs in the IR become true circular arcs in the wire (``threePointArc`` —
more numerically forgiving than radiusArc's sign conventions), so the STEP
surface is exact, not a faceted approximation.
"""

from __future__ import annotations

import cadquery as cq

from ..form.section import ArcSeg, LineSeg, ProfileLoop, SectionProfile

_PLANE_NAMES = {"YZ": "YZ", "XZ": "XZ", "XY": "XY"}


def wire_from_loop(loop: ProfileLoop, plane: str) -> cq.Workplane:
    wp = cq.Workplane(_PLANE_NAMES[plane])
    start = loop.segments[0].a
    wp = wp.moveTo(start.u, start.v)
    for seg in loop.segments:
        if isinstance(seg, LineSeg):
            wp = wp.lineTo(seg.b.u, seg.b.v)
        elif isinstance(seg, ArcSeg):
            mid = seg.point_at(0.5)
            wp = wp.threePointArc((mid.u, mid.v), (seg.b.u, seg.b.v))
        else:  # pragma: no cover - Seg union is exhaustive
            raise TypeError(f"unknown segment type {type(seg).__name__}")
    return wp.close()


#: cadquery's named "XZ" plane has normal -Y; plane_mapping puts the width
#: along +axis, so XZ sections extrude NEGATIVE to land in [0, +width].
_EXTRUDE_SIGN = {"YZ": 1.0, "XY": 1.0, "XZ": -1.0}


def extrude_section_profile(profile: SectionProfile, width: float) -> cq.Workplane:
    """Extrude the (already molded) section along its width axis, spanning
    [0, width] on the positive side per the ``plane_mapping`` convention."""
    span = _EXTRUDE_SIGN[profile.plane] * width
    solid = wire_from_loop(profile.outer, profile.plane).extrude(span)
    for void in profile.voids:
        cutter = wire_from_loop(void, profile.plane).extrude(span)
        solid = solid.cut(cutter)
    return solid


def revolve_section_profile(profile: SectionProfile) -> cq.Workplane:
    """Revolve a half-section 360 degrees into a solid of revolution.

    Convention: plane XZ — local x is the radial coordinate u, local y is
    the axial coordinate v, and the revolve axis (local (0,0)->(0,1)) is the
    global Z axis. The half-section must stay strictly on the +u side
    (validated at the IR level by form.revolve_profile_clear_of_axis).
    """
    if profile.plane != "XZ":
        raise ValueError(
            f"profile_revolve expects plane XZ (radial, axial); got {profile.plane!r}"
        )
    wp = wire_from_loop(profile.outer, profile.plane)
    return wp.revolve(360.0, (0, 0), (0, 1))
