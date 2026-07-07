"""Wave P2 mode scaffold: BodyFitSpec parsing/ranges, MODE_PROFILES as the
single source of mode truth, wearable→body_fit requirement, env injection,
and the resolve honesty fix (a formula default that cannot resolve is a
named FAIL, never a silent skip)."""

import pytest
from pydantic import ValidationError

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.product.archetype import ArchetypeSpec
from artifact_forge_ng.product.instance import BodyFitSpec, ProductInstance
from artifact_forge_ng.product.modes import MODE_PROFILES
from artifact_forge_ng.product.resolve import resolve_params


def make_instance(**extra) -> ProductInstance:
    return ProductInstance.model_validate(
        {
            "schema": "product/v1",
            "id": "t",
            "archetype": "underdesk_cable_clip_v2_molded",
            **extra,
        }
    )


BODY = {"region": "forearm", "circumference": "270mm", "length": "240mm"}


# -- BodyFitSpec ----------------------------------------------------------

def test_body_fit_parses_quantity_strings():
    fit = BodyFitSpec.model_validate(BODY)
    assert fit.circumference == 270.0
    assert fit.length == 240.0
    assert fit.clearance == 6.0  # default
    assert fit.strap_width == 25.0  # default


@pytest.mark.parametrize(
    "field,value",
    [
        ("circumference", "27mm"),   # the classic 10x typo
        ("circumference", "600mm"),
        ("length", "20mm"),
        ("clearance", "40mm"),
        ("strap_width", "5mm"),
    ],
)
def test_body_fit_rejects_inhuman_ranges(field, value):
    with pytest.raises(ValidationError, match="human range"):
        BodyFitSpec.model_validate({**BODY, field: value})


def test_env_context_names_and_d_eff():
    ctx = BodyFitSpec.model_validate(BODY).env_context()
    assert set(ctx) == {
        "body_circumference", "body_length", "body_clearance",
        "body_strap_width", "body_d_eff",
    }
    assert ctx["body_d_eff"] == pytest.approx(270.0 / 3.141592653589793)


# -- mode field -----------------------------------------------------------

def test_registry_is_the_mode_enum():
    assert set(MODE_PROFILES) >= {"engineering", "wearable"}
    with pytest.raises(ValidationError, match="unknown mode"):
        make_instance(mode="cinema")


def test_wearable_requires_body_fit():
    with pytest.raises(ValidationError, match="requires context: body_fit"):
        make_instance(mode="wearable")
    inst = make_instance(mode="wearable", body_fit=BODY)
    assert inst.body_fit is not None
    assert inst.mode == "wearable"


def test_engineering_default_needs_no_context():
    inst = make_instance()
    assert inst.mode == "engineering"
    assert inst.body_fit is None


# -- resolve injection + honesty fix --------------------------------------

def _archetype(params_yaml: dict) -> ArchetypeSpec:
    return ArchetypeSpec.model_validate(
        {
            "schema": "archetype/v1",
            "id": "cuffoid_test",
            "version": 1,
            "object_class": "wearable_cuff",
            "parameters": params_yaml,
            "form": {"type": "section_extrude", "section": "molded_side_hook",
                     "plane": "YZ", "width_axis": "X"},
            "validators": [],
        }
    )


def test_body_names_visible_to_formula_defaults():
    arch = _archetype(
        {"arm_c": {"type": "length", "default": "expr(body_circumference)",
                   "min": "150mm", "max": "450mm"}}
    )
    inst = make_instance(mode="wearable", body_fit=BODY)
    res = resolve_params(arch, inst)
    assert res.context["arm_c"] == 270.0


def test_unresolvable_formula_default_is_a_named_fail():
    arch = _archetype(
        {"arm_c": {"type": "length", "default": "expr(body_circumference)",
                   "min": "150mm", "max": "450mm"}}
    )
    res = resolve_params(arch, make_instance())  # no body_fit
    fails = [f for f in res.findings
             if f.check == "param:arm_c" and f.status is Status.FAIL]
    assert fails, "silent-skip honesty gap is back"
    assert "body_circumference" in fails[0].message
    assert "body_fit" in fails[0].message
    assert "arm_c" not in res.context


def test_mode_in_pipeline_summary():
    from artifact_forge_ng.pipeline import run_pre_cad
    from pathlib import Path

    golden = (Path(__file__).parents[2] / "catalog" / "examples"
              / "desk_cable_clip_20mm.yaml")
    state = run_pre_cad(golden, None)
    s = state.summary()
    assert s["mode"] == "engineering"
    assert "mode_tags" not in s  # engineering has no tags
