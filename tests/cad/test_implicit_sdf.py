"""Bio-4M unit level: SDF primitives on known points, smooth-min algebra,
marching-cubes watertightness on an analytic sphere, the byte-deterministic
STL writer, print-orientation parity with the BRep path, and the shared
fastener cut dimensions."""

import math
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")

from artifact_forge_ng.compiler.implicit.mesh import (  # noqa: E402
    eval_grid,
    marching_cubes_mesh,
    mesh_watertight,
    orient_vertices_for_print,
    plan_grid,
)
from artifact_forge_ng.compiler.implicit.sdf import (  # noqa: E402
    Profile2D,
    planar_frame,
    sd_box,
    sd_capsule,
    sd_cylinder_axis,
    sd_extruded_profile,
    sd_frustum_z,
    sd_prism_polygon,
    sd_sphere,
    smax,
    smin,
)
from artifact_forge_ng.compiler.implicit.stl import (  # noqa: E402
    read_binary_stl,
    write_binary_stl,
)
from artifact_forge_ng.core.fasteners import hole_cut_dims, screw_spec  # noqa: E402
from artifact_forge_ng.form.profiles_plate import rounded_rect_loop  # noqa: E402


def pts(*xyz):
    return np.asarray(xyz, dtype=np.float64)


# ---------------------------------------------------------------------------
# 2D profile: the demo plate's rounded-rect loop, lines AND arcs
# ---------------------------------------------------------------------------


class TestProfile2D:
    LOOP = rounded_rect_loop(-60.0, -40.0, 60.0, 40.0, 6.0)

    def test_known_points_on_lines(self):
        prof = Profile2D(self.LOOP)
        u = np.array([0.0, 0.0, 0.0, 0.0])
        v = np.array([0.0, 40.0, 41.0, 39.0])
        d = prof.signed(u, v)
        assert d[0] == pytest.approx(-40.0, abs=1e-9)
        assert d[1] == pytest.approx(0.0, abs=1e-6)
        assert d[2] == pytest.approx(1.0, abs=1e-9)
        assert d[3] == pytest.approx(-1.0, abs=1e-9)

    def test_known_points_on_corner_arc(self):
        prof = Profile2D(self.LOOP)
        # corner arc center (54, 34), r = 6
        s = 6.0 / math.sqrt(2.0)
        u = np.array([54.0 + s, 60.0, 54.0])
        v = np.array([34.0 + s, 40.0, 34.0])
        d = prof.signed(u, v)
        assert d[0] == pytest.approx(0.0, abs=1e-5)  # exactly on the arc
        assert d[1] == pytest.approx(math.hypot(6, 6) - 6.0, abs=1e-6)  # outside corner
        assert d[2] == pytest.approx(-6.0, abs=1e-6)  # arc center, inside

    def test_extrusion_slab(self):
        prof = Profile2D(self.LOOP)
        P = pts((0, 0, 3), (0, 0, 7), (0, 0, -1), (0, 41, 3))
        d = sd_extruded_profile(P, prof, "XY", "Z", 0.0, 6.0)
        assert d[0] == pytest.approx(-3.0, abs=1e-9)
        assert d[1] == pytest.approx(1.0, abs=1e-9)
        assert d[2] == pytest.approx(1.0, abs=1e-9)
        assert d[3] == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# solid primitives
# ---------------------------------------------------------------------------


def test_capsule_known_points():
    a, b, r = (0, 0, 0), (10, 0, 0), 2.0
    d = sd_capsule(pts((5, 0, 0), (5, 0, 3), (13, 0, 0), (0, 0, 2)), a, b, r)
    assert d[0] == pytest.approx(-2.0)
    assert d[1] == pytest.approx(1.0)
    assert d[2] == pytest.approx(1.0)
    assert d[3] == pytest.approx(0.0, abs=1e-12)


def test_sphere_box_cylinder():
    d = sd_sphere(pts((0, 0, 0), (0, 4, 0)), (0, 0, 0), 3.0)
    assert d[0] == pytest.approx(-3.0) and d[1] == pytest.approx(1.0)
    d = sd_box(pts((1, 1, 1), (3, 1, 1), (-1, -1, -1)), (0, 0, 0), (2, 2, 2))
    assert d[0] == pytest.approx(-1.0)
    assert d[1] == pytest.approx(1.0)
    assert d[2] == pytest.approx(math.sqrt(3.0))
    d = sd_cylinder_axis(
        pts((0, 0, 5), (3, 0, 5), (0, 0, 11), (3, 0, 11)), "Z", (0, 0, 0), 2.0, 0.0, 10.0
    )
    assert d[0] == pytest.approx(-2.0)
    assert d[1] == pytest.approx(1.0)
    assert d[2] == pytest.approx(1.0)
    assert d[3] == pytest.approx(math.hypot(1.0, 1.0))


def test_frustum_countersink_shape():
    # r0=1 at z0=0 opening to r1=3 at z1=2 (a countersink upside up)
    P = pts((0, 0, 1), (0, 0, -1), (3, 0, 2), (4, 0, 2), (0, 0, 2.5))
    d = sd_frustum_z(P, 0.0, 0.0, 0.0, 2.0, 1.0, 3.0)
    assert d[0] == pytest.approx(-1.0)  # axis mid-height: 1 below top disk
    assert d[1] == pytest.approx(1.0)  # below the bottom disk
    assert d[2] == pytest.approx(0.0, abs=1e-9)  # on the top rim
    assert d[3] == pytest.approx(1.0)  # radially out from the rim
    assert d[4] == pytest.approx(0.5)  # above the top disk


def test_prism_polygon_in_panel_frame():
    frame = planar_frame(None, 0.0, 0.0)  # horizontal panel at z=0, n = -z
    poly = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    P = pts((5, 5, -2), (5, 5, 1), (5, 5, -6), (12, 5, -2))
    d = sd_prism_polygon(P, poly, frame, 0.0, 5.0)
    assert d[0] == pytest.approx(-2.0)  # inside, 2 below the top entry
    assert d[1] == pytest.approx(1.0)  # above the entry plane
    assert d[2] == pytest.approx(1.0)  # below the prism floor
    assert d[3] == pytest.approx(2.0)  # outside the polygon


def test_smin_smax_properties():
    rng = np.random.default_rng(7)
    a = rng.uniform(-5, 5, 300)
    b = rng.uniform(-5, 5, 300)
    k = 1.5
    s = smin(a, b, k)
    assert np.all(s <= np.minimum(a, b) + 1e-12)  # only ever adds material
    far = np.abs(a - b) >= k
    assert np.allclose(s[far], np.minimum(a, b)[far])  # exact hard min far away
    assert np.allclose(smax(a, b, k), -smin(-a, -b, k))
    assert np.allclose(smin(a, b, 0.0), np.minimum(a, b))  # k=0 degrades hard


# ---------------------------------------------------------------------------
# marching cubes watertightness on an analytic sphere
# ---------------------------------------------------------------------------


def test_watertight_analytic_sphere():
    pytest.importorskip("skimage")
    plan = plan_grid(((-11, -11, -11), (11, 11, 11)), 0.5)
    values = eval_grid(lambda P: sd_sphere(P, (0, 0, 0), 10.0), plan)
    verts, faces = marching_cubes_mesh(values, plan)
    ok, stats = mesh_watertight(verts, faces)
    assert ok, stats
    assert stats["triangles"] > 1000
    radii = np.linalg.norm(verts, axis=1)
    assert float(np.abs(radii - 10.0).max()) < 0.4  # verts sit on the sphere


def test_voxel_budget_auto_coarsens():
    plan = plan_grid(((0, 0, 0), (100, 100, 100)), 0.2, max_voxels=1_000_000)
    assert plan.voxel_count <= 1_000_000
    assert plan.resolution > 0.2
    assert any("auto-coarsened" in n for n in plan.notes)


def test_feature_limit_auto_refines():
    plan = plan_grid(((0, 0, 0), (10, 10, 10)), 1.0, feature_limit=0.5)
    assert plan.resolution == pytest.approx(0.5)
    assert any("auto-refined" in n for n in plan.notes)


# ---------------------------------------------------------------------------
# STL writer
# ---------------------------------------------------------------------------


def test_stl_round_trip_and_byte_stability(tmp_path):
    verts = np.array(
        [[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]], dtype=np.float64
    )
    faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]], dtype=np.int64)
    p1 = write_binary_stl(tmp_path / "a.stl", verts, faces)
    p2 = write_binary_stl(tmp_path / "b.stl", verts, faces)
    assert p1.read_bytes() == p2.read_bytes()  # byte-deterministic
    normals, tris = read_binary_stl(p1)
    assert tris.shape == (4, 3, 3)
    assert np.allclose(tris, verts[faces].astype(np.float32))
    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0, atol=1e-6)


# ---------------------------------------------------------------------------
# print orientation parity with the BRep path (needs cadquery)
# ---------------------------------------------------------------------------


@pytest.mark.cad
def test_orient_vertices_parity_with_cq_rotate():
    cq = pytest.importorskip("cadquery")
    from artifact_forge_ng.cad.geometry import Geometry
    from artifact_forge_ng.compiler.pipeline import orient_for_print

    corners = np.array(
        [[x, y, z] for x in (2.0, 9.0) for y in (-3.0, 4.0) for z in (1.0, 11.0)]
    )
    box = (
        cq.Workplane("XY", origin=(2.0, -3.0, 1.0))
        .box(7.0, 7.0, 10.0, centered=False)
    )
    form = SimpleNamespace(print_orientation="side_profile")
    bb = orient_for_print(Geometry(box), form).bounding_box()
    mine = orient_vertices_for_print(corners, form)
    assert mine[:, 0].min() == pytest.approx(bb.xmin, abs=1e-6)
    assert mine[:, 0].max() == pytest.approx(bb.xmax, abs=1e-6)
    assert mine[:, 1].min() == pytest.approx(bb.ymin, abs=1e-6)
    assert mine[:, 1].max() == pytest.approx(bb.ymax, abs=1e-6)
    assert mine[:, 2].min() == pytest.approx(bb.zmin, abs=1e-6)
    assert mine[:, 2].max() == pytest.approx(bb.zmax, abs=1e-6)
    # as_modeled passes through untouched
    form2 = SimpleNamespace(print_orientation="as_modeled")
    assert np.array_equal(orient_vertices_for_print(corners, form2), corners)


# ---------------------------------------------------------------------------
# hole_cut_dims — the one fastener-cut source (BRep and SDF share it)
# ---------------------------------------------------------------------------


def test_hole_cut_dims_matches_brep_formulas():
    spec = screw_spec("m4")
    cone = hole_cut_dims("M4", 6.0)
    assert cone["bore_d"] == pytest.approx(spec["clear"] + 0.2)
    assert cone["head_r"] == pytest.approx(spec["head"] / 2.0)
    assert cone["seat_r"] == pytest.approx(spec["head"] / 2.0 + 0.3)
    assert cone["cs_depth"] == pytest.approx(min(2.0, 6.0 * 0.4))
    assert cone["cs_tip_r"] == pytest.approx(0.5)
    cyl = hole_cut_dims("M4", 6.0, head_style="cylinder")
    assert cyl["cb_depth"] == pytest.approx(min(spec["head"] * 0.8, 3.0))
    assert "cs_depth" not in cyl
