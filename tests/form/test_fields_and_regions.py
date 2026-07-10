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

    def test_centers_mirror_symmetric_odd_rows(self):
        """The lattice is anchored on the window CENTER: with an odd row
        count every cell has a (u,−v) mirror AND a (−u,v) mirror — a
        corner-anchored grid printed visibly off-center (the wall tool
        mount lesson). Height 35 fits 7 rows (odd) at row_pitch 5.655."""
        window = Rect2D(0.0, -17.5, 40.0, 17.5)  # center (20, 0)
        centers = hex_field_centers(window, cell=5.0, wall_gap=1.5)
        assert len(centers) > 10
        assert len({round(v, 6) for _, v in centers}) == 7
        have = {(round(u, 6), round(v, 6)) for u, v in centers}
        for u, v in centers:
            assert (round(u, 6), round(-v, 6)) in have, f"no v-mirror for {(u, v)}"
            assert (round(40.0 - u, 6), round(v, 6)) in have, f"no u-mirror for {(u, v)}"
        cu = sum(u for u, _ in centers) / len(centers)
        cv = sum(v for _, v in centers) / len(centers)
        assert cu == pytest.approx(20.0, abs=1e-6)
        assert cv == pytest.approx(0.0, abs=1e-6)

    def test_even_row_stack_stays_centered(self):
        """Height 40 fits 8 rows (even): strict point mirror is impossible
        for a staggered stack, but the STACK is centered (row positions
        mirror about mid-v) and every row is centered in u — no leftover
        margin dumped on one side."""
        window = Rect2D(0.0, -20.0, 40.0, 20.0)
        centers = hex_field_centers(window, cell=5.0, wall_gap=1.5)
        rows: dict[float, list[float]] = {}
        for u, v in centers:
            rows.setdefault(round(v, 6), []).append(u)
        vs = sorted(rows)
        assert len(vs) == 8
        for a, b in zip(vs, reversed(vs)):
            assert a == pytest.approx(-b, abs=1e-6)  # row positions mirror
        for v, us in rows.items():
            assert sum(us) / len(us) == pytest.approx(20.0, abs=1e-6)

    def test_stagger_survives_centering(self):
        """Consecutive rows stay offset by pitch/2 — centering must not
        collapse the hex packing into a square grid."""
        centers = hex_field_centers(Rect2D(0, 0, 40, 40), cell=5.0, wall_gap=1.5)
        rows: dict[float, list[float]] = {}
        for u, v in centers:
            rows.setdefault(round(v, 6), []).append(u)
        vs = sorted(rows)
        assert len(vs) >= 3
        for a, b in zip(vs, vs[1:]):
            # min-u of neighbouring rows differs by half a pitch
            assert abs(min(rows[a]) - min(rows[b])) == pytest.approx(6.5 / 2)

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
    form = builder(resolved, archetype, instance)
    from artifact_forge_ng.modifiers import apply_modifiers

    apply_modifiers(form, instance.modifiers, catalog.modifiers_for(instance), archetype)
    return form, archetype


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

    def test_screws_beside_hook_and_countersink_below(self, flagship_form):
        form, _ = flagship_form
        from artifact_forge_ng.form.validators import check_screw_access_clear
        from artifact_forge_ng.core.findings import Status

        assert check_screw_access_clear(form).status is Status.PASS
        for hole in form.holes:
            x, _, _ = hole.at
            assert x < 0 or x > form.width  # beside the hook, not over it
            assert hole.countersink_face == "bottom"

    def test_hole_over_hook_fails_access_check(self, flagship_form):
        """The v1-style layout (hole over the lip) must FAIL the new check."""
        from artifact_forge_ng.form.part import HoleFeature
        from artifact_forge_ng.form.validators import check_screw_access_clear
        from artifact_forge_ng.core.findings import Status

        form, _ = flagship_form
        bad_hole = HoleFeature(
            at=(form.width / 2.0, 25.0, form.plates[0].z_top),  # over the lip
            screw="M4",
            through=form.plates[0].thickness,
        )
        original_holes = form.holes
        try:
            form.holes = [bad_hole]
            finding = check_screw_access_clear(form)
            assert finding.status is Status.FAIL
            assert finding.critical
        finally:
            form.holes = original_holes

    def test_narrow_spacing_clamped_to_driver_clearance(self, flagship_form):
        """ТЗ regression asks ~30mm spacing; the archetype floor honestly
        clamps it past the hook so the screws stay reachable."""
        from artifact_forge_ng.catalog.loader import load_catalog, load_instance
        from artifact_forge_ng.product.instance import ProductInstance
        from artifact_forge_ng.product.resolve import resolve_params

        catalog = load_catalog()
        instance = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
        data = instance.model_dump(by_alias=True)
        data["params"]["screw_spacing"] = "30mm"
        instance = ProductInstance.model_validate(data)
        archetype = catalog.archetypes[instance.archetype_id]
        resolved = resolve_params(archetype, instance)
        assert resolved.context["screw_spacing"] == pytest.approx(
            resolved.context["flange_w"] + 13.0
        )
