"""Bio-3 exoskeleton materialization — the rib graph becomes real solids.

Each graph edge becomes a solid cylinder along the WORLD-space segment
between its node positions (radius = the tapered ``edge_radius``); each
node gets a full sphere of its ``node_blend_radius`` (the metaball
brep-approximation: spheres as node blends — smooth capsule junctions
without a single 3D fillet). The capsule AXES lie exactly ON the panel
surface plane, so half of every tube sinks into the substrate: the weld
overlap is guaranteed by construction (>= r >= 0.8mm, comfortably past the
0.6mm weld rule), half stands proud for the probes to find.

Frames: the same planar convention the applicator accepts — horizontal
panels and tilted planar FaceWindows, both through
``ExoskeletonIR.local_to_world``. Anything else is unreachable here
(the applicator already refuses cylindrical panels honestly).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq

from ..form.part import PartForm

#: Never build a tube thinner than this — sub-perimeter tubes are OCC
#: fragility bait and unprintable anyway (the IR checks fail long before).
MIN_SOLID_R = 0.4

#: Max chord of a subdivided capsule segment in local (s, x) (mm). At most
#: this keeps the polyline hugging the developable surface (chord sag
#: ~ L^2/8R) AND lands the midpoint probe ON the polyline (KEY LAW 4).
MAX_CAPSULE_STEP = 6.0


@dataclass(frozen=True)
class CapsuleChain:
    """One rib edge as a WORLD-space polyline (capsule axis) + radius. On a
    planar panel the polyline is a single chord; on a profile_surface it is
    subdivided to hug the curve."""

    polyline: tuple[tuple[float, float, float], ...]
    radius: float


@dataclass(frozen=True)
class NodeBlend:
    """A metaball node blend — a world-space sphere where ribs meet."""

    center: tuple[float, float, float]
    radius: float


@dataclass(frozen=True)
class WindowCarve:
    """An organic window as a world-space polygon on the surface + the
    inward recess vector. Shared with the SDF stage (stage A); the BRep
    recess cutter reads the same intent from the FieldFeature."""

    polygon: tuple[tuple[float, float, float], ...]
    depth: float
    inward: tuple[float, float, float]


def _subdivided_axis(ir, na, nb, sink: float = 0.0) -> list[tuple[float, float, float]]:
    """World polyline of a rib edge. The local (s, x) chord is split into
    <= MAX_CAPSULE_STEP pieces, forced to an EVEN count so t = 0.5 (the
    edge midpoint the topology probe samples) is always a polyline knot; each
    knot is mapped to the surface at n = 0 (the axis lies ON the panel)."""
    sa, xa = na[0], na[1]
    sb, xb = nb[0], nb[1]
    length = math.hypot(sb - sa, xb - xa)
    n = max(1, math.ceil(length / MAX_CAPSULE_STEP))
    if n % 2 == 1:
        n += 1
    out: list[tuple[float, float, float]] = []
    for k in range(n + 1):
        t = k / n
        out.append(ir.local_to_world(
            sa + (sb - sa) * t, xa + (xb - xa) * t, sink))
    return out


def exoskeleton_capsule_chains(
    form: PartForm,
) -> tuple[list[CapsuleChain], list[NodeBlend]]:
    """The ONE geometry source both the BRep twin and the SDF skin read: the
    rib graph as world-space capsule polylines + node-blend spheres. Planar
    edges collapse to a single chord (byte-identical to the legacy path);
    profile_surface edges hug the developable surface."""
    ir = form.exoskeleton
    if ir is None or not ir.graph.edges:
        return ([], [])
    graph = ir.graph
    radii = graph.edge_radius or tuple(ir.min_rib_d / 2.0 for _ in graph.edges)
    on_surface = ir.mapping == "profile_surface"
    chains: list[CapsuleChain] = []
    for (i, j), r in zip(graph.edges, radii):
        na, nb = graph.nodes[i], graph.nodes[j]
        if on_surface:
            # Sink the axis 0.25*r below the surface: the tube stays 0.75*r
            # proud (probes sample at 0.5*r) while OCC gets a fat, reliable
            # interpenetration to fuse — 300 tangent tubes on a curved body
            # is exactly the boolean-fragility case the original spec called
            # out; tangent contact left unfused islands.
            poly = _subdivided_axis(ir, na, nb, sink=0.25 * max(r, MIN_SOLID_R))
        else:
            poly = [
                ir.local_to_world(na[0], na[1], na[2]),
                ir.local_to_world(nb[0], nb[1], nb[2]),
            ]
        chains.append(
            CapsuleChain(polyline=tuple(poly), radius=max(r, MIN_SOLID_R))
        )
    blends = graph.node_blend_radius
    nodes: list[NodeBlend] = []
    for idx, node in enumerate(graph.nodes):
        r = blends[idx] if idx < len(blends) else ir.min_rib_d / 2.0
        if r < MIN_SOLID_R:
            continue
        nodes.append(NodeBlend(
            center=ir.local_to_world(node[0], node[1], node[2]), radius=r
        ))
    return chains, nodes


def _sphere(center: tuple[float, float, float], r: float) -> cq.Solid:
    return cq.Solid.makeSphere(
        r, cq.Vector(*center),
        angleDegrees1=-90.0, angleDegrees2=90.0, angleDegrees3=360.0,
    )


def build_exoskeleton_solid(form: PartForm) -> list[cq.Solid] | None:
    """The rib network as a list of solids to weld (cylinders per edge,
    spheres per node), in world coordinates. Returns None when the form
    carries no exoskeleton or the graph has no edges — the caller logs it
    and the topology probes fail honestly."""
    ir = form.exoskeleton
    if ir is None:
        return None
    graph = ir.graph
    if not graph.edges:
        return None
    if ir.mapping == "profile_surface":
        return _build_profile_surface_solids(form)

    radii = graph.edge_radius or tuple(
        ir.min_rib_d / 2.0 for _ in graph.edges
    )
    solids: list[cq.Solid] = []
    for (i, j), r in zip(graph.edges, radii):
        na, nb = graph.nodes[i], graph.nodes[j]
        a3 = ir.local_to_world(na[0], na[1], na[2])
        b3 = ir.local_to_world(nb[0], nb[1], nb[2])
        axis = cq.Vector(b3[0] - a3[0], b3[1] - a3[1], b3[2] - a3[2])
        if axis.Length < 1e-6:
            continue
        solids.append(
            cq.Solid.makeCylinder(
                max(r, MIN_SOLID_R), axis.Length, cq.Vector(*a3), axis
            )
        )
    blends = graph.node_blend_radius
    for idx, node in enumerate(graph.nodes):
        r = blends[idx] if idx < len(blends) else ir.min_rib_d / 2.0
        if r < MIN_SOLID_R:
            continue
        center = ir.local_to_world(node[0], node[1], node[2])
        solids.append(_sphere(center, r))
    return solids or None


def _build_profile_surface_solids(form: PartForm) -> list[cq.Solid] | None:
    """Polyline capsules on a developable surface: a short cylinder per
    subdivided chord, a bridge sphere at every interior knot (so the polyline
    is continuous through its bends), plus node-blend spheres. The bridge
    sphere at the edge midpoint is exactly what the topology midpoint probe
    lands on (KEY LAW 4)."""
    chains, blends = exoskeleton_capsule_chains(form)
    solids: list[cq.Solid] = []
    for ch in chains:
        r = max(ch.radius, MIN_SOLID_R)
        pts = ch.polyline
        for a3, b3 in zip(pts, pts[1:]):
            axis = cq.Vector(b3[0] - a3[0], b3[1] - a3[1], b3[2] - a3[2])
            if axis.Length < 1e-6:
                continue
            solids.append(
                cq.Solid.makeCylinder(r, axis.Length, cq.Vector(*a3), axis)
            )
        for p in pts[1:-1]:
            solids.append(_sphere(p, r))
    for nb in blends:
        solids.append(_sphere(nb.center, max(nb.radius, MIN_SOLID_R)))
    return solids or None
