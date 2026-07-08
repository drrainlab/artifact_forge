"""VF-correction CAD acceptance on the 6-part FLUSH SMOKE (cap + two
rails with ONE real lap seam + cassette + collector + one straight
profile): the lap lip really lands in the through receiver on compiled
solids (no interference, real clearances), both drip handovers verified,
the flush row reports written. The full 3x1 row is the `forge build`
acceptance artifact — kept out of the unit suite by design (build cost)."""

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.assembly.pipeline import run_assembly_build  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
SMOKE = EXAMPLES / "vertical_farm_flush_smoke.yaml"


@pytest.fixture(scope="module")
def smoke_report(tmp_path_factory):
    out = tmp_path_factory.mktemp("flush_smoke")
    return run_assembly_build(SMOKE, out, None), out


def test_smoke_builds_printed_parts(smoke_report):
    report, out = smoke_report
    assert report["status"] == "pass"
    base = out / "vertical_farm_flush_smoke"
    for ref in ("cap", "rail_1", "rail_2", "cassette", "collector"):
        assert report["parts"][ref]["status"] == "pass", ref
        assert (base / ref / "part.stl").exists()
    assert (base / "assembled.step").exists()


def test_smoke_lap_seam_on_solids(smoke_report):
    """THE correction proof: one real lap seam — flush IR verdict AND
    no CAD interference between the lip and the receiver walls."""
    report, _ = smoke_report
    checks = {}
    for j in report["joints"]:
        checks.setdefault(j["check"], []).append(j["status"])
    assert checks["assembly.lap_flow_ir"] == ["pass"]
    assert checks["assembly.fluid_joint_ir"] == ["pass", "pass"]
    assert checks["assembly.saddle_hang_ir"] == ["pass", "pass"]
    assert checks["assembly.row_flush_aligned"] == ["pass"]
    assert checks["assembly.row_drains_under_mount"] == ["pass"]
    assert checks["assembly.profile_support_full_length"] == ["pass"]
    assert all(s == "pass" for s in checks["assembly.no_interference"])
    assert set(report["built_features"]) == {
        "row_water_chain", "row_flush_integrity",
        "vertical_farm_cassette_interface",
    }


def test_smoke_flush_water_report(smoke_report):
    report, _ = smoke_report
    water = yaml.safe_load(
        Path(report["exports"]["water_report"]).read_text())
    assert water["channel"]["slope_deg"] == 0.0
    row = water["row"]
    assert row["kind"] == "tilted_flush_row"
    assert row["modules_flush"] is True
    assert row["slope_deg"] == pytest.approx(1.5)
    kinds = [h["type"] for h in row["handovers"]]
    assert kinds.count("lap_flow") == 1
    assert kinds.count("drip") == 2
    assert all(h["status"] == "pass" for h in row["handovers"])
    assert row["lap_seam_leak"] == "controlled"
    assert row["standing_water_under_mount"] == "none"
    assert water["dead_pockets"] == "none found"


def test_smoke_frame_report_and_bom(smoke_report):
    report, _ = smoke_report
    frame = yaml.safe_load(Path(report["exports"]["frame_report"]).read_text())
    assert frame["full_profile_seating"] is True
    assert frame["span_gap_mm"] == 0
    assert frame["modules_flush"] is True
    bom = report["bom"]
    printed = {e["archetype"]: e["qty"] for e in bom["printed_parts"]}
    assert printed == {"inlet_cap_v1": 1, "water_rail_v1": 2,
                       "coco_cassette_v1": 1, "collector_endcap_v1": 1}
    items = {h["item"]: h for h in bom["hardware"]}
    profile = next(v for k, v in items.items() if "aluminum profile" in k)
    assert "standard straight" in profile["item"]
    assert "mount the WHOLE row" in profile["note"]
