"""Modifier kernel tier-1: determinism, ligament guarantees, keepout
composition, additive ribs — and the negatives that keep it honest."""

from pathlib import Path

import pytest

from artifact_forge_ng.archetypes import builder_for
from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.cli import run_validate
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_fields import check_min_ligament_ok
from artifact_forge_ng.form.regions import Rect2D
from artifact_forge_ng.form.voronoi import min_polygon_gap, voronoi_cells
from artifact_forge_ng.modifiers import apply_modifiers
from artifact_forge_ng.product.instance import ProductInstance
from artifact_forge_ng.product.resolve import resolve_params

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
SHOWCASE = EXAMPLES / "showcase_plate_voronoi.yaml"


def build_form_with_modifiers(path=SHOWCASE, mutate=None):
    catalog = load_catalog()
    instance = load_instance(path)
    if mutate:
        data = instance.model_dump(by_alias=True)
        mutate(data)
        instance = ProductInstance.model_validate(data)
    archetype = catalog.archetypes[instance.archetype_id]
    resolved = resolve_params(archetype, instance)
    assert resolved.ok
    form = builder_for(archetype)(resolved, archetype, instance)
    findings = apply_modifiers(
        form, instance.modifiers, catalog.modifiers_for(instance), archetype
    )
    return form, findings


def test_showcase_validates():
    out = run_validate(SHOWCASE, strict_flag=None)
    assert out["status"] == "pass"


class TestVoronoi:
    WINDOW = Rect2D(-20, -13, 20, 13)

    def test_same_seed_same_cells(self):
        a = voronoi_cells(self.WINDOW, [], seed=7, sites=12,
                          min_ligament=1.6, edge_margin=3.0)
        b = voronoi_cells(self.WINDOW, [], seed=7, sites=12,
                          min_ligament=1.6, edge_margin=3.0)
        assert a == b  # deterministic: same YAML, same object

    def test_different_seed_different_cells(self):
        a = voronoi_cells(self.WINDOW, [], seed=7, sites=12,
                          min_ligament=1.6, edge_margin=3.0)
        b = voronoi_cells(self.WINDOW, [], seed=8, sites=12,
                          min_ligament=1.6, edge_margin=3.0)
        assert a != b

    def test_ligament_guaranteed(self):
        cells = voronoi_cells(self.WINDOW, [], seed=42, sites=16,
                              min_ligament=2.0, edge_margin=3.0)
        assert len(cells) >= 6
        assert min_polygon_gap([list(c) for c in cells]) >= 2.0 - 0.05

    def test_negative_ligament_violation_caught(self):
        """A hand-built field with touching polygons FAILS the check."""
        from artifact_forge_ng.form.part import FieldFeature, PartForm
        from artifact_forge_ng.form.section import ArcSeg, ProfileLoop, Pt, SectionProfile
        from artifact_forge_ng.form.style import MOLDED_UTILITY_PART

        c = Pt(0.0, -10.0)
        loop = ProfileLoop([
            ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
            ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
        ])
        form = PartForm(
            name="t", params={}, frame={},
            section=SectionProfile(name="t", outer=loop),
            width=5.0, style=MOLDED_UTILITY_PART,
            fields=[FieldFeature(
                plane_z=5.0, centers=(), cell=0.0, depth=5.0,
                pattern="voronoi",
                polygons=(((0, 0), (10, 0), (10, 10), (0, 10)),
                          ((10.3, 0), (20, 0), (20, 10), (10.3, 10))),
                min_ligament=1.6,
            )],
        )
        finding = check_min_ligament_ok(form)
        assert finding.status is Status.FAIL


class TestComposition:
    def test_showcase_composes_all_three(self):
        form, findings = build_form_with_modifiers()
        assert len([b for b in form.bores if "magnet" in b.name]) == 2
        assert len([c for c in form.cutboxes if "zip" in c.name]) == 2
        voronoi = [f for f in form.fields if f.pattern == "voronoi"]
        assert voronoi and len(voronoi[0].polygons) >= 4
        assert all(f.status is not Status.FAIL for f in findings)

    def test_prior_cuts_become_keepouts(self):
        """Voronoi cells must clear the zip slots cut before them."""
        form, _ = build_form_with_modifiers()
        voronoi = [f for f in form.fields if f.pattern == "voronoi"][0]
        slot_names = {k.name for k in voronoi.keepouts}
        assert any("prior_cut_zip_slot" in n for n in slot_names)
        assert any("prior_bore_magnet" in n for n in slot_names)

    def test_modifier_without_applicator_is_engine_gap(self):
        def mutate(data):
            data["modifiers"] = [
                {"id": "fillet_soften", "target": "plate_face", "params": {}}
            ]
            data["requested_features"] = ["mounting_plate_body", "hole_pattern"]

        _, findings = build_form_with_modifiers(mutate=mutate)
        gaps = [f for f in findings if "no applicator" in f.message]
        assert gaps and gaps[0].status is Status.WARN


class TestRibs:
    def test_ribs_applicator_places_and_skips(self):
        def mutate(data):
            data["modifiers"] = [
                {"id": "add_ribs", "target": "center_zone",
                 "params": {"count": 3, "rib_h": "3mm"}}
            ]
            data["requested_features"] = ["mounting_plate_body", "stiffening_ribs"]

        form, findings = build_form_with_modifiers(mutate=mutate)
        assert len(form.ribs) >= 2
        assert all(f.status is not Status.FAIL for f in findings)
        # ribs sink into the plate by the weld rule
        for rib in form.ribs:
            assert rib.box.z0 < form.params["thickness"]

    def test_magnet_pocket_too_deep_fails(self):
        def mutate(data):
            data["params"]["thickness"] = "3mm"
            data["modifiers"] = [
                {"id": "add_magnet_pockets", "target": "plate_face",
                 "params": {"magnet_d": "6mm", "magnet_h": "3mm"}}
            ]
            data["requested_features"] = ["mounting_plate_body", "magnet_pockets"]

        _, findings = build_form_with_modifiers(mutate=mutate)
        fails = [f for f in findings if f.status is Status.FAIL]
        assert fails and "skin" in fails[0].message


class TestVoronoiOnStand:
    """The plain phone stand takes a voronoi field on its rear base deck —
    a non-plate host (depth from the region box), keepouts from rest_root."""

    def test_field_on_rear_deck_clears_rest_root(self):
        from artifact_forge_ng.pipeline import run_pre_cad

        state = run_pre_cad(EXAMPLES / "phone_stand_voronoi.yaml", False)
        form = state.form
        field = [f for f in form.fields if f.pattern == "voronoi"][0]
        assert len(field.polygons) >= 8
        assert field.depth == pytest.approx(form.params["base_t"])  # through
        rest_end = form.frame["rest_foot_end"]
        lo_y = min(p[1] for poly in field.polygons for p in poly)
        assert lo_y > rest_end + 2.0  # never into the rest root
        assert state.report.status is not Status.FAIL

    def test_std_stand_untouched(self):
        from artifact_forge_ng.pipeline import run_pre_cad

        form = run_pre_cad(EXAMPLES / "phone_stand_std.yaml", False).form
        assert form.fields == []
        assert form.region("base_lightening") is not None  # canvas declared


class TestOrientedBackField:
    """Fields on the TILTED back face via the oriented FaceWindow."""

    def test_back_field_local_frame_exact(self):
        from artifact_forge_ng.pipeline import run_pre_cad
        import math

        state = run_pre_cad(EXAMPLES / "phone_stand_voronoi_back.yaml", False)
        form = state.form
        field = [f for f in form.fields if f.pattern == "voronoi"][0]
        assert field.tilt_deg == pytest.approx(68.0)
        assert len(field.polygons) >= 10
        # local->world: b along the slope, n along the inward normal
        t = math.radians(68.0)
        ox, oy, oz = field.origin
        wx, wy, wz = field.local_to_world(0.0, 10.0, 0.0)
        assert wy == pytest.approx(oy + 10.0 * math.cos(t))
        assert wz == pytest.approx(oz + 10.0 * math.sin(t))
        assert state.report.status is not Status.FAIL

    def test_solid_bands_preserved(self):
        """Top edge band (phone rest) and root band stay uncut."""
        from artifact_forge_ng.pipeline import run_pre_cad

        state = run_pre_cad(EXAMPLES / "phone_stand_voronoi_back.yaml", False)
        field = [f for f in state.form.fields if f.pattern == "voronoi"][0]
        rest_len = state.form.params["rest_len"]
        bs = [p[1] for poly in field.polygons for p in poly]
        assert min(bs) >= 12.0  # root band
        assert max(bs) <= rest_len - 14.0  # top band

    def test_bio_bowed_back_rejects_field_honestly(self):
        """The biomorphic bow curves the back — a flat field canvas does
        not exist and the modifier FAILS loudly, never cuts garbage."""
        def mutate(data):
            data["style"] = {
                "surface": "biomorphic_utility_part", "organicity": 0.6,
            }

        _, findings = build_form_with_modifiers(
            path=EXAMPLES / "phone_stand_voronoi_back.yaml", mutate=mutate
        )
        fails = [f for f in findings if f.status is Status.FAIL]
        assert fails and "no usable window" in fails[0].message
