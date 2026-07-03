"""Fit interfaces (lid_seat + press_fit_pin_pair), tier-1: dimension
chains and interference are verified BEFORE any CAD, with honest
negatives."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.pipeline import run_assembly_validate
from artifact_forge_ng.pipeline import PipelineFailure

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
BOX = EXAMPLES / "esp32_box_with_lid.yaml"


def _mutated(tmp_path, mutate):
    doc = yaml.safe_load(BOX.read_text())
    mutate(doc)
    p = tmp_path / "asm.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


def test_box_with_lid_validates_without_cad():
    out = run_assembly_validate(BOX, None)
    assert out["status"] == "pass"
    checks = {j["check"]: j["status"] for j in out["joints"]}
    assert checks["assembly.lid_seat_ir"] == "pass"
    assert checks["assembly.screw_joint_ir"] == "pass"
    assert checks["assembly.press_fit_ir"] == "pass"


def test_tight_plug_fails_the_chain(tmp_path):
    """seat_clearance below the joint's declared clearance = a lid that
    will not drop in — caught by the dimension chain, no CAD."""
    bad = _mutated(
        tmp_path,
        lambda d: d["parts"][1]["product"]["params"].update(
            seat_clearance="0.05mm"
        ),
    )
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_validate(bad, None)
    assert exc_info.value.code == 4


def test_loose_pin_fails_interference(tmp_path):
    """pin_d equal to the receiving bore = zero interference = the pin
    falls out. The declared interference is a checked contract."""
    bad = _mutated(
        tmp_path,
        lambda d: d["parts"][1]["product"]["params"].update(pin_d="4mm"),
    )
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_validate(bad, None)
    assert exc_info.value.code == 4


def test_overlong_pin_never_seats(tmp_path):
    bad = _mutated(
        tmp_path,
        lambda d: d["parts"][1]["product"]["params"].update(pin_len="6mm"),
    )
    with pytest.raises(PipelineFailure):
        run_assembly_validate(bad, None)
