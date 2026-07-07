"""Mutation tests for the Bio-2 exoskeleton form checks: a healthy IR
passes everything; each surgically broken variant (dataclasses.replace on
the frozen IR) fails EXACTLY the check that owns the defect; a form with
no exoskeleton passes all of them vacuously."""

from dataclasses import replace

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_exoskeleton import (
    check_load_paths_connected,
    check_min_rib_diameter_ok,
    check_no_load_path_through_keepout,
    check_no_rib_islands,
    check_primary_load_path_has_ribs,
    check_rib_graph_connected,
    check_rib_roots_touch_substrate,
    check_windows_inside_safe_regions,
)
from artifact_forge_ng.form.exoskeleton.ir import (
    ExoskeletonIR,
    LoadPathIR,
    RibGraph,
)
from artifact_forge_ng.form.part import FieldFeature, PartForm
from artifact_forge_ng.form.regions import Circle2D, Rect2D, Region2D
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.archetype import RegionRole

ALL_CHECKS = (
    check_rib_graph_connected,
    check_no_rib_islands,
    check_rib_roots_touch_substrate,
    check_min_rib_diameter_ok,
    check_windows_inside_safe_regions,
    check_load_paths_connected,
    check_no_load_path_through_keepout,
    check_primary_load_path_has_ribs,
)

WINDOW = Rect2D(-25.0, -20.0, 25.0, 20.0)
MASK = Region2D(
    "boss", RegionRole.FASTENER_KEEPOUT, Circle2D(Pt(10.0, -10.0), 3.0)
)

#: nodes sorted lexicographically: 0=(-20,0) 1=(0,0) 2=(0,15) 3=(20,0)
GOOD_GRAPH = RibGraph(
    nodes=((-20.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 15.0, 0.0),
           (20.0, 0.0, 0.0)),
    edges=((0, 1), (1, 2), (1, 3)),
    edge_radius=(3.0, 2.0, 2.0),
    node_blend_radius=(2.4, 2.4, 1.6, 1.6),
    root_nodes=(0,),
    # Both hops of the recorded route are load-path edges.
    load_path_edges=((0, 1), (1, 3)),
    # The ACTUAL routed path from the load seed node 3 to root 0.
    load_path_routes=((3, 1, 0),),
)


def good_ir(**overrides) -> ExoskeletonIR:
    ir = ExoskeletonIR(
        region="panel",
        window=WINDOW,
        origin=None,
        tilt_deg=0.0,
        depth=5.0,
        graph=GOOD_GRAPH,
        windows=(),
        masks=(MASK,),
        samples=(),
        anchors=((-20.0, 0.0),),
        load_seeds=((20.0, 0.0),),
        min_ligament=2.0,
        min_rib_d=3.0,
        seed=7,
        load_paths=(
            LoadPathIR(from_region="stress_zone", to_region="mount",
                       priority="primary", seed=(20.0, 0.0)),
        ),
    )
    return replace(ir, **overrides) if overrides else ir


def make_form(ir=None, fields=()) -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    return PartForm(
        name="t", params={}, frame={},
        section=SectionProfile(name="t", outer=loop),
        width=5.0, style=MOLDED_UTILITY_PART,
        fields=list(fields), exoskeleton=ir,
    )


def test_healthy_ir_passes_everything():
    form = make_form(good_ir())
    for check in ALL_CHECKS:
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_no_exoskeleton_all_pass_vacuously():
    form = make_form(None)
    for check in ALL_CHECKS:
        finding = check(form)
        assert finding.status is Status.PASS
        assert "no exoskeleton" in finding.message or "no organic" in finding.message


def test_island_node_fails_no_rib_islands():
    graph = replace(
        GOOD_GRAPH,
        nodes=GOOD_GRAPH.nodes + ((24.0, 18.0, 0.0),),
        node_blend_radius=GOOD_GRAPH.node_blend_radius + (1.0,),
    )
    form = make_form(good_ir(graph=graph))
    assert check_no_rib_islands(form).status is Status.FAIL
    # connectivity-of-roots is still fine: the island carries no root
    assert check_rib_graph_connected(form).status is Status.PASS


def test_roots_split_across_components_fails_connected():
    graph = replace(
        GOOD_GRAPH, edges=((0, 1), (2, 3)), edge_radius=(3.0, 2.0),
        root_nodes=(0, 3), load_path_edges=(),
    )
    form = make_form(good_ir(graph=graph))
    assert check_rib_graph_connected(form).status is Status.FAIL


def test_rootless_component_fails_islands():
    graph = replace(
        GOOD_GRAPH, edges=((0, 1), (2, 3)), edge_radius=(3.0, 2.0),
        root_nodes=(0,), load_path_edges=(),
    )
    form = make_form(good_ir(graph=graph))
    assert check_no_rib_islands(form).status is Status.FAIL


def test_root_off_anchors_fails_roots_touch():
    form = make_form(good_ir(anchors=((5.0, 5.0),)))
    finding = check_rib_roots_touch_substrate(form)
    assert finding.status is Status.FAIL


def test_thin_edge_fails_min_diameter():
    graph = replace(GOOD_GRAPH, edge_radius=(3.0, 2.0, 0.5))
    form = make_form(good_ir(graph=graph))
    finding = check_min_rib_diameter_ok(form)
    assert finding.status is Status.FAIL
    assert finding.measured == 1.0


def test_window_in_keepout_fails_safe_regions():
    bad_poly = ((8.0, -12.0), (12.0, -12.0), (12.0, -8.0), (8.0, -8.0))
    field = FieldFeature(
        plane_z=5.0, centers=(), cell=0.0, depth=5.0, pattern="organic",
        window=WINDOW, keepouts=(MASK,), polygons=(bad_poly,),
        min_ligament=2.0,
    )
    form = make_form(good_ir(), fields=[field])
    assert check_windows_inside_safe_regions(form).status is Status.FAIL


def test_window_straddling_a_rib_fails_safe_regions():
    """The measured windows/ribs invariant: a polygon sitting ON a rib
    centerline (edge (0,1), radius 3.0) violates the radius+ligament/2
    clearance even though it is inside the window and clear of keepouts."""
    on_rib = ((-12.0, -1.0), (-8.0, -1.0), (-8.0, 1.0), (-12.0, 1.0))
    field = FieldFeature(
        plane_z=5.0, centers=(), cell=0.0, depth=5.0, pattern="organic",
        window=WINDOW, keepouts=(), polygons=(on_rib,),
        min_ligament=2.0,
    )
    form = make_form(good_ir(), fields=[field])
    finding = check_windows_inside_safe_regions(form)
    assert finding.status is Status.FAIL
    assert "rib" in finding.message


def test_window_outside_field_window_fails_safe_regions():
    stray_poly = ((30.0, 0.0), (35.0, 0.0), (35.0, 5.0), (30.0, 5.0))
    field = FieldFeature(
        plane_z=5.0, centers=(), cell=0.0, depth=5.0, pattern="organic",
        window=WINDOW, keepouts=(), polygons=(stray_poly,),
        min_ligament=2.0,
    )
    form = make_form(good_ir(), fields=[field])
    assert check_windows_inside_safe_regions(form).status is Status.FAIL


def test_load_path_without_route_fails_connected():
    # Only the left pair is wired; the declared seed sits on node 3 whose
    # component never reaches the root.
    graph = replace(
        GOOD_GRAPH, edges=((0, 1),), edge_radius=(3.0,),
        load_path_edges=(), load_path_routes=(),
    )
    form = make_form(good_ir(graph=graph))
    assert check_load_paths_connected(form).status is Status.FAIL


def test_load_path_through_keepout_fails():
    # The ROUTED path 3 -> 1 -> 0 passes exactly through node 1 = (0,0);
    # a mask sitting there must fail the check.
    blocking = Region2D(
        "column", RegionRole.INTERFACE_KEEPOUT,
        Circle2D(Pt(0.0, 0.0), 3.0),
    )
    form = make_form(good_ir(masks=(blocking,)))
    assert check_no_load_path_through_keepout(form).status is Status.FAIL
    # ... and with the mask far away the same route is clean
    assert check_no_load_path_through_keepout(
        make_form(good_ir())
    ).status is Status.PASS


def test_detouring_route_clears_keepout_the_straight_chord_hits():
    """The check follows the GRAPH route, not the straight seed->root
    chord: a route detouring over node 2 = (0,15) clears a keepout that
    sits exactly on the chord (the pre-fix chord logic would false-FAIL
    this valid design)."""
    blocking = Region2D(
        "column", RegionRole.INTERFACE_KEEPOUT,
        Circle2D(Pt(0.0, 0.0), 3.0),
    )
    graph = replace(
        GOOD_GRAPH,
        edges=((0, 2), (2, 3)),
        edge_radius=(2.5, 2.5),
        load_path_edges=((0, 2), (2, 3)),
        load_path_routes=((3, 2, 0),),
    )
    form = make_form(good_ir(graph=graph, masks=(blocking,)))
    assert check_no_load_path_through_keepout(form).status is Status.PASS


def test_unrouted_paths_pass_vacuously_connectivity_owns_it():
    """Declared load paths but no recorded routes (unreachable seed): the
    keepout check passes vacuously — load_paths_connected owns that
    failure, one defect one check."""
    graph = replace(
        GOOD_GRAPH, edges=((0, 1),), edge_radius=(3.0,),
        load_path_edges=(), load_path_routes=(),
    )
    form = make_form(good_ir(graph=graph))
    finding = check_no_load_path_through_keepout(form)
    assert finding.status is Status.PASS
    assert "no routed load paths" in finding.message
    assert check_load_paths_connected(form).status is Status.FAIL


def test_no_declared_load_paths_pass_vacuously():
    form = make_form(good_ir(load_paths=()))
    for check in (check_load_paths_connected, check_no_load_path_through_keepout):
        finding = check(form)
        assert finding.status is Status.PASS
        assert "no load paths declared" in finding.message
    finding = check_primary_load_path_has_ribs(form)
    assert finding.status is Status.PASS
    assert "no primary load paths" in finding.message


def test_primary_route_without_thickening_fails():
    """A primary route edge whose radius missed the +20% boost (below
    1.1x the tip radius) fails primary_load_path_has_ribs."""
    graph = replace(GOOD_GRAPH, edge_radius=(3.0, 2.0, 1.5))  # (1,3) thin
    form = make_form(good_ir(graph=graph))
    finding = check_primary_load_path_has_ribs(form)
    assert finding.status is Status.FAIL
    assert "thickening" in finding.message


def test_primary_route_off_the_spine_fails():
    """A primary route hopping over an edge that is NOT a load-path edge
    means the thickened spine does not cover the declared path."""
    graph = replace(GOOD_GRAPH, load_path_edges=((0, 1),))
    form = make_form(good_ir(graph=graph))
    finding = check_primary_load_path_has_ribs(form)
    assert finding.status is Status.FAIL
    assert "not a load-path edge" in finding.message


def test_secondary_only_load_paths_pass_primary_check_vacuously():
    secondary = LoadPathIR(from_region="stress_zone", to_region="mount",
                           priority="secondary", seed=(20.0, 0.0))
    form = make_form(good_ir(load_paths=(secondary,)))
    finding = check_primary_load_path_has_ribs(form)
    assert finding.status is Status.PASS
    assert "no primary load paths" in finding.message
