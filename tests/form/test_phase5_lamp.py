"""Tier-1 for the lamp pair: socket cup presets/axis-clearance and bracket
channel math."""

from pathlib import Path

import pytest

from artifact_forge_ng.archetypes import builder_for
from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.cli import run_validate
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_channel import check_channel_inside_walls
from artifact_forge_ng.form.checks_revolve import check_revolve_profile_clear_of_axis
from artifact_forge_ng.form.profiles_cup import CupParams, build_cup_profile, cup_frame
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.instance import ProductInstance
from artifact_forge_ng.product.resolve import resolve_params

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.mark.parametrize("example", ["socket_cup_e27", "shelf_lamp_bracket"])
def test_examples_validate_clean(example):
    out = run_validate(EXAMPLES / f"{example}.yaml", strict_flag=None)
    assert out["status"] == "pass"


def _cup_form(**param_overrides):
    catalog = load_catalog()
    inst = load_instance(EXAMPLES / "socket_cup_e27.yaml")
    if param_overrides:
        data = inst.model_dump(by_alias=True)
        data["params"].update(param_overrides)
        inst = ProductInstance.model_validate(data)
    archetype = catalog.archetypes[inst.archetype_id]
    resolved = resolve_params(archetype, inst)
    return builder_for(archetype)(resolved, archetype, inst)


class TestSocketCup:
    def test_e27_preset_math(self):
        form = _cup_form()
        # housing 40.0 + 2 * 0.3 fit clearance
        assert form.params["inner_d"] == pytest.approx(40.6)
        assert form.params["depth"] == pytest.approx(32.0)
        assert form.kind == "profile_revolve"

    def test_gu10_preset(self):
        form = _cup_form(socket="gu10")
        assert form.params["inner_d"] == pytest.approx(35.6)

    def test_explicit_inner_d_overrides_preset(self):
        form = _cup_form(inner_d="42mm")
        assert form.params["inner_d"] == pytest.approx(42.0)

    def test_axis_clearance_exact(self):
        form = _cup_form()
        lo, _ = form.section.outer.bbox()
        assert lo.u == pytest.approx(4.0, abs=1e-6)  # exit_d 8 -> exit_r 4
        assert check_revolve_profile_clear_of_axis(form).status is Status.PASS

    def test_negative_no_exit_hole_rejected(self):
        with pytest.raises(ValueError, match="cable hole"):
            cup_frame(CupParams(inner_d=40, depth=30, wall=3, base_t=4, exit_d=0.5))

    def test_negative_exit_swallows_base(self):
        with pytest.raises(ValueError, match="base floor"):
            build_cup_profile(
                CupParams(inner_d=20, depth=20, wall=3, base_t=4, exit_d=18),
                MOLDED_UTILITY_PART,
            )


def _bracket_form(**param_overrides):
    catalog = load_catalog()
    inst = load_instance(EXAMPLES / "shelf_lamp_bracket.yaml")
    if param_overrides:
        data = inst.model_dump(by_alias=True)
        data["params"].update(param_overrides)
        inst = ProductInstance.model_validate(data)
    archetype = catalog.archetypes[inst.archetype_id]
    resolved = resolve_params(archetype, inst)
    return builder_for(archetype)(resolved, archetype, inst)


class TestLampBracket:
    def test_channel_l_path_consistent(self):
        form = _bracket_form()
        f = form.frame
        entry, run = form.bores
        assert entry.axis == "Z" and run.axis == "Y"
        # the two bores genuinely intersect at the elbow
        assert entry.span[0] < f["channel_z"] < entry.span[1] or entry.span[0] == f["channel_z"]
        assert run.span[0] == pytest.approx(f["channel_entry_u"])
        assert run.span[1] == pytest.approx(form.params["arm_len"])
        assert check_channel_inside_walls(form).status is Status.PASS

    def test_channel_clamped_by_yaml(self):
        form = _bracket_form(channel_d="30mm")  # way past min(arm)-4 = 18
        assert form.params["channel_d"] == pytest.approx(18.0)
        assert check_channel_inside_walls(form).status is Status.PASS

    def test_negative_forced_fat_channel_fails_ir(self):
        form = _bracket_form()
        form.params["channel_d"] = 19.5  # margin 1.25 < 2.0 floor
        assert check_channel_inside_walls(form).status is Status.FAIL

    def test_arm_tip_datum_matches_channel_exit(self):
        form = _bracket_form()
        at = form.datums["arm_tip"]["at"]
        assert at[1] == pytest.approx(form.params["arm_len"])
        assert at[2] == pytest.approx(form.frame["channel_z"])

    def test_screws_beside_arm(self):
        form = _bracket_form()
        for hole in form.holes:
            x = hole.at[0]
            assert x < 0 or x > form.width
