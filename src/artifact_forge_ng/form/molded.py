"""The molded pass — replace sharp profile corners with tangent arcs.

This is where ~90% of the "molded utility part" look lives: because the
rounding happens in exact 2D, the extruded solid needs almost no fragile
3D fillets. Line-line corners use the closed-form tangent fillet; line-arc
corners solve the tangent-circle problem; a corner whose radius cannot fit
is left sharp and reported by the smoothness validator (WARN), never
silently mangled.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .section import ArcSeg, LineSeg, ProfileLoop, Pt, Seg
from .style import SurfaceStyle

#: Joints carrying any of these tags are intentional corners (e.g. the neck
#: top edge that welds into the flange) — never rounded, never flagged.
INTENTIONAL_TAGS = frozenset({"weld_joint", "intentional_corner"})

_TANGENT_TOL_DEG = 1.0
_MIN_FILLET_R = 0.2
_MAX_SETBACK_FRACTION = 0.45


def joint_is_tangent(prev: Seg, nxt: Seg) -> bool:
    t1, t2 = prev.tangent_at_end(), nxt.tangent_at_start()
    dot = max(-1.0, min(1.0, t1.dot(t2)))
    return math.degrees(math.acos(dot)) <= _TANGENT_TOL_DEG


@dataclass(frozen=True)
class _Fillet:
    new_prev: Seg
    arc: ArcSeg
    new_next: Seg


def _trim_line_to(seg: LineSeg, new_end: Pt, at_end: bool) -> LineSeg:
    return (
        LineSeg(seg.a, new_end, seg.tags) if at_end else LineSeg(new_end, seg.b, seg.tags)
    )


def _trim_arc_to(seg: ArcSeg, new_end: Pt, at_end: bool) -> ArcSeg:
    return (
        ArcSeg(seg.a, new_end, seg.center, seg.ccw, seg.tags)
        if at_end
        else ArcSeg(new_end, seg.b, seg.center, seg.ccw, seg.tags)
    )


def _fillet_line_line(prev: LineSeg, nxt: LineSeg, r: float) -> _Fillet | None:
    p = prev.b
    e1 = (prev.a - p).unit()  # away from the corner along prev
    e2 = (nxt.b - p).unit()  # away along next
    cos_theta = max(-1.0, min(1.0, e1.dot(e2)))
    theta = math.acos(cos_theta)
    if theta < math.radians(2) or theta > math.radians(178):
        return None  # near-straight or degenerate spike
    setback = r / math.tan(theta / 2.0)
    max_setback = _MAX_SETBACK_FRACTION * min(prev.length, nxt.length)
    if setback > max_setback:
        setback = max_setback
        r = setback * math.tan(theta / 2.0)
        if r < _MIN_FILLET_R:
            return None
    t1 = p + e1.scaled(setback)
    t2 = p + e2.scaled(setback)
    bisector = (e1 + e2).unit()
    center = p + bisector.scaled(r / math.sin(theta / 2.0))
    ccw = prev.tangent_at_end().cross(nxt.tangent_at_start()) > 0
    return _Fillet(
        _trim_line_to(prev, t1, at_end=True),
        ArcSeg(t1, t2, center, ccw, frozenset({"fillet"})),
        _trim_line_to(nxt, t2, at_end=False),
    )


def _solve_line_arc(
    p: Pt, line_dir: Pt, arc: ArcSeg, r: float
) -> tuple[Pt, Pt, Pt] | None:
    """Fillet circle of radius ``r`` tangent to the line ``p + s*line_dir``
    (s > 0) and to the arc's circle, near the shared corner ``p``.

    Returns (fillet_center, tangent_point_on_line, tangent_point_on_arc) for
    the best candidate, or None. Tries both line sides and both internal /
    external arc tangency, keeping solutions whose tangent points sit near
    the corner and on the positive line side.
    """
    c, big_r = arc.center, arc.radius
    best: tuple[float, Pt, Pt, Pt] | None = None
    for side in (1.0, -1.0):
        n = line_dir.perp().scaled(side)
        for k in (big_r - r, big_r + r):
            if k <= 0:
                continue
            # |p + s*d + r*n - c|^2 = k^2  ->  quadratic in s
            w = p + n.scaled(r) - c
            b = 2.0 * w.dot(line_dir)
            cc = w.dot(w) - k * k
            disc = b * b - 4.0 * cc
            if disc < 0:
                continue
            sq = math.sqrt(disc)
            for s in ((-b - sq) / 2.0, (-b + sq) / 2.0):
                if s <= 1e-6:
                    continue
                center = p + line_dir.scaled(s) + n.scaled(r)
                t_line = p + line_dir.scaled(s)
                delta = center - c
                if delta.norm() < 1e-9:
                    continue
                t_arc = c + delta.unit().scaled(big_r)
                # The tangency must land ON the arc — on a nearly straight
                # (huge-radius, bowed) arc the mirror root sits a fraction
                # of a degree PAST the endpoint and scores identically.
                if not _arc_contains_point(arc, t_arc):
                    continue
                # Prefer the tightest fillet that stays near the corner.
                score = t_line.dist(p) + t_arc.dist(p)
                if score > 8.0 * r + 2.0:
                    continue
                if best is None or score < best[0]:
                    best = (score, center, t_line, t_arc)
    if best is None:
        return None
    return best[1], best[2], best[3]


def _arc_contains_point(arc: ArcSeg, p: Pt) -> bool:
    ang = math.atan2(p.v - arc.center.v, p.u - arc.center.u)
    start, sweep = arc.start_angle, arc.sweep
    delta = ang - start
    if sweep >= 0:
        while delta < 0:
            delta += math.tau
        return delta <= sweep + 1e-6
    while delta > 0:
        delta -= math.tau
    return delta >= sweep - 1e-6


def _fillet_line_arc(prev: Seg, nxt: Seg, r: float) -> _Fillet | None:
    """One of (prev, nxt) is a line, the other an arc, sharing corner."""
    p = prev.b
    if isinstance(prev, LineSeg) and isinstance(nxt, ArcSeg):
        line, arc, line_is_prev = prev, nxt, True
        line_dir = (prev.a - p).unit()
    elif isinstance(prev, ArcSeg) and isinstance(nxt, LineSeg):
        line, arc, line_is_prev = nxt, prev, False
        line_dir = (nxt.b - p).unit()
    else:
        return None
    max_setback = _MAX_SETBACK_FRACTION * min(prev.length, nxt.length)
    while r >= _MIN_FILLET_R:
        solved = _solve_line_arc(p, line_dir, arc, r)
        if solved is not None:
            center, t_line, t_arc = solved
            if (
                t_line.dist(p) <= max_setback
                and t_arc.dist(p) <= max(max_setback, 2.0 * r)
                and _arc_contains_point(arc, t_arc)
            ):
                if line_is_prev:
                    new_prev: Seg = _trim_line_to(line, t_line, at_end=True)
                    new_next: Seg = _trim_arc_to(arc, t_arc, at_end=False)
                    a, b = t_line, t_arc
                else:
                    new_prev = _trim_arc_to(arc, t_arc, at_end=True)
                    new_next = _trim_line_to(line, t_line, at_end=False)
                    a, b = t_arc, t_line
                ccw = prev.tangent_at_end().cross(nxt.tangent_at_start()) > 0
                try:
                    fillet = ArcSeg(a, b, center, ccw, frozenset({"fillet"}))
                except ValueError:
                    return None
                return _Fillet(new_prev, fillet, new_next)
        r *= 0.6  # shrink and retry — a smaller blend beats a sharp corner
    return None


def _fillet_arc_arc(prev: ArcSeg, nxt: ArcSeg, r: float) -> _Fillet | None:
    """Tangent fillet between two arcs: the fillet center sits at distance
    R_i +- r from each arc's center — a circle-circle intersection. Bowed
    (nearly straight, huge-radius) arcs make this well-conditioned."""
    p = prev.b
    max_setback = _MAX_SETBACK_FRACTION * min(prev.length, nxt.length)
    while r >= _MIN_FILLET_R:
        best: tuple[float, Pt, Pt, Pt] | None = None
        for k1 in (prev.radius - r, prev.radius + r):
            for k2 in (nxt.radius - r, nxt.radius + r):
                if k1 <= 0 or k2 <= 0:
                    continue
                d = nxt.center - prev.center
                dist = d.norm()
                if dist < 1e-9:
                    continue
                # circle-circle intersection (centers prev.center/nxt.center,
                # radii k1/k2)
                a = (k1 * k1 - k2 * k2 + dist * dist) / (2.0 * dist)
                h2 = k1 * k1 - a * a
                if h2 < 0:
                    continue
                h = math.sqrt(h2)
                base = prev.center + d.unit().scaled(a)
                for sign in (1.0, -1.0):
                    center = base + d.unit().perp().scaled(sign * h)
                    t1 = prev.center + (center - prev.center).unit().scaled(prev.radius)
                    t2 = nxt.center + (center - nxt.center).unit().scaled(nxt.radius)
                    score = t1.dist(p) + t2.dist(p)
                    if score > 8.0 * r + 2.0:
                        continue
                    if not (_arc_contains_point(prev, t1) and _arc_contains_point(nxt, t2)):
                        continue
                    if t1.dist(p) > max_setback or t2.dist(p) > max_setback:
                        continue
                    if best is None or score < best[0]:
                        best = (score, center, t1, t2)
        if best is not None:
            _, center, t1, t2 = best
            ccw = prev.tangent_at_end().cross(nxt.tangent_at_start()) > 0
            try:
                fillet = ArcSeg(t1, t2, center, ccw, frozenset({"fillet"}))
            except ValueError:
                return None
            return _Fillet(
                _trim_arc_to(prev, t1, at_end=True),
                fillet,
                _trim_arc_to(nxt, t2, at_end=False),
            )
        r *= 0.6
    return None


#: Segments the organic bow may NEVER touch: flat print faces, welds, and
#: anything a cable/device/tie actually rests against.
_BOW_FORBIDDEN = frozenset(
    {
        "base", "base_bottom", "mount_face", "weld_joint", "neck_top",
        "intentional_corner", "contact", "cable_contact", "bay_contact",
        "mouth_upper", "mouth_lower", "mouth_corner", "throat", "slot_floor",
        "tunnel", "tunnel_roof", "tie_contact", "device_rest", "lip_inner",
        "socket_contact",
    }
)

_MIN_BOW_LENGTH = 8.0
_MAX_BOW_MM = 2.5


def bow_external_segments(loop: ProfileLoop, style: SurfaceStyle) -> ProfileLoop:
    """The organicity pass: long external straight segments become gentle
    OUTWARD arcs (adding material — walls never thin), with a seeded
    per-segment jitter for asymmetry. Runs before corner rounding, so every
    new joint gets a proper tangent fillet."""
    if style.bow_amplitude <= 1e-6:
        return loop
    import random

    rng = random.Random(style.bow_seed)
    out: list[Seg] = []
    for seg in loop.segments:
        jitter = 1.0 + style.bow_jitter * rng.uniform(-0.8, 0.8)
        if (
            not isinstance(seg, LineSeg)
            or "external" not in seg.tags
            or seg.tags & _BOW_FORBIDDEN
            or seg.length < _MIN_BOW_LENGTH
        ):
            out.append(seg)
            continue
        bulge = min(style.bow_amplitude * seg.length * jitter, _MAX_BOW_MM)
        if bulge < 0.15:
            out.append(seg)
            continue
        t = seg.tangent_at_start()
        # CCW loop: interior is left of travel, outward is right.
        outward = Pt(t.v, -t.u)
        mid = seg.point_at(0.5)
        target = mid + outward.scaled(bulge)
        half = seg.length / 2.0
        radius = (half * half + bulge * bulge) / (2.0 * bulge)
        center = target + outward.scaled(-radius)
        arc = ArcSeg(seg.a, seg.b, center, ccw=True, tags=seg.tags)
        if arc.point_at(0.5).dist(target) > 1e-3:
            arc = ArcSeg(seg.a, seg.b, center, ccw=False, tags=seg.tags)
        out.append(arc)
    return ProfileLoop(out)


def round_profile_corners(loop: ProfileLoop, style: SurfaceStyle) -> ProfileLoop:
    """Round every non-tangent, non-intentional joint; radius by joint tags.

    When the style carries a bow amplitude (biomorphic), long external
    straight segments bow outward FIRST, so their new joints are filleted
    tangent like everything else.

    Walks the joint list once; a successful fillet trims both neighbours and
    inserts the arc, then skips past it (both new joints are tangent by
    construction). A corner that cannot take a fillet is left sharp for the
    smoothness validator to report.
    """
    loop = bow_external_segments(loop, style)
    segments: list[Seg] = list(loop.segments)
    idx = 0
    while idx < len(segments):
        j = (idx + 1) % len(segments)
        prev, nxt = segments[idx], segments[j]
        joint_tags = prev.tags | nxt.tags
        if (
            joint_tags & INTENTIONAL_TAGS
            or joint_is_tangent(prev, nxt)
            or prev.length < 1e-6
            or nxt.length < 1e-6
        ):
            idx += 1
            continue
        r = style.corner_radius(joint_tags)
        if isinstance(prev, LineSeg) and isinstance(nxt, LineSeg):
            result = _fillet_line_line(prev, nxt, r)
        elif isinstance(prev, ArcSeg) and isinstance(nxt, ArcSeg):
            result = _fillet_arc_arc(prev, nxt, r)
        else:
            result = _fillet_line_arc(prev, nxt, r)
        if result is None:
            idx += 1
            continue
        segments[idx] = result.new_prev
        segments[j] = result.new_next
        # Insert after idx; for the wrap-around joint (j == 0) this appends
        # at the end, keeping ... new_prev, arc | new_next ... adjacency.
        segments.insert(idx + 1, result.arc)
        idx += 2
    return ProfileLoop(segments)
