"""Bio-organic SurfaceStyle: sliders compile into controlled form passes;
engineering is untouchable by construction; determinism holds."""

from pathlib import Path

import pytest

from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.cli import run_validate
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_stability import check_device_slot_fits
from artifact_forge_ng.form.section import ArcSeg, LineSeg
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART, resolve_style
from artifact_forge_ng.pipeline import run_pre_cad
from artifact_forge_ng.product.instance import ProductInstance

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
BIO = EXAMPLES / "phone_stand_bio.yaml"
STD = EXAMPLES / "phone_stand_std.yaml"


def test_bio_example_validates_clean():
    out = run_validate(BIO, strict_flag=None)
    assert out["status"] == "pass"


class TestResolveStyle:
    def _style(self, style_block):
        catalog = load_catalog()
        inst = load_instance(STD)
        data = inst.model_dump(by_alias=True)
        data["style"] = style_block
        inst = ProductInstance.model_validate(data)
        return resolve_style(inst, catalog.archetypes[inst.archetype_id])

    def test_default_is_plain_molded(self):
        style = self._style({})
        assert style.name == "molded_utility_part"
        assert style.bow_amplitude == 0.0

    def test_softness_scales_decorative_radii_not_contact(self):
        style = self._style(
            {"surface": "biomorphic_utility_part", "softness": 1.0, "organicity": 0}
        )
        assert style.external_edge_r > MOLDED_UTILITY_PART.external_edge_r
        assert style.root_blend_r > MOLDED_UTILITY_PART.root_blend_r
        # contact radius is engineering, not style
        assert style.contact_r == MOLDED_UTILITY_PART.contact_r

    def test_sliders_clamped_to_unit_range(self):
        style = self._style(
            {"surface": "biomorphic_utility_part", "organicity": 7.0}
        )
        assert style.bow_amplitude == pytest.approx(0.035)

    def test_unknown_surface_rejected(self):
        with pytest.raises(ValueError, match="unknown style.surface"):
            self._style({"surface": "vibes_based_organic"})


class TestBioStand:
    def test_back_face_bowed_veins_present(self):
        state = run_pre_cad(BIO, False)
        form = state.form
        backs = form.section.outer.tagged("rest_back")
        assert any(isinstance(s, ArcSeg) for s in backs)  # the organic bow
        assert len(form.ribs) == 5  # vein_rhythm 0.45 -> 2 + 0.45*6 ~ 5
        assert state.report.status is not Status.FAIL

    def test_engineering_untouched_by_style(self):
        bio = run_pre_cad(BIO, False).form
        std = run_pre_cad(STD, False).form
        # exact same slot trigonometry and footprint
        assert bio.frame["slot_w"] == pytest.approx(std.frame["slot_w"])
        assert bio.frame["u_rest"] == pytest.approx(std.frame["u_rest"])
        assert check_device_slot_fits(bio).status is Status.PASS
        # the flat print base stayed a straight line
        base = bio.section.outer.tagged("base_bottom")
        assert all(isinstance(s, LineSeg) for s in base)

    def test_deterministic_same_seed(self):
        a = run_pre_cad(BIO, False).form
        b = run_pre_cad(BIO, False).form
        assert [
            (s.a.u, s.a.v) for s in a.section.outer.segments
        ] == [(s.a.u, s.a.v) for s in b.section.outer.segments]
        assert [r.box for r in a.ribs] == [r.box for r in b.ribs]

    def test_std_stand_regression_unchanged(self):
        """The plain example must be byte-for-byte unaffected by the style
        machinery — no bows, no veins."""
        form = run_pre_cad(STD, False).form
        assert form.ribs == []
        backs = form.section.outer.tagged("rest_back")
        assert all(isinstance(s, LineSeg) for s in backs)

    def test_profile_fully_smooth_after_bow(self):
        """Bowed arcs meet their neighbours through proper fillets — the
        arc-arc/containment fix, pinned."""
        state = run_pre_cad(BIO, False)
        assert state.report.passed("form.profile_smooth")
        assert state.report.passed("form.contact_edges_rounded")
