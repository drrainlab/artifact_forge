"""Rib taper — root-to-tip radius assignment along the graph.

Every node gets a normalized root-distance ``t`` (multi-source Dijkstra
from the root nodes); an edge's radius is the root/tip lerp at its
midpoint ``t``, and edges on a load path are thickened by 20% (capped at
the root radius — a load path never grows FATTER than a root)."""

from __future__ import annotations

import heapq
import math
from dataclasses import replace

from .blend import node_blend_radii
from .ir import RibGraph


def node_root_distances(graph: RibGraph) -> tuple[float, ...]:
    """Normalized distance from the nearest root, per node: 0.0 at the
    roots, 1.0 at the farthest reachable node. Unreachable nodes read 1.0
    (they are tips as far as tapering cares; connectivity checks complain
    about them separately)."""
    n = len(graph.nodes)
    dist = [math.inf] * n
    heap: list[tuple[float, int]] = []
    for r in graph.root_nodes:
        dist[r] = 0.0
        heapq.heappush(heap, (0.0, r))
    adjacency: dict[int, list[tuple[int, float]]] = {}
    for i, j in graph.edges:
        w = math.hypot(
            graph.nodes[i][0] - graph.nodes[j][0],
            graph.nodes[i][1] - graph.nodes[j][1],
        )
        adjacency.setdefault(i, []).append((j, w))
        adjacency.setdefault(j, []).append((i, w))
    seen: set[int] = set()
    while heap:
        d, node = heapq.heappop(heap)
        if node in seen:
            continue
        seen.add(node)
        for nxt, w in adjacency.get(node, ()):
            nd = d + w
            if nd < dist[nxt] - 1e-12:
                dist[nxt] = nd
                heapq.heappush(heap, (nd, nxt))
    reachable = [d for d in dist if math.isfinite(d)]
    d_max = max(reachable, default=0.0)
    if d_max <= 1e-9:
        return tuple(0.0 if math.isfinite(d) else 1.0 for d in dist)
    return tuple(min(d / d_max, 1.0) if math.isfinite(d) else 1.0 for d in dist)


def load_path_guided_ribs(
    graph: RibGraph,
    *,
    rib_d_root: float,
    rib_d_tip: float,
    node_blend: float,
) -> RibGraph:
    """Fill ``edge_radius`` and ``node_blend_radius`` on a raw graph.

    ``rib_d_tip`` must already be clamped ≤ ``rib_d_root`` by the caller
    (the applicator notes the clamp); the taper is then monotone in the
    root distance by construction."""
    t = node_root_distances(graph)
    lp = set(graph.load_path_edges)
    radii: list[float] = []
    for i, j in graph.edges:
        t_mid = (t[i] + t[j]) / 2.0
        r = (rib_d_root + (rib_d_tip - rib_d_root) * t_mid) / 2.0
        if (i, j) in lp:
            r = min(r * 1.2, rib_d_root / 2.0)
        radii.append(r)
    blend = node_blend_radii(
        len(graph.nodes), graph.edges, tuple(radii), node_blend
    )
    return replace(
        graph, edge_radius=tuple(radii), node_blend_radius=blend
    )
