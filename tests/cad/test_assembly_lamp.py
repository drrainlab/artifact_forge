"""R1 Verified Assemblies acceptance: the desk lamp really fits together —
measured in the assembled pose, with physical negatives."""

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.assembly.pipeline import run_assembly_build  # noqa: E402
from artifact_forge_ng.pipeline import PipelineFailure  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
LAMP = EXAMPLES / "desk_lamp_e27.yaml"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("lamp")
    return run_assembly_build(LAMP, out, None), out


def test_acceptance_definition_of_done(built):
    report, out = built
    assert report["status"] == "pass"
    checks = {j["check"]: j["status"] for j in report["joints"]}
    assert checks["assembly.screw_joint_ir"] == "pass"
    assert checks["assembly.no_interference"] == "pass"
    assert checks["assembly.screw_axes_clear"] == "pass"
    assert checks["assembly.channel_continuous_across"] == "pass"
    assert set(report["built_features"]) == {"bolted_interface", "cross_part_wiring"}
    base = out / "desk_lamp_e27"
    assert (base / "bracket" / "part.stl").exists()
    assert (base / "cup" / "part.stl").exists()
    assert (base / "assembled.step").exists()
    assert (base / "assembly_report.yaml").exists()
    poses = {p["part"] for p in report["assembly_pose"]}
    assert poses == {"bracket", "cup"}


def test_wrong_pose_creates_real_interference(tmp_path):
    """Flip the cup the wrong way (opening INTO the arm) — the parts
    physically collide and the interference probe must catch it."""
    doc = yaml.safe_load(LAMP.read_text())
    doc["joints"][0]["rotate"] = [0, 0, 0]
    bad = tmp_path / "bad_pose.yaml"
    bad.write_text(yaml.safe_dump(doc, sort_keys=False))
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_build(bad, tmp_path / "out", None)
    assert "assembly" in str(exc_info.value)


def test_blocked_channel_fails_the_cad_probe(tmp_path):
    """Shrink the cup's cable exit below the declared wiring diameter —
    the cross-part continuity probe must fail on real material."""
    doc = yaml.safe_load(LAMP.read_text())
    doc["parts"][1]["product"]["params"]["exit_d"] = "5mm"
    doc["wiring"]["d"] = "8mm"
    bad = tmp_path / "blocked.yaml"
    bad.write_text(yaml.safe_dump(doc, sort_keys=False))
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_build(bad, tmp_path / "out", None)
    report = getattr(exc_info.value, "report", None)
    assert report is not None
    checks = {j["check"]: j["status"] for j in report["joints"]}
    assert checks["assembly.channel_continuous_across"] == "fail"
