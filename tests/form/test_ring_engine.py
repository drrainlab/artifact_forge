"""Ring engine, tier-1: revolve_band frame/regions, cylindrical mapping
math, seed determinism, honest refusals, local catalog merge."""

import math
from pathlib import Path

import pytest

from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.form.part import FieldFeature
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
RING = EXAMPLES / "mens_ring_voronoi.yaml"


def _band(**over) -> RecipeState:
    st = RecipeState()
    p = {"inner_d": 20.4, "height": 8.0, "wall": 2.2, "corner_r": 0.8,
         "size_clearance": 0.25, "seam_keepout": 2.0, "edge_margin": 0.9}
    p.update(over)
    RECIPE_OPS["revolve_band"].apply(st, p, "band")
    return st


def test_revolve_band_frame_and_regions():
    st = _band()
    f = st.frame
    assert st.kind == "profile_revolve"
    assert f["inner_d_effective"] == pytest.approx(20.65)
    assert f["outer_r"] == pytest.approx(20.65 / 2 + 2.2)
    assert f["cyl_r_mid"] == pytest.approx((f["inner_r"] + f["outer_r"]) / 2)
    names = {r.name for r in st.regions}
    assert {"band_outer_surface", "bore_contact", "seam_keepout",
            "top_edge_keepout", "bottom_edge_keepout"} <= names
    # half-section entirely on the +u side of the axis
    lo, _ = st.section.outer.bbox()
    assert lo.u >= f["inner_r"] - 1e-9


def test_cylindrical_local_to_world_math():
    field = FieldFeature(
        plane_z=0, centers=(), cell=0, depth=2.2,
        mapping="cylindrical", cyl_center=(0.0, 0.0),
        cyl_r=11.425, cyl_r_outer=12.525, cyl_z0=0.0,
    )
    for deg in (0, 90, 180, 270):
        a = math.radians(deg) * 11.425
        x, y, z = field.local_to_world(a, 4.0, 0.0)
        assert math.hypot(x, y) == pytest.approx(12.525)
        assert math.degrees(math.atan2(y, x)) % 360 == pytest.approx(deg, abs=1e-6)
        assert z == pytest.approx(4.0)
    # depth n moves inward radially
    x, y, _ = field.local_to_world(0.0, 0.0, 2.2)
    assert math.hypot(x, y) == pytest.approx(12.525 - 2.2)


def test_too_thin_wall_refused():
    with pytest.raises(RecipeError, match="too thin"):
        _band(wall=1.2)


@pytest.fixture(scope="module")
def ring_state():
    return run_pre_cad(RING, None)


def test_ring_ir_green_with_cylindrical_field(ring_state):
    fails = [f for f in ring_state.report.findings if f.status.value == "fail"]
    assert fails == []
    form = ring_state.form
    field = form.fields[0]
    assert field.mapping == "cylindrical"
    assert field.polygons, "no voronoi cells on the band"
    # every cell inside the window: past the seam, inside the band height
    w = form.windows["band_outer_surface"].window
    for poly in field.polygons:
        for a, b in poly:
            assert w.u0 - 1e-6 <= a <= w.u1 + 1e-6
            assert w.v0 - 1e-6 <= b <= w.v1 + 1e-6


def test_seed_determinism(ring_state):
    again = run_pre_cad(RING, None)
    assert again.form.fields[0].polygons == ring_state.form.fields[0].polygons


def test_ligament_and_arc_bound(ring_state):
    field = ring_state.form.fields[0]
    assert field.min_ligament == pytest.approx(1.2)
    r = field.cyl_r
    for poly in field.polygons:
        width = max(p[0] for p in poly) - min(p[0] for p in poly)
        assert width <= 0.6 * r + 1e-6, "cell too wide for tangent-plane cut"


def test_local_catalog_merged():
    catalog = load_catalog()
    assert "finger_ring_v1" in catalog.archetypes
    assert catalog.origins["finger_ring_v1"] == "local"
    assert catalog.origins["underdesk_cable_clip_v2_molded"] == "builtin"
