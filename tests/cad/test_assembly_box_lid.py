"""Fit-interfaces acceptance: the ESP32 box + lid really closes — seat,
screws and press-fit pins all verified in the assembled pose."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.assembly.pipeline import run_assembly_build  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
BOX = EXAMPLES / "esp32_box_with_lid.yaml"


def test_box_with_lid_acceptance(tmp_path):
    report = run_assembly_build(BOX, tmp_path, None)
    assert report["status"] == "pass"
    checks = {j["check"]: j["status"] for j in report["joints"]}
    for check in (
        "assembly.lid_seat_ir", "assembly.screw_joint_ir",
        "assembly.press_fit_ir", "assembly.no_interference",
        "assembly.screw_axes_clear", "assembly.lid_seats",
        "assembly.pins_engage",
    ):
        assert checks[check] == "pass", check
    assert set(report["built_features"]) == {
        "seated_lid", "bolted_interface", "press_fit_alignment"
    }
    base = tmp_path / "esp32_box_with_lid"
    assert (base / "box" / "part.stl").exists()
    assert (base / "lid" / "part.stl").exists()
    assert (base / "assembled.step").exists()
    # the press fit is real material overlap — measured, bounded, declared
    ni = next(j for j in report["joints"] if j["check"] == "assembly.no_interference")
    assert ni["measured"] > 0.5, "press-fit pins should overlap their bores"
    assert ni["measured"] <= ni["limit"]
