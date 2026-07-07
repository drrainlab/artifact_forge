"""Developable ``profile_surface`` mapping (Bio-4M stage B).

The branch clamp is a constant YZ section extruded along X: a curved,
organic body, not a flat plate. This module unrolls that body into a flat
``(s, x)`` canvas the existing 2D exoskeleton machinery (substrate, graph,
ribs, windows) grows on unchanged — ``s`` is arc length along the section's
OUTER contour, ``x`` the extrusion offset. The map is DEVELOPABLE (a ruled
sweep of a planar curve), so ``(s, x)`` distances equal true surface
distances: ligaments and rib lengths stay honest.

Two hard decisions live here:

* **Seam at the mate block.** The canvas is NOT a periodic wrap — it is the
  external+fillet run of the contour, the complement of the contiguous
  mate/saddle block. The seam sits inside that block (off the canvas), so a
  rib graph never has to cross a discontinuity. The dovetail rail on the
  upper half is an INTERIOR keepout interval of the canvas, not a break.
* **Arc subdivision to a 0.05 mm chord error.** Every arc is chorded finely
  enough that a plain lerp of the stored knots reproduces the surface — the
  map carries no arc primitives, only points and normals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..section import ArcSeg, LineSeg, ProfileLoop, Seg
from .ir import ProfileSurfaceMap

#: Max chord deviation of a subdivided arc from the true arc (mm).
CHORD_TOL = 0.05

#: Segment-tag families the contour walk classifies into. The mate face and
#: the saddle (arcs + recessed pad lands) form the ONE contiguous block the
#: canvas is the complement of; the dovetail rail is an interior keepout.
_MATE_TAGS = frozenset({"mate_face"})
_SADDLE_TAGS = frozenset(
    {"saddle_contact", "cavity_inner", "contact", "pad_land", "pad_wall"}
)
_RAIL_TAGS = frozenset({"rail_flank", "rail_top"})
_CANVAS_TAGS = frozenset({"external", "fillet"})


def _classify(seg: Seg) -> str:
    """One of ``mate`` / ``saddle`` / ``rail`` / ``canvas`` — the rail check
    comes first (rail flanks are 'intentional_corner' too, and the mate/
    saddle test would otherwise never see them anyway)."""
    tags = seg.tags
    if tags & _RAIL_TAGS:
        return "rail"
    if tags & _MATE_TAGS:
        return "mate"
    if tags & _SADDLE_TAGS:
        return "saddle"
    if tags & _CANVAS_TAGS:
        return "canvas"
    # An untagged external wall (defensive): treat as canvas so material is
    # never silently excluded; the classifier is exhaustive for the clamp.
    return "canvas"


def _outward_normal(tangent_u: float, tangent_v: float) -> tuple[float, float]:
    """Outward unit normal of a CCW loop: interior is LEFT of travel, so
    outward is the tangent rotated -90 degrees."""
    mag = math.hypot(tangent_u, tangent_v)
    if mag < 1e-12:
        return (1.0, 0.0)
    tu, tv = tangent_u / mag, tangent_v / mag
    return (tv, -tu)


def _arc_subdivisions(seg: ArcSeg) -> int:
    r = seg.radius
    if r < 1e-9:
        return 1
    # chord error = r (1 - cos(dtheta/2)); solve dtheta for CHORD_TOL
    ratio = max(-1.0, min(1.0, 1.0 - CHORD_TOL / r))
    dtheta = 2.0 * math.acos(ratio)
    if dtheta < 1e-6:
        return 1
    return max(1, math.ceil(abs(seg.sweep) / dtheta))


def _seg_knots(seg: Seg) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Points + outward normals along one segment, EXCLUDING the start point
    (the previous segment already emitted it) and INCLUDING the end. Line
    segments emit just their end; arcs emit their chorded interior + end."""
    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    if isinstance(seg, LineSeg):
        t = seg.tangent_at_end()
        nrm = _outward_normal(t.u, t.v)
        out.append(((seg.b.u, seg.b.v), nrm))
        return out
    n = _arc_subdivisions(seg)
    for k in range(1, n + 1):
        frac = k / n
        p = seg.point_at(frac)
        ang = seg.start_angle + seg.sweep * frac
        tangent = seg._tangent(ang)
        nrm = _outward_normal(tangent.u, tangent.v)
        out.append(((p.u, p.v), nrm))
    return out


@dataclass(frozen=True)
class ProfileSurfaceCanvas:
    """The unrolled clamp body plus its usable growth interval.

    ``surface`` maps ``(s, x)`` to the world; ``[s0, s1]`` is the external+
    fillet canvas (``s0 == 0`` by construction — the walk starts at the
    canvas); ``rail_interval`` is the interior keepout the dovetail occupies
    (``None`` on the lower half); ``seam_s`` sits inside the mate/saddle
    block, guaranteed OUTSIDE ``[s0, s1]``."""

    surface: ProfileSurfaceMap
    s0: float
    s1: float
    rail_interval: tuple[float, float] | None
    seam_s: float


def _rotate_to_canvas(segments: list[Seg]) -> list[Seg]:
    """Rotate the loop so it STARTS at the first canvas/rail segment that
    follows the mate/saddle block — then ``s = 0`` is the canvas seam and the
    block lives at the high-``s`` end."""
    cats = [_classify(s) for s in segments]
    block = {"mate", "saddle"}
    n = len(segments)
    for i in range(n):
        if cats[i] not in block and cats[i - 1] in block:
            return segments[i:] + segments[:i]
    # No mate/saddle block at all (defensive) — leave as is.
    return segments


def build_profile_surface(loop: ProfileLoop, width: float) -> ProfileSurfaceMap:
    """Unroll the section's outer loop into a :class:`ProfileSurfaceMap`,
    starting the ``s`` parametrization at the canvas seam."""
    segments = _rotate_to_canvas(list(loop.segments))
    start = segments[0].a
    points: list[tuple[float, float]] = [(start.u, start.v)]
    # normal of the FIRST point: use the first segment's start tangent
    t0 = segments[0].tangent_at_start()
    normals: list[tuple[float, float]] = [_outward_normal(t0.u, t0.v)]
    s_breaks: list[float] = [0.0]
    s = 0.0
    for seg in segments:
        for (pu, pv), nrm in _seg_knots(seg):
            du = pu - points[-1][0]
            dv = pv - points[-1][1]
            step = math.hypot(du, dv)
            if step < 1e-7:
                # coincident knot (a zero-length trim): keep the newer normal
                normals[-1] = nrm
                continue
            s += step
            s_breaks.append(s)
            points.append((pu, pv))
            normals.append(nrm)
    return ProfileSurfaceMap(
        s_breaks=tuple(s_breaks),
        points=tuple(points),
        normals=tuple(normals),
        total_s=s,
        width=width,
    )


def profile_surface_canvas(
    loop: ProfileLoop, width: float
) -> ProfileSurfaceCanvas:
    """Unroll the loop AND locate the canvas interval + rail keepout + seam.

    ``s1`` is the arc length at the end of the last canvas/rail segment
    before the mate/saddle block resumes; the block occupies ``[s1, total]``
    and the seam is placed at its midpoint (never on the canvas)."""
    segments = _rotate_to_canvas(list(loop.segments))
    cats = [_classify(s) for s in segments]
    block = {"mate", "saddle"}
    surface = build_profile_surface(loop, width)

    # Re-walk the rotated segments accumulating arc length so we can mark the
    # canvas end and the rail interval in the SAME s-frame the map uses.
    s = 0.0
    last = (segments[0].a.u, segments[0].a.v)
    s1 = 0.0
    rail_lo: float | None = None
    rail_hi: float | None = None
    seen_block = False
    for seg, cat in zip(segments, cats):
        for (pu, pv), _n in _seg_knots(seg):
            step = math.hypot(pu - last[0], pv - last[1])
            if step >= 1e-7:
                s += step
                last = (pu, pv)
        if cat in block:
            seen_block = True
        elif not seen_block:
            # still inside the leading canvas run
            s1 = s
            if cat == "rail":
                if rail_lo is None:
                    rail_lo = s - seg.length
                rail_hi = s
    seam_s = (s1 + surface.total_s) / 2.0
    rail_interval = (
        (rail_lo, rail_hi) if rail_lo is not None and rail_hi is not None else None
    )
    return ProfileSurfaceCanvas(
        surface=surface,
        s0=0.0,
        s1=s1,
        rail_interval=rail_interval,
        seam_s=seam_s,
    )
