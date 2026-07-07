"""VF-3 CAD acceptance on the 4-part SMOKE row (cap + rail + cassette +
collector): both fluid handovers and both saddle hangs verified on the
compiled solids, the fluid paths void, the row water report and BOM-lite
written. The full 3-cell row is the `forge build` acceptance artifact —
kept out of the unit suite by design (build cost)."""

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.assembly.pipeline import run_assembly_build  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
SMOKE = EXAMPLES / "vertical_farm_row_smoke.yaml"


@pytest.fixture(scope="module")
def smoke_report(tmp_path_factory):
    out = tmp_path_factory.mktemp("row_smoke")
    return run_assembly_build(SMOKE, out, None), out


def test_smoke_builds_four_parts(smoke_report):
    report, out = smoke_report
    assert report["status"] == "pass"
    base = out / "vertical_farm_row_smoke"
    for ref in ("cap", "rail", "cassette", "collector"):
        assert report["parts"][ref]["status"] == "pass", ref
        assert (base / ref / "part.stl").exists()
    assert (base / "assembled.step").exists()


def test_smoke_fluid_chain(smoke_report):
    report, _ = smoke_report
    checks = {}
    for j in report["joints"]:
        checks.setdefault(j["check"], []).append(j["status"])
    assert checks["assembly.fluid_joint_ir"] == ["pass", "pass"]
    assert checks["assembly.saddle_hang_ir"] == ["pass", "pass"]
    assert all(s == "pass" for s in checks["assembly.no_interference"])
    assert set(report["built_features"]) == {
        "row_fluid_chain", "saddle_mount", "vertical_farm_cassette_interface",
    }


def test_smoke_row_water_report(smoke_report):
    report, out = smoke_report
    water = yaml.safe_load(
        Path(report["exports"]["water_report"]).read_text())
    row = water["row"]
    assert row["kind"] == "fluid_cascade"
    assert row["rack_mounting"] == "deferred"
    assert row["cells"] == 1
    assert len(row["handovers"]) == 2
    assert all(h["status"] == "pass" for h in row["handovers"])
    assert row["orphan_fluid_ports"] == "none"
    assert water["dead_pockets"] == "none found"


def test_smoke_bom(smoke_report):
    report, _ = smoke_report
    bom = report["bom"]
    printed = {e["archetype"]: e["qty"] for e in bom["printed_parts"]}
    assert printed == {"inlet_cap_v1": 1, "water_rail_v1": 1,
                       "coco_cassette_v1": 1, "collector_endcap_v1": 1}
    items = {h["item"]: h["qty"] for h in bom["hardware"]}
    assert items["silicone tube"] == 2
    assert Path(report["exports"]["bom"]).exists()
