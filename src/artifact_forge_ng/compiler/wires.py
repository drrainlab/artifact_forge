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


def extrude_section_profile(profile: SectionProfile, width: float) -> cq.Workplane:
    """Extrude the (already molded) section along its width axis.

    For plane YZ the workplane normal is +X, so ``extrude(width)`` spans
    x in [0, width] — exactly the ``plane_mapping`` convention.
    """
    solid = wire_from_loop(profile.outer, profile.plane).extrude(width)
    for void in profile.voids:
        cutter = wire_from_loop(void, profile.plane).extrude(width)
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
