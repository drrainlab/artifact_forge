"""VF-correction CAD acceptance on the 6-part FLUSH SMOKE (cap + two
rails with ONE real lap seam + cassette + collector + one straight
profile): the lap lip really nests in the FLOORED lip-seat receiver on
compiled solids (no interference, real clearances), both drip handovers verified,
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


def test_smoke_collector_is_end_receiver(smoke_report):
    """VF-4.1: the receiver truths hold on the compiled, posed solids."""
    report, _ = smoke_report
    checks = {}
    for j in report["joints"]:
        checks.setdefault(j["check"], []).append(j["status"])
    assert checks["assembly.collector_captures_drain_edge"] == ["pass"]
    assert checks["assembly.collector_mouth_envelopes_outlet_lip"] == ["pass"]
    assert checks["assembly.collector_removable_by_hand"] == ["pass"]


def test_smoke_parts_print_supportless(smoke_report):
    """Printability on real parts: the skeleton rail has no ceiling
    bridges, the collector's VERTICAL drain has no horizontal bore to flag,
    and the declared orientation matches the builder."""
    report, out = smoke_report
    base = out / "vertical_farm_flush_smoke"
    for ref, expect in (("rail_1", "manufacturing.supportless_lightweight_windows_ok"),
                        ("collector", "manufacturing.horizontal_bore_supportless")):
        findings = yaml.safe_load((base / ref / "findings.yaml").read_text())
        by_check = {f["check"]: f["status"] for f in findings["findings"]}
        assert by_check.get(expect) == "pass", (ref, expect, by_check.get(expect))
        assert by_check.get("manufacturing.print_orientation_declared") == "pass"


def test_smoke_collector_sturdy_and_vertical_drain(smoke_report):
    """VF-4.2 on the compiled collector: sturdy U-frame verdict, and the
    drain really exits the BOTTOM (void column from the tray floor down
    through the part underside, solid walls beside the mouth)."""
    report, out = smoke_report
    base = out / "vertical_farm_flush_smoke"
    findings = yaml.safe_load((base / "collector" / "findings.yaml").read_text())
    by_check = {f["check"]: f["status"] for f in findings["findings"]}
    assert by_check.get("form.collector_structure_sturdy") == "pass"
    assert by_check.get("form.collector_tray_drains") == "pass"

    import cadquery as cq

    from artifact_forge_ng.cad.geometry import Geometry
    from artifact_forge_ng.validators.topology import box_probe, solid_fraction
    geo = Geometry(cq.importers.importStep(
        str(base / "collector" / "part.step")))
    bb = geo.workplane.val().BoundingBox()
    # a void column near the drain (x~0) from the very bottom up a few mm —
    # the tube passage out the underside
    drain = box_probe(-3.0, bb.ymin + 3.0, bb.zmin + 0.5,
                      3.0, bb.ymin + 12.0, bb.zmin + 4.0)
    assert solid_fraction(geo.workplane, drain) < 0.2
    # a solid side wall beside the mouth (x near the outer edge, mid height)
    wall = box_probe(bb.xmax - 3.5, -6.0, bb.zmin + 3.0,
                     bb.xmax - 1.0, -3.0, bb.zmin + 8.0)
    assert solid_fraction(geo.workplane, wall) > 0.85


def test_smoke_frame_report_and_bom(smoke_report):
    report, _ = smoke_report
    frame = yaml.safe_load(Path(report["exports"]["frame_report"]).read_text())
    assert frame["full_profile_seating"] is True
    assert frame["span_gap_mm"] == 0
    assert frame["modules_flush"] is True
    assert "magnet_installation" not in frame  # smoke has no magnets
    bom = report["bom"]
    printed = {e["archetype"]: e["qty"] for e in bom["printed_parts"]}
    assert printed == {"inlet_cap_v1": 1, "water_rail_v1": 2,
                       "coco_cassette_v1": 1, "collector_endcap_v1": 1}
    items = {h["item"]: h for h in bom["hardware"]}
    profile = next(v for k, v in items.items() if "aluminum profile" in k)
    assert "standard straight" in profile["item"]
    assert "mount the WHOLE row" in profile["note"]
