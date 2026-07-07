"""Bio-2 rib graph: determinism (tuple equality, not similarity), root
placement, mask avoidance and the root-to-tip taper."""

import math

from artifact_forge_ng.form.exoskeleton.graph import (
    graph_components,
    surface_rib_graph,
)
from artifact_forge_ng.form.exoskeleton.masks import point_clear
from artifact_forge_ng.form.exoskeleton.ribs import (
    load_path_guided_ribs,
    node_root_distances,
)
from artifact_forge_ng.form.exoskeleton.substrate import (
    SubstrateForm,
    jittered_grid_samples,
)
from artifact_forge_ng.form.regions import Circle2D, Rect2D, Region2D
from artifact_forge_ng.form.section import Pt
from artifact_forge_ng.product.archetype import RegionRole

WINDOW = Rect2D(-30.0, -20.0, 30.0, 20.0)
MASKS = (
    Region2D(
        "boss", RegionRole.FASTENER_KEEPOUT, Circle2D(Pt(0.0, 0.0), 6.0)
    ),
)
ANCHORS = ((-30.0, 0.0), (30.0, 0.0))
LOAD_SEEDS = ((10.0, 12.0),)


def make_substrate(seed: int = 11, pitch: float = 7.0) -> SubstrateForm:
    samples = jittered_grid_samples(WINDOW, MASKS, pitch=pitch, seed=seed)
    assert len(samples) >= 12  # room to grow
    return SubstrateForm(
        window=WINDOW, pitch=pitch, seed=seed, samples=samples,
        anchors=ANCHORS, load_seeds=LOAD_SEEDS,
    )


def test_same_seed_same_graph_tuple_equality():
    sub = make_substrate(seed=11)
    a = surface_rib_graph(sub, MASKS, rib_density=0.5, seed=11)
    b = surface_rib_graph(sub, MASKS, rib_density=0.5, seed=11)
    assert a == b  # frozen dataclasses: EQUAL, not statistically similar
    assert a.nodes == b.nodes and a.edges == b.edges
    assert a.root_nodes == b.root_nodes
    assert a.load_path_edges == b.load_path_edges


def test_different_seed_different_graph():
    a = surface_rib_graph(make_substrate(seed=11), MASKS, rib_density=0.5, seed=11)
    b = surface_rib_graph(make_substrate(seed=12), MASKS, rib_density=0.5, seed=12)
    assert a.nodes != b.nodes


def test_connected_and_roots_are_anchors():
    graph = surface_rib_graph(make_substrate(), MASKS, rib_density=0.5, seed=11)
    comps = graph_components(graph)
    assert len(comps) == 1  # repair produced one skeleton
    assert graph.root_nodes  # anchors became roots ...
    for r in graph.root_nodes:
        node = graph.nodes[r]
        assert (node[0], node[1]) in ANCHORS  # ... at EXACT anchor coords
    # load seed was force-included too
    seed_nodes = [(n[0], n[1]) for n in graph.nodes]
    assert LOAD_SEEDS[0] in seed_nodes


def test_load_path_routes_recorded_and_walk_the_graph():
    """The graph records the ACTUAL Dijkstra routes (one per load seed):
    seed node first, a root last, every hop an existing edge — the routed
    keepout check samples these, never the straight chord."""
    graph = surface_rib_graph(make_substrate(), MASKS, rib_density=0.5, seed=11)
    assert len(graph.load_path_routes) == len(LOAD_SEEDS)
    edge_set = set(graph.edges)
    for route in graph.load_path_routes:
        start = graph.nodes[route[0]]
        assert (start[0], start[1]) in LOAD_SEEDS
        assert route[-1] in graph.root_nodes
        for a, b in zip(route, route[1:]):
            assert (min(a, b), max(a, b)) in edge_set
    # the thickened spine is exactly the routes' edge set
    route_edges = {
        (min(a, b), max(a, b))
        for route in graph.load_path_routes
        for a, b in zip(route, route[1:])
    }
    assert route_edges == set(graph.load_path_edges)


def test_edges_avoid_masks():
    graph = surface_rib_graph(make_substrate(), MASKS, rib_density=0.6, seed=11)
    assert graph.edges
    for i, j in graph.edges:
        a, b = graph.nodes[i], graph.nodes[j]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(3, math.ceil(length / 2.0))  # every <= 2mm, like the builder
        for k in range(1, n):
            t = k / n
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            assert point_clear(p, MASKS), f"edge ({i},{j}) crosses the mask"


def test_edge_clear_catches_keepout_between_quarter_points():
    """Adversarial repro: a keepout tangent-dodging the fixed 1/4-1/2-3/4
    samples of a 40mm edge. Distance-based sampling (<=2mm) must reject
    the edge; the old fixed sampling let it through."""
    from artifact_forge_ng.form.exoskeleton.graph import _edge_clear

    trap = (
        Region2D(
            "trap", RegionRole.FASTENER_KEEPOUT,
            Circle2D(Pt(14.0, 4.0), 5.5),
        ),
    )
    a, b = (0.0, 0.0), (40.0, 0.0)
    # the trap deliberately clears all three OLD sample points ...
    for t in (0.25, 0.5, 0.75):
        p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        assert point_clear(p, trap)
    # ... yet the edge genuinely crosses it and must be rejected
    assert _edge_clear(a, b, trap) is False


def test_organicity_jitter_is_deterministic_and_consumed():
    """FIX 5: the jitter fraction (0.15 + 0.4*organicity) is a real input —
    same seed + same jitter reproduces the samples exactly; a different
    organicity moves them."""
    lo = jittered_grid_samples(WINDOW, MASKS, pitch=7.0, seed=11,
                               jitter=0.15 + 0.4 * 0.1)
    lo2 = jittered_grid_samples(WINDOW, MASKS, pitch=7.0, seed=11,
                                jitter=0.15 + 0.4 * 0.1)
    hi = jittered_grid_samples(WINDOW, MASKS, pitch=7.0, seed=11,
                               jitter=0.15 + 0.4 * 0.9)
    default = jittered_grid_samples(WINDOW, MASKS, pitch=7.0, seed=11)
    mid = jittered_grid_samples(WINDOW, MASKS, pitch=7.0, seed=11,
                                jitter=0.15 + 0.4 * 0.5)
    assert lo == lo2  # deterministic at fixed organicity
    assert lo != hi  # organicity actually moves the samples
    assert mid == default  # 0.5 keeps the historical 0.35 fraction


def test_taper_is_monotone_root_to_tip():
    raw = surface_rib_graph(make_substrate(), MASKS, rib_density=0.5, seed=11)
    graph = load_path_guided_ribs(
        raw, rib_d_root=6.0, rib_d_tip=3.0, node_blend=2.0
    )
    assert len(graph.edge_radius) == len(graph.edges)
    t = node_root_distances(graph)
    lp = set(graph.load_path_edges)
    for (i, j), r in zip(graph.edges, graph.edge_radius):
        t_mid = (t[i] + t[j]) / 2.0
        expected = (6.0 + (3.0 - 6.0) * t_mid) / 2.0
        if (i, j) in lp:
            expected = min(expected * 1.2, 3.0)
        assert math.isclose(r, expected, rel_tol=1e-9)
        assert r <= 3.0 + 1e-9  # never fatter than the root radius
    # a root-incident edge is at least as fat as the thinnest tip edge
    root_edges = [
        r for (i, j), r in zip(graph.edges, graph.edge_radius)
        if i in graph.root_nodes or j in graph.root_nodes
    ]
    assert root_edges and max(root_edges) >= max(graph.edge_radius) - 1e-9
    # blends: one per node, floored at 0.8x the fattest incident rib
    assert len(graph.node_blend_radius) == len(graph.nodes)
    incident = [0.0] * len(graph.nodes)
    for (i, j), r in zip(graph.edges, graph.edge_radius):
        incident[i] = max(incident[i], r)
        incident[j] = max(incident[j], r)
    for blend, inc in zip(graph.node_blend_radius, incident):
        assert blend >= 0.8 * inc - 1e-9
