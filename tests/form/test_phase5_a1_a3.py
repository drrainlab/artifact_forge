"""Tier-1 (no CAD) for adapter_plate_v1, cable_comb_v1, zip_tie_anchor_v1:
golden validates, exact IR measurements, and one negative per archetype."""

from pathlib import Path

import pytest

from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.cli import run_validate
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form import silhouette  # noqa: F401  (import sanity)
from artifact_forge_ng.form.checks_slots import (
    check_slot_throat_retention,
    check_slots_open_topped,
    check_teeth_count_matches,
)
from artifact_forge_ng.form.checks_tunnel import check_tunnel_fits_tie
from artifact_forge_ng.form.profiles_comb import CombParams, build_cable_comb_profile
from artifact_forge_ng.form.profiles_omega import OmegaParams, build_omega_profile
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.pipeline import PipelineFailure, run_pre_cad
from artifact_forge_ng.product.instance import ProductInstance
from artifact_forge_ng.product.resolve import resolve_params

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.mark.parametrize(
    "example",
    ["adapter_plate_router_mount", "desk_comb_5x4mm", "zip_anchor_48_screw"],
)
def test_examples_validate_clean(example):
    out = run_validate(EXAMPLES / f"{example}.yaml", strict_flag=None)
    assert out["status"] == "pass"
    assert out["capability"]["unsupported_features"] == []


class TestAdapterPlate:
    def test_min_web_gate(self):
        """Two M4 holes 8mm apart on a small plate must fail strict."""
        catalog = load_catalog()
        inst = load_instance(EXAMPLES / "adapter_plate_router_mount.yaml")
        data = inst.model_dump(by_alias=True)
        data["params"]["a_spacing"] = "8mm"
        data["params"]["bore_d"] = "0mm"
        data["params"]["b_kind"] = "none"
        data["id"] = "tight"
        bad = ProductInstance.model_validate(data)
        archetype = catalog.archetypes[bad.archetype_id]
        resolved = resolve_params(archetype, bad)
        from artifact_forge_ng.archetypes import builder_for
        from artifact_forge_ng.form.checks_holes import check_min_web_between_holes

        form = builder_for(archetype)(resolved, archetype, bad)
        assert check_min_web_between_holes(form).status is Status.FAIL

    def test_pattern_b_none_means_no_b_holes(self):
        catalog = load_catalog()
        inst = load_instance(EXAMPLES / "adapter_plate_router_mount.yaml")
        data = inst.model_dump(by_alias=True)
        data["params"]["b_kind"] = "none"
        inst = ProductInstance.model_validate(data)
        archetype = catalog.archetypes[inst.archetype_id]
        resolved = resolve_params(archetype, inst)
        from artifact_forge_ng.archetypes import builder_for

        form = builder_for(archetype)(resolved, archetype, inst)
        assert len(form.holes) == 2  # a-pattern only
        assert form.bores and form.bores[0].d == pytest.approx(12.0)


def comb(cable_d=4.0, throat_w=None, slot_count=5):
    return CombParams(
        cable_d=cable_d,
        slot_count=slot_count,
        clearance=0.3,
        wall=3.0,
        throat_w=throat_w if throat_w is not None else cable_d * 0.7,
        pitch=cable_d + 2 * 0.3 + 2 * 3.0 + 1,
        base_h=6.0,
        end_margin=5.0,
    )


class TestCableComb:
    @pytest.mark.parametrize("cable_d", [2.0, 4.0, 8.0])
    def test_throat_exact_across_range(self, cable_d):
        from artifact_forge_ng.form.part import PartForm

        profile, frame = build_cable_comb_profile(comb(cable_d), MOLDED_UTILITY_PART)
        form = PartForm(
            name="t", params={"cable_d": cable_d}, frame=frame,
            section=profile, width=12.0, style=MOLDED_UTILITY_PART,
        )
        assert check_slot_throat_retention(form).status is Status.PASS
        assert check_slots_open_topped(form).status is Status.PASS
        assert check_teeth_count_matches(form).status is Status.PASS
        # exact throat measurement
        from artifact_forge_ng.form.section import LineSeg

        walls = [
            s for s in profile.outer.tagged("slot_0")
            if isinstance(s, LineSeg) and "throat" in s.tags
        ]
        us = sorted(s.a.u for s in walls)
        assert us[-1] - us[0] == pytest.approx(cable_d * 0.7, abs=1e-9)

    def test_negative_wide_throat_fails_retention(self):
        from artifact_forge_ng.form.part import PartForm

        p = comb(4.0, throat_w=4.4)  # wider than the cable — no retention
        profile, frame = build_cable_comb_profile(p, MOLDED_UTILITY_PART)
        form = PartForm(
            name="t", params={"cable_d": 4.0}, frame=frame,
            section=profile, width=12.0, style=MOLDED_UTILITY_PART,
        )
        assert check_slot_throat_retention(form).status is Status.FAIL

    def test_yaml_clamps_throat(self):
        """A requested throat wider than 0.9*cable_d clamps at resolve."""
        catalog = load_catalog()
        inst = load_instance(EXAMPLES / "desk_comb_5x4mm.yaml")
        data = inst.model_dump(by_alias=True)
        data["params"]["throat_w"] = "5mm"  # > 0.9 * 4mm
        inst = ProductInstance.model_validate(data)
        archetype = catalog.archetypes[inst.archetype_id]
        resolved = resolve_params(archetype, inst)
        assert resolved.context["throat_w"] == pytest.approx(3.6)


class TestZipTieAnchor:
    def test_tunnel_exact(self):
        from artifact_forge_ng.form.part import PartForm

        p = OmegaParams(tie_w=4.8, tie_t=1.6, clearance=0.4, wall=2.4,
                        flange_w=8.0, base_t=2.4)
        profile, frame = build_omega_profile(p, MOLDED_UTILITY_PART)
        assert frame["tunnel_w"] == pytest.approx(5.6)
        assert frame["tunnel_h"] == pytest.approx(2.4)
        form = PartForm(
            name="t", params={"tie_w": 4.8, "tie_t": 1.6}, frame=frame,
            section=profile, width=10.0, style=MOLDED_UTILITY_PART,
        )
        assert check_tunnel_fits_tie(form).status is Status.PASS

    def test_negative_undersized_tunnel_fails(self):
        from artifact_forge_ng.form.part import PartForm

        p = OmegaParams(tie_w=4.8, tie_t=1.6, clearance=0.4, wall=2.4,
                        flange_w=8.0, base_t=2.4)
        profile, frame = build_omega_profile(p, MOLDED_UTILITY_PART)
        form = PartForm(
            name="t", params={"tie_w": 8.0, "tie_t": 1.6}, frame=frame,
            section=profile, width=10.0, style=MOLDED_UTILITY_PART,
        )
        assert check_tunnel_fits_tie(form).status is Status.FAIL

    def test_adhesive_variant_has_no_holes(self):
        catalog = load_catalog()
        inst = load_instance(EXAMPLES / "zip_anchor_48_screw.yaml")
        data = inst.model_dump(by_alias=True)
        data["params"]["mount"] = "adhesive"
        data["requested_features"] = ["tie_tunnel", "surface_mount_base"]
        inst = ProductInstance.model_validate(data)
        archetype = catalog.archetypes[inst.archetype_id]
        resolved = resolve_params(archetype, inst)
        from artifact_forge_ng.archetypes import builder_for

        form = builder_for(archetype)(resolved, archetype, inst)
        assert form.holes == []


def test_unimplemented_form_check_is_engine_gap_not_silence(monkeypatch):
    """Regression for the wiring gap this phase caught live: a declared
    check with no implementation must WARN (and block built-status), never
    silently pass."""
    from artifact_forge_ng.core.findings import Level
    from artifact_forge_ng.form.validators import validate_form
    from artifact_forge_ng.archetypes import builder_for
    from artifact_forge_ng.validators.probes import KNOWN_CHECKS, CheckDecl

    name = "form.future_check_without_impl"
    monkeypatch.setitem(
        KNOWN_CHECKS, name, CheckDecl(name=name, level=Level.FORM, description="t")
    )
    catalog = load_catalog()
    inst = load_instance(EXAMPLES / "desk_comb_5x4mm.yaml")
    archetype = catalog.archetypes[inst.archetype_id]
    resolved = resolve_params(archetype, inst)
    form = builder_for(archetype)(resolved, archetype, inst)
    findings = validate_form(form, archetype, extra_checks=(name,))
    gap = [f for f in findings if f.check == name]
    assert gap and gap[0].status is Status.WARN
    assert "no implementation" in gap[0].message
    assert gap[0].level is Level.FORM
