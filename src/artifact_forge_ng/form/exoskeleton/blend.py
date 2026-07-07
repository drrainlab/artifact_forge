"""Node blends and the implicit-surface handoff parameters.

Bio-2 only computes NUMBERS; Bio-3's CAD materialization consumes them
(metaballs / smooth node fillets where ribs meet)."""

from __future__ import annotations

from typing import Sequence

from .ir import RibGraph


def node_blend_radii(
    n_nodes: int,
    edges: Sequence[tuple[int, int]],
    edge_radius: Sequence[float],
    node_blend: float,
) -> tuple[float, ...]:
    """Per-node blend radius: grows with degree (a 4-way junction wants a
    bigger organic fillet than a passthrough), floored at 0.8× the fattest
    incident rib so the blend never undercuts its own ribs."""
    degree = [0] * n_nodes
    max_incident = [0.0] * n_nodes
    for (i, j), r in zip(edges, edge_radius):
        degree[i] += 1
        degree[j] += 1
        max_incident[i] = max(max_incident[i], r)
        max_incident[j] = max(max_incident[j], r)
    return tuple(
        max(node_blend * (0.6 + 0.2 * min(d, 4)), 0.8 * m)
        for d, m in zip(degree, max_incident)
    )


def metaball_params(graph: RibGraph) -> dict:
    """A plain-dict implicit description of the rib network — balls at the
    nodes (blend radii) and capsule struts along the edges. IR-only in
    Bio-2; the Bio-3 mesher evaluates it."""
    return {
        "schema": "metaball_params/v1",
        "balls": [
            {"at": list(node), "r": r}
            for node, r in zip(graph.nodes, graph.node_blend_radius)
        ],
        "struts": [
            {"a": i, "b": j, "r": r}
            for (i, j), r in zip(graph.edges, graph.edge_radius)
        ],
        "threshold": 1.0,
    }
