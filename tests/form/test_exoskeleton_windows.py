"""Bio-2 organic windows: keepout clearance, guaranteed ligament, and the
honest zero-window outcome on a hopeless panel."""

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_fields import check_field_cells_present
from artifact_forge_ng.form.exoskeleton.graph import surface_rib_graph
from artifact_forge_ng.form.exoskeleton.masks import poly_clear
from artifact_forge_ng.form.exoskeleton.ribs import load_path_guided_ribs
from artifact_forge_ng.form.exoskeleton.substrate import (
    SubstrateForm,
    jittered_grid_samples,
)
from artifact_forge_ng.form.exoskeleton.windows import organic_window_field
from artifact_forge_ng.form.part import FieldFeature, PartForm
from artifact_forge_ng.form.regions import Circle2D, Rect2D, Region2D
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.form.voronoi import min_polygon_gap
from artifact_forge_ng.product.archetype import RegionRole

WINDOW = Rect2D(-40.0, -25.0, 40.0, 25.0)
MASKS = (
    Region2D(
        "boss", RegionRole.FASTENER_KEEPOUT, Circle2D(Pt(-20.0, 0.0), 5.0)
    ),
)


def build_windows(min_ligament: float = 2.0):
    samples = jittered_grid_samples(WINDOW, MASKS, pitch=8.0, seed=5)
    sub = SubstrateForm(
        window=WINDOW, pitch=8.0, seed=5, samples=samples,
        anchors=((-40.0, 0.0), (40.0, 0.0)), load_seeds=((0.0, 0.0),),
    )
    graph = surface_rib_graph(sub, MASKS, rib_density=0.5, seed=5)
    graph = load_path_guided_ribs(
        graph, rib_d_root=6.0, rib_d_tip=3.0, node_blend=2.0
    )
    return organic_window_field(
        graph, sub, MASKS,
        window_scale=0.85, min_ligament=min_ligament,
    )


def test_windows_clear_of_keepouts_and_inside_window():
    windows = build_windows()
    assert len(windows) >= 4
    for poly in windows:
        assert poly_clear(poly, MASKS)
        for x, y in poly:
            assert WINDOW.u0 - 1e-6 <= x <= WINDOW.u1 + 1e-6
            assert WINDOW.v0 - 1e-6 <= y <= WINDOW.v1 + 1e-6


def test_ligament_guaranteed_between_windows():
    ligament = 2.0
    windows = build_windows(min_ligament=ligament)
    assert len(windows) >= 2
    gap = min_polygon_gap([list(p) for p in windows])
    assert gap >= ligament - 0.05


def _minimal_form(fields):
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    return PartForm(
        name="t", params={}, frame={},
        section=SectionProfile(name="t", outer=loop),
        width=5.0, style=MOLDED_UTILITY_PART, fields=list(fields),
    )


def test_tiny_window_zero_windows_is_honest():
    tiny = Rect2D(0.0, 0.0, 8.0, 8.0)
    samples = jittered_grid_samples(tiny, (), pitch=6.0, seed=3)
    sub = SubstrateForm(
        window=tiny, pitch=6.0, seed=3, samples=samples,
        anchors=((0.0, 4.0),), load_seeds=(),
    )
    graph = surface_rib_graph(sub, (), rib_density=0.2, seed=3)
    windows = organic_window_field(
        graph, sub, (), window_scale=0.8, min_ligament=2.0
    )
    assert windows == ()  # zero windows, no invented geometry
    # ... and the declared-but-empty organic field FAILS the presence check
    form = _minimal_form([
        FieldFeature(
            plane_z=5.0, centers=(), cell=0.0, depth=5.0, pattern="organic",
            window=tiny, keepouts=(), polygons=(), min_ligament=2.0,
        )
    ])
    finding = check_field_cells_present(form)
    assert finding.status is Status.FAIL
