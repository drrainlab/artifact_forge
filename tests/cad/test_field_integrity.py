"""Field integrity (VF-4.1, user-reported defect): a printed cassette
arrived with 1-3 random SOLID mesh cells — the old probe sampled one cell
and statistically never landed on them. Now EVERY cell is probed (one
compound boolean for the fast path) and the finding names the solid cells;
the planar cutter builds one compound instead of chaining hundreds of
unions (the silent-drop source)."""

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.geometry import Geometry  # noqa: E402
from artifact_forge_ng.compiler.fields import cut_field  # noqa: E402
from artifact_forge_ng.core.findings import Status  # noqa: E402
from artifact_forge_ng.form.part import FieldFeature, PartForm  # noqa: E402
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile  # noqa: E402
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART  # noqa: E402
from artifact_forge_ng.validators.topology import hex_field_present  # noqa: E402

T = 3.0  # plate thickness
N = 6    # 6x6 grid of 6mm square cells, 2mm ribs


def grid_polygons(skip: set[int] = frozenset()) -> list[list[tuple[float, float]]]:
    polys = []
    idx = 0
    for i in range(N):
        for j in range(N):
            if idx not in skip:
                x0 = -24.0 + i * 8.0
                y0 = -24.0 + j * 8.0
                polys.append([(x0, y0), (x0 + 6.0, y0),
                              (x0 + 6.0, y0 + 6.0), (x0, y0 + 6.0)])
            idx += 1
    return polys


def field_of(polys) -> FieldFeature:
    return FieldFeature(plane_z=T, centers=[], cell=6.0, depth=T,
                        pattern="slots", window=(-30, -30, 30, 30),
                        keepouts=[], polygons=polys)


def form_with(field: FieldFeature) -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    return PartForm(
        name="t", params={}, frame={},
        section=SectionProfile(name="t", outer=loop),
        width=T, style=MOLDED_UTILITY_PART, fields=[field],
    )


def plate() -> cq.Workplane:
    return cq.Workplane("XY").box(60, 60, T, centered=(True, True, False))


def test_full_grid_cuts_and_passes():
    """36 cells cut as ONE compound — all 36 verified void, PASS."""
    declared = field_of(grid_polygons())
    body, ok = cut_field(plate(), declared)
    assert ok
    finding = hex_field_present(Geometry(body), form_with(declared))
    assert finding.status is Status.PASS, finding.message
    assert "every cell probed" in finding.message


def test_missing_cells_named():
    """The user's defect, reproduced: the SOLID declares 36 cells but two
    were never cut — the checker must name exactly those two."""
    declared = field_of(grid_polygons())
    body, ok = cut_field(plate(), field_of(grid_polygons(skip={7, 22})))
    assert ok
    finding = hex_field_present(Geometry(body), form_with(declared))
    assert finding.status is Status.FAIL
    assert "2/36" in finding.message
    assert "7" in finding.message and "22" in finding.message


def test_single_missing_cell_caught():
    """Even ONE solid cell out of 36 must trip the compound fast-path —
    exactly the case a single-sample probe missed for the user."""
    declared = field_of(grid_polygons())
    body, _ = cut_field(plate(), field_of(grid_polygons(skip={35})))
    finding = hex_field_present(Geometry(body), form_with(declared))
    assert finding.status is Status.FAIL
    assert "1/36" in finding.message


# -- VF-7: the EXPORTED mesh must be edge-manifold (the slicer's test) ----------


def _cassette_form(cell: float, rib: float):
    """A real coco cassette: tray + contact window + mesh floor + snaps +
    lift tabs. A fine mesh packs hundreds of openings into one planar floor
    face and OCC BRepMesh drops some — the STL arrives non-manifold."""
    from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState

    st = RecipeState()
    RECIPE_OPS["substrate_tray_body"].apply(
        st, {"cassette_l": 192.0, "cassette_w": 192.0, "h": 26.0,
             "wall": 2.4, "floor_t": 2.0, "corner_r": 3.0}, "tray")
    RECIPE_OPS["contact_window"].apply(
        st, {"window_w": 12.0, "window_l": 60.0, "drop": 1.5,
             "cx": 0.0, "cy": 0.0}, "window")
    RECIPE_OPS["mesh_floor"].apply(st, {"cell": cell, "rib": rib, "margin": 6.0}, "mesh")
    for oid, off in (("snap_window_a", -60.0), ("snap_window_b", 60.0)):
        RECIPE_OPS["snap_window_pair"].apply(
            st, {"w": 10.0, "h": 4.0, "top_offset": 8.5, "offset": off}, oid)
    RECIPE_OPS["lift_tabs"].apply(st, {"notch_w": 18.0, "notch_d": 8.0}, "lift")
    return PartForm(
        name="c", params={}, frame=st.frame, section=st.section, width=st.width,
        style=MOLDED_UTILITY_PART, channels=st.channels, cutboxes=st.cutboxes,
        bores=st.bores, ribs=st.ribs, fields=st.fields, regions=st.regions,
        datums=st.datums)


def test_default_cassette_mesh_is_manifold():
    """The shipped default (8 mm cells) tessellates into a clean manifold STL."""
    from artifact_forge_ng.compiler.solids import compile_part
    from artifact_forge_ng.validators.manufacturing import mesh_manifold

    form = _cassette_form(cell=8.0, rib=1.5)
    geo, _ = compile_part(form)
    f = mesh_manifold(geo, form)
    assert f.status is Status.PASS, f.message
    assert "watertight" in f.message


def test_fine_cassette_mesh_flagged_non_manifold():
    """A too-fine 6 mm mesh (~600+ openings in one face) out-runs BRepMesh —
    the check FAILs instead of shipping the torn STL the user's slicer
    rejected."""
    from artifact_forge_ng.compiler.solids import compile_part
    from artifact_forge_ng.validators.manufacturing import mesh_manifold

    form = _cassette_form(cell=6.0, rib=1.3)
    geo, _ = compile_part(form)
    f = mesh_manifold(geo, form)
    assert f.status is Status.FAIL
    assert "non-manifold" in f.message and f.measured > 0


def test_non_slot_part_manifold_na():
    """A part with no orthogonal slot mesh is n/a — the check never meshes it
    (organic/hex/voronoi fields have their own integrity probes)."""
    from artifact_forge_ng.validators.manufacturing import mesh_manifold

    form = PartForm(name="p", params={}, frame={},
                    section=SectionProfile(name="p", outer=ProfileLoop([
                        ArcSeg(Pt(0, -5), Pt(0, -15), Pt(0.0, -10.0), ccw=True),
                        ArcSeg(Pt(0, -15), Pt(0, -5), Pt(0.0, -10.0), ccw=True)])),
                    width=T, style=MOLDED_UTILITY_PART, fields=[])
    f = mesh_manifold(None, form)  # geometry never touched without a slot mesh
    assert f.status is Status.PASS and "n/a" in f.message
