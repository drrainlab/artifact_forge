"""Rounded-rectangle plate profiles — an exact 4-line/4-arc loop. All
joints are tangent by construction, so no molded pass is needed.
"""

from __future__ import annotations

from .section import ArcSeg, LineSeg, ProfileLoop, Pt, Seg


def rounded_rect_loop(
    u0: float,
    v0: float,
    u1: float,
    v1: float,
    corner_r: float,
    tags: frozenset[str] = frozenset({"external"}),
) -> ProfileLoop:
    r = max(0.0, min(corner_r, (u1 - u0) / 2 - 1e-6, (v1 - v0) / 2 - 1e-6))
    if r < 1e-6:
        pts = [Pt(u0, v0), Pt(u1, v0), Pt(u1, v1), Pt(u0, v1)]
        return ProfileLoop(
            [LineSeg(a, b, tags) for a, b in zip(pts, pts[1:] + pts[:1])]
        )
    segs: list[Seg] = [
        LineSeg(Pt(u0 + r, v0), Pt(u1 - r, v0), tags),
        ArcSeg(Pt(u1 - r, v0), Pt(u1, v0 + r), Pt(u1 - r, v0 + r), ccw=True, tags=tags),
        LineSeg(Pt(u1, v0 + r), Pt(u1, v1 - r), tags),
        ArcSeg(Pt(u1, v1 - r), Pt(u1 - r, v1), Pt(u1 - r, v1 - r), ccw=True, tags=tags),
        LineSeg(Pt(u1 - r, v1), Pt(u0 + r, v1), tags),
        ArcSeg(Pt(u0 + r, v1), Pt(u0, v1 - r), Pt(u0 + r, v1 - r), ccw=True, tags=tags),
        LineSeg(Pt(u0, v1 - r), Pt(u0, v0 + r), tags),
        ArcSeg(Pt(u0, v0 + r), Pt(u0 + r, v0), Pt(u0 + r, v0 + r), ccw=True, tags=tags),
    ]
    return ProfileLoop(segs)
