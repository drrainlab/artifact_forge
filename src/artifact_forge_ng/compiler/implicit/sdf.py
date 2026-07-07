"""Vectorized world-frame SDF primitives (numpy only, no cadquery).

Every function takes ``P`` — an ``(N, 3)`` float64 array of world points —
and returns an ``(N,)`` array of signed distances (negative = inside
material). Exactness policy:

* :func:`sd_extruded_profile` measures the EXACT distance to the section's
  Line/Arc segment chain; the inside/outside sign comes from a
  crossing-number test against a polyline sample of the loop whose chord
  sagitta is bounded (default ``1e-6`` mm) — sign errors are confined to a
  band thinner than any voxel by three orders of magnitude.
* Cylinders/boxes/frusta/prisms are exact Euclidean SDFs.
* :func:`smin`/:func:`smax` are the polynomial smooth min/max — the
  "muscle transition" operators; ``k <= 0`` degrades to hard min/max.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

__all__ = [
    "Frame",
    "Profile2D",
    "sd_extruded_profile",
    "sd_capsule",
    "sd_sphere",
    "sd_box",
    "sd_cylinder_axis",
    "sd_frustum_z",
    "sd_rounded_rect_prism_z",
    "sd_prism_polygon",
    "sd_polygon_2d",
    "smin",
    "smax",
]

#: world (x, y, z) -> section (u, v, w); the exact inverse of
#: form.section.plane_mapping — one convention, one place, both directions.
_INVERSE_MAPPINGS = {
    ("YZ", "X"): (1, 2, 0),
    ("XZ", "Y"): (0, 2, 1),
    ("XY", "Z"): (0, 1, 2),
}


@dataclass(frozen=True)
class Frame:
    """A local orthonormal frame: ``origin`` + axes ``a``/``b`` spanning a
    panel plane and ``n`` pointing INTO the material (the ExoskeletonIR /
    FieldFeature convention)."""

    origin: tuple[float, float, float]
    a_axis: tuple[float, float, float]
    b_axis: tuple[float, float, float]
    n_axis: tuple[float, float, float]

    def to_local(self, P: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        d = P - np.asarray(self.origin, dtype=np.float64)
        a = d @ np.asarray(self.a_axis, dtype=np.float64)
        b = d @ np.asarray(self.b_axis, dtype=np.float64)
        n = d @ np.asarray(self.n_axis, dtype=np.float64)
        return a, b, n

    def to_world(self, a: float, b: float, n: float) -> tuple[float, float, float]:
        o = np.asarray(self.origin, dtype=np.float64)
        p = (
            o
            + a * np.asarray(self.a_axis, dtype=np.float64)
            + b * np.asarray(self.b_axis, dtype=np.float64)
            + n * np.asarray(self.n_axis, dtype=np.float64)
        )
        return (float(p[0]), float(p[1]), float(p[2]))


def planar_frame(
    origin: tuple[float, float, float] | None, tilt_deg: float, plane_z: float
) -> Frame:
    """The panel frame matching ``ExoskeletonIR.local_to_world`` /
    ``FieldFeature.local_to_world`` exactly: horizontal panels
    (``origin is None``) map ``(a, b, n) -> (a, b, plane_z - n)``; tilted
    planar panels rotate about +X by ``tilt_deg``."""
    if origin is None:
        return Frame((0.0, 0.0, plane_z), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0))
    t = math.radians(tilt_deg)
    return Frame(
        origin,
        (1.0, 0.0, 0.0),
        (0.0, math.cos(t), math.sin(t)),
        (0.0, -math.sin(t), math.cos(t)),
    )


# ---------------------------------------------------------------------------
# 2D profile machinery
# ---------------------------------------------------------------------------


class Profile2D:
    """Precomputed exact-distance + crossing-sign machinery for one closed
    ``ProfileLoop``. Pure function of the loop and the sagitta — safe to
    build once and reuse across grid chunks."""

    def __init__(self, loop, sagitta: float = 1e-6) -> None:
        from ...form.section import ArcSeg, LineSeg

        lines_a: list[tuple[float, float]] = []
        lines_b: list[tuple[float, float]] = []
        arcs: list[tuple[float, float, float, float, float, float, float, float, float]] = []
        poly: list[tuple[float, float]] = []
        for seg in loop.segments:
            if isinstance(seg, LineSeg):
                lines_a.append((seg.a.u, seg.a.v))
                lines_b.append((seg.b.u, seg.b.v))
                poly.append((seg.a.u, seg.a.v))
            elif isinstance(seg, ArcSeg):
                r = seg.radius
                # chord count from the sagitta bound: s = r (1 - cos(θ/2))
                theta = 2.0 * math.acos(max(-1.0, 1.0 - min(sagitta / max(r, 1e-9), 2.0)))
                count = max(2, int(math.ceil(abs(seg.sweep) / max(theta, 1e-9))))
                arcs.append(
                    (
                        seg.center.u, seg.center.v, r,
                        seg.start_angle, seg.sweep,
                        seg.a.u, seg.a.v, seg.b.u, seg.b.v,
                    )
                )
                for i in range(count):
                    p = seg.point_at(i / count)
                    poly.append((p.u, p.v))
            else:  # pragma: no cover — Seg union is exhaustive
                raise TypeError(f"unknown segment type {type(seg).__name__}")
        self._lines_a = np.asarray(lines_a, dtype=np.float64).reshape(-1, 2)
        self._lines_b = np.asarray(lines_b, dtype=np.float64).reshape(-1, 2)
        self._arcs = arcs
        self._poly = np.asarray(poly, dtype=np.float64).reshape(-1, 2)

    # -- exact unsigned distance to the segment chain -------------------------

    def distance(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        best = np.full(u.shape, np.inf, dtype=np.float64)
        for (ax, ay), (bx, by) in zip(self._lines_a, self._lines_b):
            best = np.minimum(best, _dist_segment(u, v, ax, ay, bx, by))
        for cu, cv, r, start, sweep, au, av, bu, bv in self._arcs:
            du, dv = u - cu, v - cv
            rho = np.hypot(du, dv)
            ang = np.arctan2(dv, du)
            if sweep >= 0:
                delta = np.mod(ang - start, 2.0 * math.pi)
                on_arc = delta <= sweep
            else:
                delta = np.mod(start - ang, 2.0 * math.pi)
                on_arc = delta <= -sweep
            d_circle = np.abs(rho - r)
            d_ends = np.minimum(np.hypot(u - au, v - av), np.hypot(u - bu, v - bv))
            best = np.minimum(best, np.where(on_arc, d_circle, d_ends))
        return best

    # -- crossing-number sign on the polyline sample ---------------------------

    def inside(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        poly = self._poly
        n_pts = u.shape[0]
        crossings = np.zeros(n_pts, dtype=np.int64)
        n_edges = poly.shape[0]
        # chunk the edges so the (points x edges) broadcast stays bounded
        chunk = max(1, int(4_000_000 // max(n_pts, 1)))
        uu = u[:, None]
        vv = v[:, None]
        starts = poly
        ends = np.roll(poly, -1, axis=0)
        for e0 in range(0, n_edges, chunk):
            i = starts[e0 : e0 + chunk]
            j = ends[e0 : e0 + chunk]
            vi, vj = i[:, 1][None, :], j[:, 1][None, :]
            ui, uj = i[:, 0][None, :], j[:, 0][None, :]
            cond = (vi > vv) != (vj > vv)
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (vv - vi) / (vj - vi)
                ucross = ui + t * (uj - ui)
            hit = cond & (uu < ucross)
            crossings += np.count_nonzero(hit, axis=1)
        return crossings % 2 == 1

    def signed(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        d = self.distance(u, v)
        return np.where(self.inside(u, v), -d, d)

    def signed_unique(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """``signed`` with a unique-(u, v) reduction — grid evaluations of an
        extruded profile repeat every (u, v) along the width axis; paying
        the crossing test once per unique pair keeps big grids cheap."""
        pts = np.stack([u, v], axis=1)
        uniq, inverse = np.unique(pts, axis=0, return_inverse=True)
        d = self.signed(uniq[:, 0], uniq[:, 1])
        return d[inverse.reshape(-1)]


def _dist_segment(
    u: np.ndarray, v: np.ndarray, ax: float, ay: float, bx: float, by: float
) -> np.ndarray:
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    if ll < 1e-18:
        return np.hypot(u - ax, v - ay)
    t = np.clip(((u - ax) * dx + (v - ay) * dy) / ll, 0.0, 1.0)
    return np.hypot(u - (ax + t * dx), v - (ay + t * dy))


def _combine_2d_slab(d2: np.ndarray, dw: np.ndarray) -> np.ndarray:
    """Exact 3D distance from a 2D signed distance + a slab signed distance
    (the standard box combination)."""
    outside = np.hypot(np.maximum(d2, 0.0), np.maximum(dw, 0.0))
    inside = np.minimum(np.maximum(d2, dw), 0.0)
    return outside + inside


def sd_extruded_profile(
    P: np.ndarray,
    profile: Profile2D,
    plane: str,
    width_axis: str,
    w0: float,
    w1: float,
) -> np.ndarray:
    """Signed distance to a constant-section extrusion of ``profile`` along
    its width axis over ``[w0, w1]`` (the ``plane_mapping`` convention)."""
    try:
        iu, iv, iw = _INVERSE_MAPPINGS[(plane, width_axis)]
    except KeyError:
        raise ValueError(
            f"unsupported plane/width_axis pair ({plane!r}, {width_axis!r})"
        ) from None
    u, v, w = P[:, iu], P[:, iv], P[:, iw]
    d2 = profile.signed_unique(u, v)
    dw = np.maximum(w0 - w, w - w1)
    return _combine_2d_slab(d2, dw)


# ---------------------------------------------------------------------------
# solid primitives
# ---------------------------------------------------------------------------


def sd_capsule(
    P: np.ndarray,
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    r: float,
) -> np.ndarray:
    a_ = np.asarray(a, dtype=np.float64)
    ba = np.asarray(b, dtype=np.float64) - a_
    ll = float(ba @ ba)
    pa = P - a_
    if ll < 1e-18:
        return np.linalg.norm(pa, axis=1) - r
    h = np.clip((pa @ ba) / ll, 0.0, 1.0)
    return np.linalg.norm(pa - h[:, None] * ba[None, :], axis=1) - r


def sd_sphere(P: np.ndarray, c: tuple[float, float, float], r: float) -> np.ndarray:
    return np.linalg.norm(P - np.asarray(c, dtype=np.float64), axis=1) - r


def sd_box(
    P: np.ndarray,
    lo: tuple[float, float, float],
    hi: tuple[float, float, float],
) -> np.ndarray:
    q = np.maximum(np.asarray(lo, dtype=np.float64) - P, P - np.asarray(hi, dtype=np.float64))
    outside = np.linalg.norm(np.maximum(q, 0.0), axis=1)
    inside = np.minimum(np.max(q, axis=1), 0.0)
    return outside + inside


_AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}


def sd_cylinder_axis(
    P: np.ndarray,
    axis: str,
    center: tuple[float, float, float],
    r: float,
    lo: float,
    hi: float,
) -> np.ndarray:
    """Finite axis-aligned cylinder: ``center`` is any point on the axis,
    ``lo``/``hi`` bound the axis coordinate."""
    idx = _AXIS_INDEX[axis]
    others = [i for i in range(3) if i != idx]
    c = np.asarray(center, dtype=np.float64)
    dr = np.hypot(P[:, others[0]] - c[others[0]], P[:, others[1]] - c[others[1]]) - r
    t = P[:, idx]
    da = np.maximum(lo - t, t - hi)
    return _combine_2d_slab(dr, da)


def sd_frustum_z(
    P: np.ndarray,
    cx: float,
    cy: float,
    z0: float,
    z1: float,
    r0: float,
    r1: float,
) -> np.ndarray:
    """A Z-axis cone frustum (countersinks): radius ``r0`` at ``z0``,
    ``r1`` at ``z1``. Exact — the axisymmetric solid's SDF equals the 2D
    distance in the (radius, z) half-plane to the three REAL boundary
    edges (bottom disk, lateral cone, top disk); the axis is interior."""
    q = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    z = P[:, 2]
    dist = np.minimum(
        _dist_segment(q, z, 0.0, z0, r0, z0),
        _dist_segment(q, z, r0, z0, r1, z1),
    )
    dist = np.minimum(dist, _dist_segment(q, z, r1, z1, 0.0, z1))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.clip((z - z0) / max(z1 - z0, 1e-12), 0.0, 1.0)
    r_at_z = r0 + (r1 - r0) * t
    inside = (z >= z0) & (z <= z1) & (q <= r_at_z)
    return np.where(inside, -dist, dist)


def sd_rounded_rect_prism_z(
    P: np.ndarray,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    corner_r: float,
    z0: float,
    z1: float,
) -> np.ndarray:
    """A rounded-rectangle prism along Z — the PlateFeature twin."""
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    hx, hy = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    r = max(0.0, min(corner_r, hx - 1e-9, hy - 1e-9))
    qx = np.abs(P[:, 0] - cx) - (hx - r)
    qy = np.abs(P[:, 1] - cy) - (hy - r)
    outside = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
    inside = np.minimum(np.maximum(qx, qy), 0.0)
    d2 = outside + inside - r
    dz = np.maximum(z0 - P[:, 2], P[:, 2] - z1)
    return _combine_2d_slab(d2, dz)


def sd_polygon_2d(
    px: np.ndarray, py: np.ndarray, poly: tuple[tuple[float, float], ...]
) -> np.ndarray:
    """Exact signed distance to a simple polygon (negative inside), sign by
    the even-odd crossing rule — winding direction does not matter."""
    n = len(poly)
    best = np.full(px.shape, np.inf, dtype=np.float64)
    crossings = np.zeros(px.shape, dtype=np.int64)
    for k in range(n):
        ax, ay = poly[k]
        bx, by = poly[(k + 1) % n]
        best = np.minimum(best, _dist_segment(px, py, ax, ay, bx, by))
        cond = (ay > py) != (by > py)
        if abs(by - ay) > 1e-18:
            t = (py - ay) / (by - ay)
            xc = ax + t * (bx - ax)
            crossings += (cond & (px < xc)).astype(np.int64)
    return np.where(crossings % 2 == 1, -best, best)


def sd_prism_polygon(
    P: np.ndarray,
    poly: tuple[tuple[float, float], ...],
    frame: Frame,
    n0: float,
    n1: float,
) -> np.ndarray:
    """A polygon in the frame's local (a, b) plane, extruded along the
    local n axis over ``[n0, n1]`` (n runs INTO the material)."""
    a, b, n = frame.to_local(P)
    d2 = sd_polygon_2d(a, b, poly)
    dn = np.maximum(n0 - n, n - n1)
    return _combine_2d_slab(d2, dn)


# ---------------------------------------------------------------------------
# smooth boolean operators
# ---------------------------------------------------------------------------


def smin(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    """Polynomial smooth minimum: the smooth-union operator. Bounded by
    ``min(a, b)`` from above (only ever ADDS material) and exactly equal to
    the hard min once ``|a - b| >= k``."""
    if k <= 0.0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def smax(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    """Polynomial smooth maximum — the window-lip subtraction operator:
    ``smax(d, -cutter, k)`` rounds the cut edges by ~k."""
    if k <= 0.0:
        return np.maximum(a, b)
    return -smin(-a, -b, k)
