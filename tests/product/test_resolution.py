"""Parameter resolution: defaults, expr bounds, clamping order, derived,
constraints, environment injection — the v1 resolve_model contract on the
NG value grammar."""

from pathlib import Path

import pytest

from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.product.instance import ProductInstance
from artifact_forge_ng.product.resolve import resolve_params

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture(scope="module")
def archetype():
    return load_catalog().archetypes["underdesk_cable_clip_v2_molded"]


def make_instance(params: dict, **extra) -> ProductInstance:
    return ProductInstance.model_validate(
        {
            "schema": "product/v1",
            "id": "t",
            "archetype": "underdesk_cable_clip_v2_molded",
            "params": params,
            **extra,
        }
    )


def test_golden_example_resolves_clean(archetype):
    inst = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
    res = resolve_params(archetype, inst)
    assert res.ok
    assert res.context["bundle_d"] == 20.0
    assert res.context["mouth_gap"] == 10.0
    assert res.context["lower_lip_len"] == 15.0
    assert res.context["upper_lip_len"] == 6.0
    assert res.choices["screw"] == "M4"


def test_defaults_fire_only_when_unset(archetype):
    res = resolve_params(archetype, make_instance({"bundle_d": "30mm"}))
    assert res.context["bundle_d"] == 30.0
    assert res.context["wall"] == 3.5  # archetype default
    assert res.context["mouth_gap"] == 10.0


def test_expr_max_clamps_mouth_gap(archetype):
    res = resolve_params(
        archetype, make_instance({"bundle_d": "10mm", "mouth_gap": "9mm"})
    )
    # max = bundle_d * 0.7 = 7.0
    assert res.context["mouth_gap"] == pytest.approx(7.0)
    assert any(f.status is Status.WARN and "mouth_gap" in f.check for f in res.findings)


def test_asymmetry_clamp_lower_lip(archetype):
    res = resolve_params(
        archetype,
        make_instance({"upper_lip_len": "8mm", "lower_lip_len": "9mm"}),
    )
    # min = upper * 1.6 = 12.8 — the load-bearing asymmetric-hook identity
    assert res.context["lower_lip_len"] == pytest.approx(12.8)


def test_declaration_order_sees_clamped_value(archetype):
    # upper_lip_len clamps to 12 (max); lower's min uses the CLAMPED value.
    res = resolve_params(
        archetype,
        make_instance({"upper_lip_len": "50mm", "lower_lip_len": "10mm"}),
    )
    assert res.context["upper_lip_len"] == 12.0
    assert res.context["lower_lip_len"] == pytest.approx(12.0 * 1.6)


def test_instance_expr_param(archetype):
    res = resolve_params(
        archetype,
        make_instance({"bundle_d": "20mm", "mouth_gap": "expr(bundle_d * 0.5)"}),
    )
    assert res.context["mouth_gap"] == pytest.approx(10.0)


def test_derived_computed_last(archetype):
    res = resolve_params(archetype, make_instance({"bundle_d": "20mm"}))
    assert res.context["cavity_r"] == pytest.approx((20.0 + 2 * 0.8) / 2)
    assert res.context["outer_r"] == pytest.approx(res.context["cavity_r"] + 3.5)


def test_environment_injection(archetype):
    inst = make_instance({}, manufacturing={"nozzle": "0.6mm"})
    res = resolve_params(archetype, inst)
    assert res.context["printer_min_wall"] == pytest.approx(1.2)
    inst2 = make_instance({}, manufacturing={"nozzle": "0.8mm"})
    res2 = resolve_params(archetype, inst2)
    assert res2.context["printer_min_wall"] == pytest.approx(1.6)


def test_unknown_param_fails(archetype):
    res = resolve_params(archetype, make_instance({"warp_factor": 9}))
    assert not res.ok
    assert any("warp_factor" in f.message for f in res.findings)


def test_bad_choice_fails(archetype):
    res = resolve_params(archetype, make_instance({"screw": "M99"}))
    assert not res.ok


def test_constraints_pass_on_defaults(archetype):
    res = resolve_params(archetype, make_instance({}))
    constraint_findings = [f for f in res.findings if f.check.startswith("constraint:")]
    assert constraint_findings
    assert all(f.status is Status.PASS for f in constraint_findings)
