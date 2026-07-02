"""THE golden test: `forge validate` on the flagship example must pass
without CAD and print exactly the promised form_checks — and a strict run
against a broken instance must exit non-zero."""

from pathlib import Path

import pytest

from artifact_forge_ng.cli import PipelineFailure, run_validate

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = EXAMPLES / "desk_cable_clip_20mm.yaml"


def test_golden_validate_passes():
    out = run_validate(GOLDEN, strict_flag=None)
    checks = out["form_checks"]
    assert checks["mouth_gap"] == "10mm"
    assert checks["mouth_direction"] == "+Y"
    assert checks["lower_lip_len"] == "15mm"
    assert checks["upper_lip_len"] == "6mm"
    assert checks["lower_lip_ratio_ok"] is True
    assert checks["symmetric_c_ring"] is False
    assert checks["flange_above_cradle"] is True
    assert set(checks["regions_present"]) == {
        "flange",
        "screw_zones",
        "cable_contact",
        "snap_root",
        "lower_lip",
        "neck_weld",
        "perforation_safe_zone",
    }
    assert out["status"] == "pass"
    assert out["capability"]["buildable"] is True
    assert out["capability"]["unsupported_features"] == []


def test_strict_unsupported_feature_fails(tmp_path):
    text = GOLDEN.read_text().replace(
        "requested_features:", "requested_features:\n  - integrated_living_hinge"
    )
    bad = tmp_path / "bad.yaml"
    bad.write_text(text)
    with pytest.raises(PipelineFailure, match="living_hinge"):
        run_validate(bad, strict_flag=None)


def test_non_strict_unsupported_feature_reported_not_fatal(tmp_path):
    text = GOLDEN.read_text().replace("strict: true", "strict: false").replace(
        "requested_features:", "requested_features:\n  - integrated_living_hinge"
    )
    bad = tmp_path / "soft.yaml"
    bad.write_text(text)
    out = run_validate(bad, strict_flag=None)
    assert out["capability"]["unsupported_features"] == ["integrated_living_hinge"]
    assert out["capability"]["buildable"] is False


def test_cli_exit_code_zero_on_golden():
    from artifact_forge_ng.cli import main

    assert main(["validate", str(GOLDEN)]) == 0
