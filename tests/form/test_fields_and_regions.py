"""Hex fields with keepouts, and the flagship PartForm's regions."""

import math
from pathlib import Path

import pytest

from artifact_forge_ng.archetypes import builder_for
from artifact_forge_ng.catalog.loader import load_catalog, load_instance, validate_instance
from artifact_forge_ng.form.fields import apply_field_with_keepouts, hex_field_centers
from artifact_forge_ng.form.regions import Circle2D, Rect2D, Region2D
from artifact_forge_ng.form.section import Pt
from artifact_forge_ng.product.archetype import RegionRole
from artifact_forge_ng.product.resolve import resolve_params

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


class TestHexField:
    def test_centers_fill_window(self):
        centers = hex_field_centers(Rect2D(0, 0, 30, 30), cell=5.0, wall_gap=1.5)
        assert len(centers) > 10
        assert all(0 <= u <= 30 and 0 <= v <= 30 for u, v in centers)

    def test_empty_window_no_centers(self):
        assert hex_field_centers(Rect2D(5, 5, 5, 5), 5.0, 1.5) == []

    def test_keepouts_filter_cells(self):
        keepout = Region2D(
            "screw", RegionRole.FASTENER_KEEPOUT, Circle2D(Pt(15, 15), 6.0)
        )
        field = apply_field_with_keepouts(
            window=Rect2D(0, 0, 30, 30),
            keepouts=[keepout],
            cell=5.0,
            wall_gap=1.5,
            margin=2.0,
            plane_z=5.0,
            depth=5.0,
        )
        r_hex = 5.0 / math.sqrt(3)
        assert field.centers
        for cu, cv in field.centers:
            assert math.hypot(cu - 15, cv - 15) > 6.0 + r_hex

    def test_window_smaller_than_margin_is_graceful(self):
        field = apply_field_with_keepouts(
            window=Rect2D(0, 0, 6, 6),
            keepouts=[],
            cell=5.0,
            wall_gap=1.5,
            margin=10.0,
            plane_z=1.0,
            depth=1.0,
        )
        assert field.centers == ()


@pytest.fixture(scope="module")
def flagship_form():
    catalog = load_catalog()
    instance = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
    archetype = validate_instance(instance, catalog)
    resolved = resolve_params(archetype, instance)
    assert resolved.ok
    builder = builder_for(archetype)
    assert builder is not None
    return builder(resolved, archetype, instance), archetype


class TestFlagshipForm:
    def test_all_declared_regions_present(self, flagship_form):
        form, archetype = flagship_form
        have = {r.name for r in form.regions}
        assert have >= {r.id for r in archetype.regions}

    def test_screw_keepouts_contain_hole_centers(self, flagship_form):
        form, _ = flagship_form
        zone = form.region("screw_zones")
        assert zone is not None
        for hole in form.holes:
            x, y, z = hole.at
            assert zone.box.contains(x, y, z - 0.1)

    def test_hex_cells_avoid_screws_and_neck(self, flagship_form):
        form, _ = flagship_form
        assert form.fields, "hex modifier requested but no field built"
        field = form.fields[0]
        assert len(field.centers) > 0
        r_hex = field.cell / math.sqrt(3)
        for hole in form.holes:
            hx, hy, _ = hole.at
            for cu, cv in field.centers:
                assert math.hypot(cu - hx, cv - hy) > form.frame["screw_head_r"] + r_hex

    def test_flange_above_hook(self, flagship_form):
        form, _ = flagship_form
        _, hi = form.section.outer.bbox()
        assert form.plates[0].z_bottom >= hi.v - 1.0

    def test_datums_present(self, flagship_form):
        form, _ = flagship_form
        assert "flange_face" in form.datums and "mouth_center" in form.datums
