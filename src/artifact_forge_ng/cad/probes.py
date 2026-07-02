"""Geometry probes — swept-cylinder and box intersection measurements the
topology validators build on. ``channel_probe`` is the ported v1
``verify._channel_probe``.
"""

from __future__ import annotations

import math

import cadquery as cq


def channel_probe(path: list[tuple[float, float, float]], d: float) -> cq.Workplane | None:
    """A 'cable' solid: cylinders of diameter ``d`` along the polyline —
    the volume that must (or must not) be clear."""
    r = max(0.3, d / 2.0)
    body: cq.Workplane | None = None
    z = cq.Vector(0, 0, 1)
    for a, b in zip(path, path[1:]):
        v = cq.Vector(b[0] - a[0], b[1] - a[1], b[2] - a[2])
        length = v.Length
        if length < 1e-6:
            continue
        seg = cq.Workplane("XY").circle(r).extrude(length).val()
        ang = math.degrees(z.getAngle(v))
        axis = z.cross(v)
        if axis.Length < 1e-9:  # parallel/antiparallel to Z
            axis = cq.Vector(1, 0, 0)
        seg = seg.located(cq.Location(cq.Vector(*a), axis, ang))
        w = cq.Workplane(obj=seg)
        body = w if body is None else body.union(w)
    return body


def probe_volume(probe: cq.Workplane | None) -> float:
    if probe is None:
        return 0.0
    try:
        return sum(s.Volume() for s in probe.solids().vals())
    except Exception:
        return 0.0


def intersect_volume(solid: cq.Workplane, probe: cq.Workplane | None) -> float:
    """Volume of ``solid`` inside ``probe`` — how much of the probed zone is
    still material."""
    if probe is None:
        return 0.0
    try:
        overlap = solid.intersect(probe)
        return sum(s.Volume() for s in overlap.solids().vals())
    except Exception:
        return 0.0


def solid_fraction(solid: cq.Workplane, probe: cq.Workplane | None) -> float:
    """0.0 = probed zone fully void, 1.0 = fully material."""
    pv = probe_volume(probe)
    if pv <= 1e-9:
        return 0.0
    return intersect_volume(solid, probe) / pv


def box_probe(
    x0: float, y0: float, z0: float, x1: float, y1: float, z1: float
) -> cq.Workplane:
    return (
        cq.Workplane("XY", origin=((x0 + x1) / 2, (y0 + y1) / 2, z0))
        .rect(abs(x1 - x0), abs(y1 - y0))
        .extrude(z1 - z0)
    )
