"""Exoskeleton Form IR — the checkable skeleton intent (Bio-2, no CAD).

Everything the exoskeleton applicator computes lives here as FROZEN
dataclasses: determinism tests compare whole graphs by tuple equality, and
the mutation tests build broken variants with ``dataclasses.replace`` —
neither works on mutable ad-hoc dicts.

Local frame convention: node coordinates are ``(a, b, n)`` in the SAME
local frame FieldFeature.local_to_world uses (form/part.py) — ``a`` maps to
world X offset, ``b`` runs in-plane (rotated about +X by ``tilt_deg``),
``n`` is the offset ALONG the cut direction, into the material. A
horizontal panel (``origin is None``) degenerates to ``(a, b) == (x, y)``
with ``n`` measured down from ``plane_z``. This module documents the
convention; it never re-derives the mapping.

This module imports only stdlib + form/regions — no import cycle with
form/part.py (which imports :class:`ExoskeletonIR` for its optional field).
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

from ..regions import Rect2D, Region2D


@dataclass(frozen=True)
class ProfileSurfaceMap:
    """A developable surface: the section's OUTER contour swept along the
    extrusion width. Local coordinates are ``(s, x)`` — ``s`` is arc length
    along the contour (0 at the canvas seam), ``x`` the extrusion offset —
    plus ``n``, the depth INTO the material along the inward normal (the
    same sign convention as the planar frame: the proud side is negative n).

    The contour is pre-subdivided (arcs to a chord error < 0.05 mm) so a
    plain per-segment lerp of ``points``/``normals`` reproduces the true
    surface. Determinism is tuple equality — every field is an immutable
    tuple, so two identical clamps produce EQUAL maps."""

    #: Cumulative arc-length knots, ``s_breaks[0] == 0``, strictly increasing,
    #: ``s_breaks[-1] == total_s`` (the closing knot repeats ``points[0]``).
    s_breaks: tuple[float, ...]
    #: Contour points ``(u, v)`` in section coords at each knot.
    points: tuple[tuple[float, float], ...]
    #: Outward UNIT normal ``(nu, nv)`` at each knot.
    normals: tuple[tuple[float, float], ...]
    total_s: float
    #: Extrusion width (world +X span); ``x`` runs in ``[0, width]``.
    width: float

    def sample(self, s: float) -> tuple[float, float, float, float]:
        """``(u, v, nu, nv)`` at arc length ``s`` — clamped to the domain,
        linearly interpolated between the bracketing knots, normal
        renormalized."""
        total = self.total_s
        if s <= 0.0:
            u, v = self.points[0]
            nu, nv = self.normals[0]
            return (u, v, nu, nv)
        if s >= total:
            u, v = self.points[-1]
            nu, nv = self.normals[-1]
            return (u, v, nu, nv)
        k = bisect.bisect_right(self.s_breaks, s) - 1
        k = max(0, min(k, len(self.s_breaks) - 2))
        s0, s1 = self.s_breaks[k], self.s_breaks[k + 1]
        t = 0.0 if s1 - s0 < 1e-12 else (s - s0) / (s1 - s0)
        (u0, v0), (u1, v1) = self.points[k], self.points[k + 1]
        (a0, b0), (a1, b1) = self.normals[k], self.normals[k + 1]
        u = u0 + (u1 - u0) * t
        v = v0 + (v1 - v0) * t
        nu = a0 + (a1 - a0) * t
        nv = b0 + (b1 - b0) * t
        mag = math.hypot(nu, nv)
        if mag < 1e-9:
            nu, nv = a0, b0
        else:
            nu, nv = nu / mag, nv / mag
        return (u, v, nu, nv)

    def to_world(
        self, a: float, b: float, n: float = 0.0
    ) -> tuple[float, float, float]:
        """Map local ``(s=a, x=b, n)`` to world XYZ. The contour lies in the
        section's YZ plane (``u -> Y``, ``v -> Z``) and the extrusion runs
        along +X, so ``x`` IS world X. ``n`` runs into the material along
        ``-outward_normal`` — negative n is the proud (outward) side, exactly
        like the planar convention the topology probes assume."""
        u, v, nu, nv = self.sample(a)
        return (b, u - n * nu, v - n * nv)

    def to_local(self, world: tuple[float, float, float]) -> tuple[float, float]:
        """World ``(X, Y, Z)`` -> local ``(s, x)`` — ``x`` is world X, ``s``
        is the arc length of the nearest contour knot to ``(Y, Z)``. Coarse
        (nearest knot, not a full segment projection): it seeds the growth
        substrate, which the graph then refines."""
        y, z = world[1], world[2]
        best_s = 0.0
        best_d = math.inf
        for s, (pu, pv) in zip(self.s_breaks, self.points):
            d = (pu - y) ** 2 + (pv - z) ** 2
            if d < best_d:
                best_d, best_s = d, s
        return (best_s, world[0])


@dataclass(frozen=True)
class RibGraph:
    """The rib network on a panel, in local (a, b, n) coordinates.

    ``edges`` are index pairs with ``i < j``, lexicographically sorted;
    nodes are lexicographically sorted before indexing, so two runs with
    the same seed produce EQUAL graphs (tuple equality, not "similar").
    ``edge_radius``/``node_blend_radius`` are filled by the rib-taper pass
    (form/exoskeleton/ribs.py); the raw graph builder leaves them empty.
    """

    nodes: tuple[tuple[float, float, float], ...]
    edges: tuple[tuple[int, int], ...]
    edge_radius: tuple[float, ...] = ()
    node_blend_radius: tuple[float, ...] = ()
    #: Node indices where rib roots land (the anchors' nodes).
    root_nodes: tuple[int, ...] = ()
    #: Edges on the Dijkstra shortest path from each load seed to its
    #: nearest root — the +20%-thickened structural spine.
    load_path_edges: tuple[tuple[int, int], ...] = ()
    #: The ACTUAL routed paths, one node-index sequence per load seed
    #: (seed ... root). form.no_load_path_through_keepout samples THESE —
    #: the straight seed->root chord is not what the ribs walk.
    load_path_routes: tuple[tuple[int, ...], ...] = ()


@dataclass(frozen=True)
class LoadPathIR:
    """One DECLARED archetype load path, resolved onto the panel: the
    source region's center projected into the window. The form checks
    (``form.load_paths_connected`` / ``form.no_load_path_through_keepout``)
    verify the built graph honors exactly these."""

    from_region: str
    to_region: str
    priority: str  # "primary" | "secondary"
    #: Source point in local (a, b) — the load seed the graph grew from.
    seed: tuple[float, float]


@dataclass(frozen=True)
class ExoskeletonIR:
    """The complete Bio-2 exoskeleton intent attached to a PartForm.

    Bio-3 materializes it in CAD (rib sweeps, node blends, window cuts);
    until then the bio features stay honestly supported-but-not-built."""

    region: str
    window: Rect2D
    #: Local frame of the panel — identical semantics to FieldFeature.
    origin: tuple[float, float, float] | None
    tilt_deg: float
    depth: float
    graph: RibGraph
    #: Organic window polygons in local (a, b) — final vertices.
    windows: tuple[tuple[tuple[float, float], ...], ...]
    #: The semantic keepout mask everything above was filtered against.
    masks: tuple[Region2D, ...]
    #: Raw jittered-grid surface samples the graph was thinned from.
    samples: tuple[tuple[float, float], ...]
    #: Anchor points (rib-root landing sites) in local (a, b).
    anchors: tuple[tuple[float, float], ...]
    #: Load seed points (declared load paths or the heuristic fallback).
    load_seeds: tuple[tuple[float, float], ...]
    min_ligament: float
    #: Declared minimum rib diameter (the tip diameter after clamping).
    min_rib_d: float
    seed: int
    #: Resolved DECLARED load paths (empty = heuristic seeding was used;
    #: the load-path checks then pass vacuously).
    load_paths: tuple[LoadPathIR, ...] = field(default=())
    #: Top-face z of a HORIZONTAL panel (``origin is None``) — the plane
    #: the rib axes lie on. Oriented panels carry the plane in ``origin``/
    #: ``tilt_deg`` instead and leave this 0.
    plane_z: float = 0.0
    #: "planar" (the legacy horizontal/tilted frame) or "profile_surface"
    #: (the developable section-sweep of Bio-4M stage B). The default keeps
    #: every existing exoskeleton byte-identical.
    mapping: str = "planar"
    #: The developable surface when ``mapping == "profile_surface"``; the
    #: graph nodes' ``(a, b)`` are then ``(s, x)`` on it.
    surface: ProfileSurfaceMap | None = None

    def local_to_world(
        self, a: float, b: float, n: float = 0.0
    ) -> tuple[float, float, float]:
        """Map local (a, b, n) to world XYZ — the exact planar convention
        of ``FieldFeature.local_to_world`` (n runs INTO the material, so
        the proud side of the panel is negative n). The Bio-3 compiler and
        the topology probes both read the frame through this one method."""
        import math

        if self.mapping == "profile_surface" and self.surface is not None:
            return self.surface.to_world(a, b, n)
        if self.origin is None:
            return (a, b, self.plane_z - n)
        t = math.radians(self.tilt_deg)
        ox, oy, oz = self.origin
        return (
            ox + a,
            oy + b * math.cos(t) - n * math.sin(t),
            oz + b * math.sin(t) + n * math.cos(t),
        )
