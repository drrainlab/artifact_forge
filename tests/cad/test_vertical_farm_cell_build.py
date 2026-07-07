"""Vertical Farm Pack CAD acceptance: the golden cell really builds — 3
printable solids, water path open on the compiled rail, cassette seated
without interference, snap lips in their windows, water report + view
metadata written; and the two-cell line builds with continuous channels."""

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.assembly.pipeline import run_assembly_build  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
CELL = EXAMPLES / "water_rail_cell_2020_petg.yaml"
LINE = EXAMPLES / "two_cell_line_petg.yaml"


@pytest.fixture(scope="module")
def cell_report(tmp_path_factory):
    out = tmp_path_factory.mktemp("cell")
    return run_assembly_build(CELL, out, None), out


def test_cell_builds_three_parts(cell_report):
    report, out = cell_report
    assert report["status"] == "pass"
    base = out / "water_rail_cell_2020_petg"
    for ref in ("rail", "cassette", "frame"):
        assert report["parts"][ref]["status"] == "pass", ref
        assert (base / ref / "part.stl").exists()
        assert (base / ref / "part.step").exists()
    assert (base / "assembled.step").exists()


def test_cell_water_contract(cell_report):
    report, out = cell_report
    checks = {j["check"]: j["status"] for j in report["joints"]}
    assert checks["assembly.removable_insert_ir"] == "pass"
    assert checks["assembly.snap_joint_ir"] == "pass"
    assert checks["assembly.no_interference"] == "pass"
    assert checks["assembly.hooks_engage"] == "pass"
    assert set(report["built_features"]) == {
        "vertical_farm_cassette_interface", "snapped_retainer",
    }


def test_cell_water_report(cell_report):
    report, out = cell_report
    path = Path(report["exports"]["water_report"])
    assert path.exists()
    water = yaml.safe_load(path.read_text())
    assert water["mode"] == "transient_pulse"
    assert water["storage"] == "forbidden"
    assert water["channel"]["slope_deg"] == pytest.approx(1.25)
    assert water["channel"]["drop_mm"] == pytest.approx(5.41, abs=0.05)
    assert water["overflow"]["air_gap_mm"] == pytest.approx(1.5)
    assert water["dead_pockets"] == "none found"
    assert water["permanent_substrate_contact"] is False
    assert water["contact_window"]["verdict"] == "pulse_only"


def test_cell_view_metadata(cell_report):
    report, _ = cell_report
    views = report["views"]
    names = {p["name"] for p in views["section_planes"]}
    assert names == {"flow_section", "cross_section"}
    exploded = {e["part"]: e["vector"] for e in views["explode"]}
    assert exploded["cassette"][2] > 0  # inserts lift +Z
    assert exploded["frame"][2] > exploded["cassette"][2]


def test_two_cell_line_builds(tmp_path):
    report = run_assembly_build(LINE, tmp_path, None)
    assert report["status"] == "pass"
    checks = {j["check"]: j["status"] for j in report["joints"]}
    assert checks["assembly.tongue_groove_ir"] == "pass"
    assert checks["assembly.no_interference"] == "pass"
    assert report["built_features"] == ["module_line_interface"]
    # the line spreads along X in the explode metadata
    exploded = {e["part"]: e["vector"] for e in report["views"]["explode"]}
    assert abs(exploded["rail_b"][0]) > 0
