"""Mutation tests for the substrate cassette form checks: a healthy
hand-built cassette IR (matching the Cassette Interface Standard frame
keys) passes everything; each broken variant fails exactly its owning
check."""

from dataclasses import replace

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_substrate_cassette import (
    check_cassette_no_reservoir,
    check_contact_window_geometry_ok,
    check_lift_access_ok,
    check_mesh_floor_orthogonal_ok,
    check_snap_pockets_cleanable,
)
from artifact_forge_ng.form.checks_water import check_no_secondary_water_channel
from artifact_forge_ng.form.part import (
    CutBoxFeature,
    FieldFeature,
    PartForm,
    RibFeature,
)
from artifact_forge_ng.form.regions import Box3, Region
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.archetype import RegionRole

CASSETTE_CHECKS = (
    check_mesh_floor_orthogonal_ok,
    check_cassette_no_reservoir,
    check_contact_window_geometry_ok,
    check_snap_pockets_cleanable,
    check_lift_access_ok,
    check_no_secondary_water_channel,
)

FLOOR_T = 2.0
DROP = 1.5
CELL = 6.0
RIB = 1.3
PITCH = CELL + RIB


def grid_polygons(nx=5, ny=5, cell=CELL, pitch=PITCH):
    polys = []
    for i in range(nx):
        for j in range(ny):
            cx = (i - (nx - 1) / 2.0) * pitch
            cy = (j - (ny - 1) / 2.0) * pitch
            h = cell / 2.0
            polys.append((
                (cx - h, cy - h), (cx + h, cy - h),
                (cx + h, cy + h), (cx - h, cy + h),
            ))
    return tuple(polys)


def good_field(**over) -> FieldFeature:
    kw: dict = dict(
        plane_z=FLOOR_T, centers=(), cell=CELL,
        depth=FLOOR_T + DROP + 1.0, pattern="slots",
        polygons=grid_polygons(), min_ligament=RIB,
    )
    kw.update(over)
    return FieldFeature(**kw)


def good_frame(**over) -> dict:
    f = dict(
        floor_t=FLOOR_T, shell_wall=2.4, shell_h=26.0,
        cassette_u0=-110.0, cassette_v0=-110.0,
        cassette_u1=110.0, cassette_v1=110.0,
        cassette_h=26.0, floor_bottom_z=0.0,
        window_cx=0.0, window_w=32.0, window_l=60.0,
        window_drop=DROP, window_floor_z=-DROP,
        lift_notch_w=18.0, lift_notch_d=8.0, lift_notch_count=2.0,
        inner_u0=-107.6, inner_u1=107.6,
    )
    f.update(over)
    return f


def good_regions() -> list[Region]:
    return [
        Region("mesh_canvas", RegionRole.SUBSTRATE_SUPPORT_MESH,
               Box3(-18.0, -18.0, 0.0, 18.0, 18.0, FLOOR_T)),
        Region("contact_window", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-16.0, -30.0, -DROP - 0.1, 16.0, 30.0, 0.6)),
    ]


def good_snap_windows() -> list[CutBoxFeature]:
    return [
        CutBoxFeature("snap_window_0", Box3(107.5, -5.0, 8.0, 110.5, 5.0, 12.0)),
        CutBoxFeature("snap_window_1", Box3(-110.5, -5.0, 8.0, -107.5, 5.0, 12.0)),
    ]


def make_cassette(fields=None, frame=None, cutboxes=None, ribs=None,
                  regions=None) -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    return PartForm(
        name="cassette", params={},
        frame=good_frame() if frame is None else frame,
        section=SectionProfile(name="cassette", outer=loop),
        width=26.0, style=MOLDED_UTILITY_PART,
        fields=[good_field()] if fields is None else fields,
        cutboxes=good_snap_windows() if cutboxes is None else cutboxes,
        ribs=[RibFeature("cassette_window_slab",
                         Box3(-16.0, -30.0, -DROP, 16.0, 30.0, 0.6))]
        if ribs is None else ribs,
        regions=good_regions() if regions is None else regions,
    )


def failing(form: PartForm) -> set:
    return {c.__name__ for c in CASSETTE_CHECKS if c(form).status is Status.FAIL}


def test_healthy_cassette_passes_everything():
    form = make_cassette()
    for check in CASSETTE_CHECKS:
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_big_mesh_cell_rejected():
    form = make_cassette(fields=[good_field(polygons=grid_polygons(cell=10.0, pitch=11.3))])
    assert "check_mesh_floor_orthogonal_ok" in failing(form)


def test_thin_mesh_rib_rejected():
    form = make_cassette(fields=[good_field(min_ligament=0.9)])
    assert failing(form) == {"check_mesh_floor_orthogonal_ok"}


def test_non_orthogonal_mesh_rejected():
    tri = (((0.0, 0.0), (6.0, 0.0), (3.0, 6.0)),) * 25
    form = make_cassette(fields=[good_field(polygons=tri)])
    assert "check_mesh_floor_orthogonal_ok" in failing(form)


def test_directional_mesh_rejected():
    # a tilted field is a flow-directing mesh — both the mesh check and the
    # secondary-channel detector own this defect
    form = make_cassette(fields=[good_field(origin=(0.0, 0.0, 2.0), tilt_deg=15.0)])
    fails = failing(form)
    assert "check_mesh_floor_orthogonal_ok" in fails
    assert "check_no_secondary_water_channel" in fails


def test_shallow_mesh_is_reservoir():
    form = make_cassette(fields=[good_field(depth=2.2)])
    assert failing(form) == {"check_cassette_no_reservoir"}


def test_partial_mesh_coverage_is_reservoir():
    # mesh only on one half of the floor — the bare half pools water
    half = tuple(p for p in grid_polygons() if all(x <= 0.5 for x, _ in p))
    form = make_cassette(fields=[good_field(polygons=half)])
    assert "check_cassette_no_reservoir" in failing(form)


def test_deep_window_rejected():
    # mesh deepened to keep piercing — the drop band is the only defect
    form = make_cassette(
        fields=[good_field(depth=FLOOR_T + 3.0 + 1.0)],
        frame=good_frame(window_drop=3.0, window_floor_z=-3.0),
    )
    assert failing(form) == {"check_contact_window_geometry_ok"}


def test_shallow_window_rejected():
    form = make_cassette(frame=good_frame(window_drop=0.5, window_floor_z=-0.5))
    assert failing(form) == {"check_contact_window_geometry_ok"}


def test_missing_window_slab_rejected():
    form = make_cassette(ribs=[])
    assert failing(form) == {"check_contact_window_geometry_ok"}


def test_blind_snap_pocket_rejected():
    blind = [
        CutBoxFeature("snap_window_0", Box3(108.5, -5.0, 8.0, 110.5, 5.0, 12.0)),
        CutBoxFeature("snap_window_1", Box3(-110.5, -5.0, 8.0, -108.5, 5.0, 12.0)),
    ]
    form = make_cassette(cutboxes=blind)
    assert failing(form) == {"check_snap_pockets_cleanable"}


def test_no_snap_pockets_is_vacuously_clean():
    form = make_cassette(cutboxes=[])
    assert check_snap_pockets_cleanable(form).status is Status.PASS


def test_missing_lift_notches_rejected():
    form = make_cassette(frame=good_frame(lift_notch_count=0.0))
    assert failing(form) == {"check_lift_access_ok"}


def test_narrow_lift_notch_rejected():
    form = make_cassette(frame=good_frame(lift_notch_w=10.0))
    assert failing(form) == {"check_lift_access_ok"}


def test_hex_floor_field_rejected():
    form = make_cassette(fields=[good_field(pattern="hex")])
    fails = failing(form)
    assert "check_no_secondary_water_channel" in fails
    assert "check_mesh_floor_orthogonal_ok" in fails


def test_field_replace_is_frozen():
    fld = good_field()
    assert replace(fld, depth=9.0).depth == 9.0
