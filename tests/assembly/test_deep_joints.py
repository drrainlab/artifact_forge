"""Butt-split and snap joints, tier-1: section identity, interference and
flexure strain are checked contracts with honest negatives."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.pipeline import run_assembly_validate
from artifact_forge_ng.pipeline import PipelineFailure

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


def _mutated(src, tmp_path, mutate):
    doc = yaml.safe_load((EXAMPLES / src).read_text())
    mutate(doc)
    p = tmp_path / "asm.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


def test_split_raceway_validates():
    out = run_assembly_validate(EXAMPLES / "raceway_400_split.yaml", None)
    assert out["status"] == "pass"
    checks = {j["check"]: j["status"] for j in out["joints"]}
    assert checks["assembly.butt_pin_ir"] == "pass"


def test_split_halves_must_share_one_section(tmp_path):
    """Different inner_w on the halves = different profiles — a butt joint
    cannot align them and says so before CAD."""
    bad = _mutated(
        "raceway_400_split.yaml", tmp_path,
        lambda d: (d["shared"].pop("inner_w"),
                   d["parts"][0]["product"]["params"].update(inner_w="24mm"),
                   d["parts"][1]["product"]["params"].update(inner_w="30mm")),
    )
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_validate(bad, None)
    assert exc_info.value.code == 4


def test_snap_lid_validates_with_strain_note():
    out = run_assembly_validate(EXAMPLES / "esp32_box_snap_lid.yaml", None)
    assert out["status"] == "pass"
    snap = next(j for j in out["joints"] if j["check"] == "assembly.snap_joint_ir")
    assert snap["status"] == "pass"
    assert 0.0 < snap["measured"] <= 0.05  # the strain is a real number


def test_overstrained_hook_fails(tmp_path):
    """A short stiff beam with a deep lip strains past the plastic limit —
    the hook snaps OFF, and the joint says so before anything prints."""
    bad = _mutated(
        "esp32_box_snap_lid.yaml", tmp_path,
        lambda d: d["shared"].update(hook_len="7mm"),
    )
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_validate(bad, None)
    assert exc_info.value.code == 4


def test_misplaced_window_fails(tmp_path):
    """Break the shared chain: a lid with a longer hook than the box was
    told about puts the lip below the window."""
    bad = _mutated(
        "esp32_box_snap_lid.yaml", tmp_path,
        lambda d: (d["shared"].pop("hook_len"),
                   d["parts"][0]["product"]["params"].update(hook_len="10mm"),
                   d["parts"][1]["product"]["params"].update(hook_len="13mm")),
    )
    with pytest.raises(PipelineFailure):
        run_assembly_validate(bad, None)
