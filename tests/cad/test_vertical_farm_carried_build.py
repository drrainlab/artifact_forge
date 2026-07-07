"""VF-4 CAD acceptance on the carried smoke (cell + adapters + one
aluminum profile reference proxy): the sloped-top proxy compiles, does not
pierce the rail grooves in the pose (no_interference), the reference part
skips manufacturing scrutiny honestly, and the frame report + BOM land in
the build. The full 3-cell carried row is the forge-build acceptance
artifact — out of the unit suite by design."""

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.assembly.pipeline import run_assembly_build  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
SMOKE = EXAMPLES / "vertical_farm_carried_smoke.yaml"


@pytest.fixture(scope="module")
def carried_report(tmp_path_factory):
    out = tmp_path_factory.mktemp("carried_smoke")
    return run_assembly_build(SMOKE, out, None), out


def test_carried_smoke_builds(carried_report):
    report, out = carried_report
    assert report["status"] == "pass"
    base = out / "vertical_farm_carried_smoke"
    for ref in ("cap", "rail", "cassette", "collector", "profile_e"):
        assert report["parts"][ref]["status"] == "pass", ref
    assert (base / "assembled.step").exists()
    # the profile exports as reference, never as a print
    assert report["parts"]["profile_e"]["exports"]["role"] == "reference"
    assert report["parts"]["rail"]["exports"]["role"] == "print"


def test_carried_support_verified_on_solids(carried_report):
    report, _ = carried_report
    checks = {}
    for j in report["joints"]:
        checks.setdefault(j["check"], []).append(j["status"])
    assert checks["assembly.profile_perch_ir"] == ["pass"]
    assert checks["assembly.row_supported"] == ["pass"]
    assert checks["assembly.row_pitch_aligned"] == ["pass"]
    assert checks["assembly.profile_slope_feeds_downhill"] == ["pass"]
    # the sloped proxy touches the groove without piercing it
    assert all(s == "pass" for s in checks["assembly.no_interference"])
    assert "row_carried_by_profile" in report["built_features"]


def test_carried_frame_report_written(carried_report):
    report, _ = carried_report
    frame_path = Path(report["exports"]["frame_report"])
    assert frame_path.exists()
    frame = yaml.safe_load(frame_path.read_text())
    assert frame["support_verdict"] == "pass"
    assert "reference proxy" in frame["carrier"][0]["geometry"]
    assert "VF-4.1" in frame["scope"]


def test_carried_bom(carried_report):
    report, _ = carried_report
    items = {h["item"]: h for h in report["bom"]["hardware"]}
    assert "aluminum profile 2020, standard straight, cut to length" in items
    printed = {e["archetype"] for e in report["bom"]["printed_parts"]}
    assert "aluminum_profile_ref_v1" not in printed
