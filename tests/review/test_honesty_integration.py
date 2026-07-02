"""End-to-end honesty: a successful build proves every requested feature
with validators and writes the report files; nothing is claimed without
evidence."""

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.compiler.pipeline import run_build  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = EXAMPLES / "desk_cable_clip_20mm.yaml"


@pytest.fixture(scope="module")
def build_out(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("build")
    return run_build(GOLDEN, out_dir, strict_flag=None), out_dir


def test_all_requested_features_built_and_verified(build_out):
    out, _ = build_out
    honesty = out["honesty_report"]
    assert set(honesty["built_features"]) >= set(honesty["requested_features"])
    assert honesty["missing_features"] == []
    assert honesty["unsupported_features"] == []
    assert honesty["critical_failures"] == []


def test_forbidden_forms_all_checked_absent(build_out):
    out, _ = build_out
    checked = {c["form"]: c["status"] for c in out["honesty_report"]["forbidden_forms_checked"]}
    assert checked == {
        "symmetric_c_ring": "absent",
        "closed_ring": "absent",
        "downward_entry": "absent",
        "boxy_rectangular_hook": "absent",
    }


def test_score_pass_with_all_dimensions(build_out):
    out, _ = build_out
    score = out["score"]
    assert score["status"] == "pass"
    assert {"form", "manufacturing", "quality"} <= set(score["scores"])


def test_report_files_written(build_out):
    out, out_dir = build_out
    target = out_dir / "desk_cable_clip_20mm"
    honesty = yaml.safe_load((target / "honesty_report.yaml").read_text())
    assert honesty["built_features"]
    findings = yaml.safe_load((target / "findings.yaml").read_text())
    assert findings["status"] == "pass"
    assert (target / "part.stl").stat().st_size > 10_000
