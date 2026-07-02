"""YAML patch repair: absolute/expr/delta application, purity, locked-role
rejection, illegal-result rejection, and the deterministic rule table."""

from pathlib import Path

import pytest

from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.core.findings import Finding, Level, Status, ValidationReport
from artifact_forge_ng.product.resolve import resolve_params
from artifact_forge_ng.repair.patch import (
    ModifierAdd,
    ModifierOps,
    Patch,
    PatchError,
    apply_patch,
)
from artifact_forge_ng.repair.rules import RepairLedger, SEMANTIC_RULES, propose_repairs

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture(scope="module")
def env():
    catalog = load_catalog()
    instance = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
    archetype = catalog.archetypes[instance.archetype_id]
    return catalog, instance, archetype


def make_patch(**kwargs) -> Patch:
    return Patch(schema="patch/v1", **kwargs)


class TestApplyPatch:
    def test_absolute_set(self, env):
        catalog, instance, archetype = env
        patched = apply_patch(
            instance, make_patch(params={"mouth_gap": "12mm"}), archetype, catalog
        )
        assert patched.params["mouth_gap"] == "12mm"

    def test_delta_applies_to_resolved_value(self, env):
        catalog, instance, archetype = env
        patched = apply_patch(
            instance, make_patch(params={"lower_lip_len": "+3mm"}), archetype, catalog
        )
        assert patched.params["lower_lip_len"] == "18mm"  # 15 + 3

    def test_expr_stays_parametric(self, env):
        catalog, instance, archetype = env
        patched = apply_patch(
            instance,
            make_patch(params={"mouth_gap": "expr(bundle_d * 0.5)"}),
            archetype,
            catalog,
        )
        assert patched.params["mouth_gap"] == "expr(bundle_d * 0.5)"
        resolved = resolve_params(archetype, patched)
        assert resolved.context["mouth_gap"] == pytest.approx(10.0)

    def test_purity_input_untouched(self, env):
        catalog, instance, archetype = env
        before = instance.model_dump()
        apply_patch(instance, make_patch(params={"mouth_gap": "9mm"}), archetype, catalog)
        assert instance.model_dump() == before

    def test_unknown_param_rejected(self, env):
        catalog, instance, archetype = env
        with pytest.raises(PatchError, match="unknown parameter"):
            apply_patch(instance, make_patch(params={"warp": "1mm"}), archetype, catalog)

    def test_illegal_modifier_add_rejected(self, env):
        catalog, instance, archetype = env
        bad = make_patch(
            modifiers=ModifierOps(
                add=[ModifierAdd(id="add_hex_perforation", target="snap_root")]
            )
        )
        with pytest.raises(PatchError, match="illegal instance"):
            apply_patch(instance, bad, archetype, catalog)

    def test_modifier_remove(self, env):
        catalog, instance, archetype = env
        patched = apply_patch(
            instance,
            make_patch(modifiers=ModifierOps(remove=["add_hex_perforation"])),
            archetype,
            catalog,
        )
        assert all(m.id != "add_hex_perforation" for m in patched.modifiers)


class TestRules:
    def test_min_wall_rule_fires_and_clears(self, env):
        catalog, instance, archetype = env
        report = ValidationReport(
            findings=[
                Finding(
                    check="manufacturing.min_wall",
                    status=Status.FAIL,
                    level=Level.MANUFACTURING,
                    message="too thin",
                )
            ]
        )
        patches = propose_repairs(report, instance)
        assert len(patches) == 1
        patched = apply_patch(instance, patches[0], archetype, catalog)
        resolved = resolve_params(archetype, patched)
        # wall = printer_min_wall * 1.5; thinnest = wall * 0.7 >= floor
        assert resolved.context["wall"] * 0.7 >= resolved.context["printer_min_wall"] - 1e-6

    def test_asymmetry_rule(self, env):
        catalog, instance, archetype = env
        report = ValidationReport(
            findings=[
                Finding(
                    check="form.lower_lip_longer_than_upper",
                    status=Status.FAIL,
                    level=Level.FORM,
                    message="symmetric",
                    critical=True,
                )
            ]
        )
        patches = propose_repairs(report, instance)
        assert patches and "lower_lip_len" in patches[0].params
        patched = apply_patch(instance, patches[0], archetype, catalog)
        resolved = resolve_params(archetype, patched)
        assert resolved.context["lower_lip_len"] > resolved.context["upper_lip_len"] * 1.5

    def test_semantic_falls_out(self, env):
        catalog, instance, archetype = env
        patch = SEMANTIC_RULES["falls_out"](instance)
        patched = apply_patch(instance, patch, archetype, catalog)
        resolved = resolve_params(archetype, patched)
        assert resolved.context["mouth_gap"] == pytest.approx(10.0)  # 20 * 0.5
        assert resolved.context["lower_lip_len"] == pytest.approx(18.0)

    def test_no_rules_for_passing_report(self, env):
        _, instance, _ = env
        assert propose_repairs(ValidationReport(), instance) == []


class TestLedger:
    def test_survivor_becomes_engine_gap(self):
        ledger = RepairLedger()
        ledger.record_attempt("topology.cavity_open")
        assert ledger.survivors(["topology.cavity_open"]) == []
        ledger.record_attempt("topology.cavity_open")
        gaps = ledger.survivors(["topology.cavity_open"])
        assert gaps and gaps[0]["survived_repairs"] == 2

    def test_cleared_finding_is_not_a_gap(self):
        ledger = RepairLedger()
        ledger.record_attempt("x")
        ledger.record_attempt("x")
        assert ledger.survivors([]) == []
