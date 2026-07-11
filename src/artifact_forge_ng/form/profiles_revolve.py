"""Shared polyline helpers for revolve-based recipe ops (``profile_revolve``
half-sections in XZ, axis = Z). Every joint of these technical silhouettes
is a machined-style corner by design (barb teeth, flange steps, chamfers) —
tagged intentional so form.profile_smooth judges styled parts, not these.
"""
from __future__ import annotations

from .section import LineSeg, ProfileLoop, Pt


def sawtooth(points: list[Pt], r_root: float, r_crest: float,
             v0: float, v1: float, count: int, toward_tip_at_v0: bool) -> None:
    """Append barb sawtooth points between v0 and v1 (v0 < v1). The sharp
    (vertical) face looks toward the flange so the hose slides on from the
    tip and bites against pull-off."""
    pitch = (v1 - v0) / count
    ramp = 0.75 * pitch
    if toward_tip_at_v0:
        # tip at v0: each tooth ramps gently away from the tip, then drops
        # vertically (the sharp face looks toward the flange at v1)
        for k in range(count):
            a = v0 + k * pitch
            points.append(Pt(r_root, a))
            points.append(Pt(r_crest, a + ramp))
            points.append(Pt(r_root, a + ramp))
        points.append(Pt(r_root, v1))
    else:
        # tip at v1: mirrored — flat toward the flange, vertical sharp face
        # (looking toward v0), then a gentle ramp descending to the tip side
        points.append(Pt(r_root, v0))
        for k in range(count):
            a = v0 + k * pitch
            points.append(Pt(r_root, a + pitch - ramp))
            points.append(Pt(r_crest, a + pitch - ramp))
            points.append(Pt(r_root, a + pitch))


def loop_from_points(points: list[Pt]) -> ProfileLoop:
    """Closed polyline loop with every joint tagged as an intentional
    corner. Zero-length segments (coincident consecutive points) are
    dropped so callers can emit degenerate steps freely."""
    segs = []
    for a, b in zip(points, points[1:] + points[:1]):
        if a.dist(b) > 1e-6:
            segs.append(LineSeg(a, b, tags=frozenset({"intentional_corner"})))
    return ProfileLoop(segs)
