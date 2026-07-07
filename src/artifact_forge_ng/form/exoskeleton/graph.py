"""The rib graph builder — Gabriel graph over thinned surface samples,
mask-pruned, connectivity-repaired, with Dijkstra load paths.

Determinism is a hard contract: sites are thinned after a SEEDED shuffle,
anchors and load seeds are force-included, and the final node list is
lexicographically sorted before indexing — the same inputs yield an EQUAL
RibGraph (tuple equality), not a statistically similar one.
"""

from __future__ import annotations

import heapq
import math
import random
from typing import Sequence

from ..regions import Region2D
from .ir import RibGraph
from .masks import point_clear
from .substrate import SubstrateForm


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


#: Max spacing between interior samples when testing an edge against the
#: masks (mm). Fixed 1/4-1/2-3/4 sampling missed keepouts hiding between
#: the quarter points of long edges.
EDGE_SAMPLE_STEP = 2.0


def _edge_clear(
    a: tuple[float, float],
    b: tuple[float, float],
    masks: Sequence[Region2D],
) -> bool:
    """An edge survives when interior samples spaced at most
    ``EDGE_SAMPLE_STEP`` apart all clear every mask (the endpoints were
    mask-filtered when they became sites). Repair bridges run through the
    same function, so they obey the same rule."""
    n = max(3, math.ceil(_dist(a, b) / EDGE_SAMPLE_STEP))
    for k in range(1, n):
        t = k / n
        p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        if not point_clear(p, masks):
            return False
    return True


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.parent[max(ri, rj)] = min(ri, rj)


def _thin_sites(
    substrate: SubstrateForm, n_sites: int, seed: int
) -> list[tuple[float, float]]:
    """Greedy min-spacing selection after a seeded shuffle — an even,
    organic-looking spread without Lloyd iterations."""
    points = list(substrate.samples)
    random.Random(seed).shuffle(points)
    area = max(substrate.window.width * substrate.window.height, 1e-9)
    min_spacing = 0.75 * math.sqrt(area / max(n_sites, 1))
    selected: list[tuple[float, float]] = []
    for p in points:
        if len(selected) >= n_sites:
            break
        if all(_dist(p, q) >= min_spacing for q in selected):
            selected.append(p)
    return selected


def _force_include(
    sites: list[tuple[float, float]],
    forced: Sequence[tuple[float, float]],
    pitch: float,
) -> list[tuple[float, float]]:
    """Every anchor/load seed becomes a node: snap the nearest free site
    within one pitch onto it, else insert it as a new site."""
    out = list(sites)
    forced_unique = list(dict.fromkeys(forced))
    forced_set: set[tuple[float, float]] = set()
    for f in forced_unique:
        best_i: int | None = None
        best_d = pitch
        for i, s in enumerate(out):
            if s in forced_set:
                continue
            d = _dist(f, s)
            if d <= best_d:
                best_d, best_i = d, i
        if best_i is not None:
            out[best_i] = f
        else:
            out.append(f)
        forced_set.add(f)
    return list(dict.fromkeys(out))


def _gabriel_edges(
    pts: Sequence[tuple[float, float]]
) -> list[tuple[int, int]]:
    """Gabriel graph: (i, j) is an edge iff no third site lies strictly
    inside the circle whose diameter is the segment ij."""
    n = len(pts)
    edges: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            mx = (pts[i][0] + pts[j][0]) / 2.0
            my = (pts[i][1] + pts[j][1]) / 2.0
            r2 = ((pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2) / 4.0
            ok = True
            for k in range(n):
                if k == i or k == j:
                    continue
                d2 = (pts[k][0] - mx) ** 2 + (pts[k][1] - my) ** 2
                if d2 < r2 - 1e-9:
                    ok = False
                    break
            if ok:
                edges.append((i, j))
    return edges


def _repair_connectivity(
    pts: Sequence[tuple[float, float]],
    edges: list[tuple[int, int]],
    masks: Sequence[Region2D],
) -> list[tuple[int, int]]:
    """Union-find repair: while the graph is split, add the SHORTEST
    mask-clear edge bridging two components. When no clear bridge exists
    the graph honestly stays disconnected — the form checks fail, nothing
    pretends."""
    n = len(pts)
    uf = _UnionFind(n)
    for i, j in edges:
        uf.union(i, j)
    existing = set(edges)
    while True:
        roots = {uf.find(i) for i in range(n)}
        if len(roots) <= 1:
            break
        best: tuple[float, int, int] | None = None
        for i in range(n):
            for j in range(i + 1, n):
                if uf.find(i) == uf.find(j) or (i, j) in existing:
                    continue
                d = _dist(pts[i], pts[j])
                if (best is None or d < best[0]) and _edge_clear(
                    pts[i], pts[j], masks
                ):
                    best = (d, i, j)
        if best is None:
            break
        _, i, j = best
        edges.append((i, j))
        existing.add((i, j))
        uf.union(i, j)
    return edges


def _dijkstra_route(
    adjacency: dict[int, list[tuple[int, float]]],
    start: int,
    roots: set[int],
) -> tuple[int, ...]:
    """The node sequence of the shortest path from ``start`` to its
    NEAREST root (heapq Dijkstra). A start that IS a root routes trivially
    to itself; an unreachable start yields an empty route — the
    connectivity checks own that failure."""
    if start in roots:
        return (start,)
    dist = {start: 0.0}
    prev: dict[int, int] = {}
    heap: list[tuple[float, int]] = [(0.0, start)]
    goal: int | None = None
    seen: set[int] = set()
    while heap:
        d, node = heapq.heappop(heap)
        if node in seen:
            continue
        seen.add(node)
        if node in roots:
            goal = node
            break
        for nxt, w in adjacency.get(node, ()):
            nd = d + w
            if nd < dist.get(nxt, math.inf) - 1e-12:
                dist[nxt] = nd
                prev[nxt] = node
                heapq.heappush(heap, (nd, nxt))
    if goal is None:
        return ()
    route = [goal]
    node = goal
    while node != start:
        node = prev[node]
        route.append(node)
    route.reverse()
    return tuple(route)


def _route_edges(route: tuple[int, ...]) -> list[tuple[int, int]]:
    return [
        (min(a, b), max(a, b)) for a, b in zip(route, route[1:])
    ]


def surface_rib_graph(
    substrate: SubstrateForm,
    masks: Sequence[Region2D],
    *,
    rib_density: float,
    seed: int,
) -> RibGraph:
    """Build the deterministic rib graph over the substrate. Radii are
    left empty — form/exoskeleton/ribs.py tapers them in a second pass."""
    n_sites = round(6 + rib_density * 30)
    sites = _thin_sites(substrate, n_sites, seed)
    forced = list(substrate.anchors) + list(substrate.load_seeds)
    sites = _force_include(sites, forced, substrate.pitch)
    pts = sorted(dict.fromkeys(sites))  # lexicographic order IS the index
    index = {p: i for i, p in enumerate(pts)}

    edges = _gabriel_edges(pts)
    edges = [e for e in edges if _edge_clear(pts[e[0]], pts[e[1]], masks)]
    edges = _repair_connectivity(pts, edges, masks)
    edges = sorted(edges)

    root_nodes = tuple(sorted(
        index[a] for a in dict.fromkeys(substrate.anchors) if a in index
    ))
    load_nodes = sorted(
        index[s] for s in dict.fromkeys(substrate.load_seeds) if s in index
    )

    adjacency: dict[int, list[tuple[int, float]]] = {}
    for i, j in edges:
        w = _dist(pts[i], pts[j])
        adjacency.setdefault(i, []).append((j, w))
        adjacency.setdefault(j, []).append((i, w))
    roots = set(root_nodes)
    lp_edges: set[tuple[int, int]] = set()
    routes: list[tuple[int, ...]] = []
    for start in load_nodes:
        route = _dijkstra_route(adjacency, start, roots)
        if route:
            routes.append(route)
        lp_edges.update(_route_edges(route))

    return RibGraph(
        nodes=tuple((p[0], p[1], 0.0) for p in pts),
        edges=tuple(edges),
        edge_radius=(),
        node_blend_radius=(),
        root_nodes=root_nodes,
        load_path_edges=tuple(sorted(lp_edges)),
        load_path_routes=tuple(routes),
    )


def graph_components(graph: RibGraph) -> list[set[int]]:
    """Connected components over the graph's edges — shared by the form
    checks (rib_graph_connected / no_rib_islands / load_paths_connected)."""
    n = len(graph.nodes)
    uf = _UnionFind(n)
    for i, j in graph.edges:
        uf.union(i, j)
    comps: dict[int, set[int]] = {}
    for i in range(n):
        comps.setdefault(uf.find(i), set()).add(i)
    return list(comps.values())
