"""Bio-1 split branch clamp assembly, tier-1: the compression_gap_joint is
a checked contract — the golden example passes, a branch_d desync between
the halves fails loudly, a mis-declared gap fails, and mismatched bolt
grids die in the screw joint. All IR-level, no CAD."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.pipeline import run_assembly_validate
from artifact_forge_ng.pipeline import PipelineFailure

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
CLAMP = EXAMPLES / "branch_lamp_clamp_60.yaml"


def _mutated(tmp_path, mutate):
    doc = yaml.safe_load(CLAMP.read_text())
    mutate(doc)
    p = tmp_path / "asm.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


def _joint(out, check):
    return next(j for j in out["joints"] if j["check"] == check)


def test_golden_clamp_assembly_validates():
    out = run_assembly_validate(CLAMP, None)
    assert out["status"] == "pass"
    screw = _joint(out, "assembly.screw_joint_ir")
    gap = _joint(out, "assembly.clamp_gap_ir")
    assert screw["status"] == "pass"
    assert gap["status"] == "pass"
    # the measured mate separation IS the declared gap
    assert gap["measured"] == pytest.approx(3.0, abs=0.15)
    poses = {p["part"] for p in out["assembly_pose"]}
    assert poses == {"lower", "upper"}
    # the upper is posed with no flip — it is modeled mating-face-down
    upper_pose = next(p for p in out["assembly_pose"] if p["part"] == "upper")
    assert upper_pose["rotate"] == [0.0, 0.0, 0.0]


def test_branch_d_desync_between_halves_fails(tmp_path):
    """Break the shared chain: 60 mm lower vs 80 mm upper — two saddles
    that will never form one branch circle."""
    bad = _mutated(
        tmp_path,
        lambda d: (d["shared"].pop("nominal_branch_d"),
                   d["parts"][0]["product"]["params"].update(
                       nominal_branch_d="60mm"),
                   d["parts"][1]["product"]["params"].update(
                       nominal_branch_d="80mm")),
    )
    out = run_assembly_validate(bad, False)
    assert out["status"] == "fail"
    gap = _joint(out, "assembly.clamp_gap_ir")
    assert gap["status"] == "fail"
    assert "desync" in gap["message"]


def test_desync_is_a_strict_failure(tmp_path):
    bad = _mutated(
        tmp_path,
        lambda d: (d["shared"].pop("nominal_branch_d"),
                   d["parts"][0]["product"]["params"].update(
                       nominal_branch_d="60mm"),
                   d["parts"][1]["product"]["params"].update(
                       nominal_branch_d="80mm")),
    )
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_validate(bad, None)
    assert exc_info.value.code == 4


def test_misdeclared_joint_gap_fails(tmp_path):
    """The joint says 5 mm, the halves were built for 3 — the posed mate
    planes contradict the declaration."""
    bad = _mutated(tmp_path,
                   lambda d: d["joints"][1]["params"].update(gap="5mm"))
    out = run_assembly_validate(bad, False)
    gap = _joint(out, "assembly.clamp_gap_ir")
    assert gap["status"] == "fail"
    assert "declared gap" in gap["message"]


def test_gap_below_the_compression_floor_fails(tmp_path):
    def mutate(d):
        d["shared"]["compression_gap"] = "1.5mm"
        d["joints"][1]["params"]["gap"] = "1mm"

    bad = _mutated(tmp_path, mutate)
    out = run_assembly_validate(bad, False)
    gap = _joint(out, "assembly.clamp_gap_ir")
    assert gap["status"] == "fail"
    assert "never squeeze" in gap["message"]


def test_mismatched_bolt_grids_fail_the_screw_joint(tmp_path):
    """Different clamp_w per half shifts bolt_dx — the four bolts no longer
    coincide in the pose."""
    bad = _mutated(
        tmp_path,
        lambda d: (d["shared"].pop("clamp_w"),
                   d["parts"][0]["product"]["params"].update(clamp_w="40mm"),
                   d["parts"][1]["product"]["params"].update(clamp_w="64mm")),
    )
    out = run_assembly_validate(bad, False)
    screw = _joint(out, "assembly.screw_joint_ir")
    assert screw["status"] == "fail"
