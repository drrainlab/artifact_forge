"""Tier-1 for phone_stand_v1 — slot trigonometry and the stability gate."""

import math
from pathlib import Path

import pytest

from artifact_forge_ng.archetypes import builder_for
from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.cli import run_validate
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_stability import (
    check_device_slot_fits,
    check_stability_footprint,
)
from artifact_forge_ng.product.instance import ProductInstance
from artifact_forge_ng.product.resolve import resolve_params

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


def _form(**param_overrides):
    catalog = load_catalog()
    inst = load_instance(EXAMPLES / "phone_stand_std.yaml")
    if param_overrides:
        data = inst.model_dump(by_alias=True)
        data["params"].update(param_overrides)
        inst = ProductInstance.model_validate(data)
    archetype = catalog.archetypes[inst.archetype_id]
    resolved = resolve_params(archetype, inst)
    assert resolved.ok, [f.message for f in resolved.findings if f.status is Status.FAIL]
    return builder_for(archetype)(resolved, archetype, inst)


def test_example_validates():
    out = run_validate(EXAMPLES / "phone_stand_std.yaml", strict_flag=None)
    assert out["status"] == "pass"


@pytest.mark.parametrize("tilt", [45.0, 68.0, 80.0])
def test_slot_width_exact_trig(tilt):
    form = _form(tilt_deg=f"{tilt}deg")
    expected = 11.0 / math.sin(math.radians(tilt)) + 2 * 0.5
    assert form.frame["slot_w"] == pytest.approx(expected, abs=1e-9)
    assert check_device_slot_fits(form).status is Status.PASS


def test_default_stand_is_stable():
    form = _form()
    finding = check_stability_footprint(form)
    assert finding.status is Status.PASS, finding.message


def test_negative_tipping_config_fails():
    """Low tilt + long rest + short base: device COM lands behind the base."""
    form = _form(
        tilt_deg="45deg", rest_len="140mm", base_depth="60mm", device_w="55mm"
    )
    finding = check_stability_footprint(form)
    assert finding.status is Status.FAIL
    assert "COM" in finding.message


def test_cutout_respects_rest_root():
    from artifact_forge_ng.form.checks_cuts import check_cuts_respect_keepouts

    form = _form()
    assert form.cutboxes, "charging cutout requested"
    assert check_cuts_respect_keepouts(form).status is Status.PASS
    # widen the cutout into the rest root -> keepout violation
    from artifact_forge_ng.form.part import CutBoxFeature
    from artifact_forge_ng.form.regions import Box3

    bad = CutBoxFeature(
        "charging_cutout",
        Box3(
            form.cutboxes[0].box.x0, -1.0, form.cutboxes[0].box.z0,
            form.cutboxes[0].box.x1, form.frame["rest_foot_end"] + 1.0,
            form.cutboxes[0].box.z1,
        ),
    )
    form.cutboxes = [bad]
    assert check_cuts_respect_keepouts(form).status is Status.FAIL


def test_no_cutout_variant():
    form = _form(charging_cutout=False)
    assert form.cutboxes == []
