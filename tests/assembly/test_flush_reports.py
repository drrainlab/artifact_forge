"""Row reports after the VF correction, at the IR level: water_report
tells the tilted flush row story (virtual drop, lap + drip handovers,
controlled seam leak), frame_report reports FULL seating on standard
straight profiles (span gap 0), and the BOM carries cut-to-length
profiles, the mount note and the magnet line."""

from pathlib import Path

import pytest

from artifact_forge_ng.assembly.bom import build_bom
from artifact_forge_ng.assembly.frame_report import build_frame_report
from artifact_forge_ng.assembly.pipeline import (
    _inject_shared,
    _joint_findings,
    load_assembly,
)
from artifact_forge_ng.assembly.water_report import build_water_report
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.pipeline import pre_cad_from_instance

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
ROW = EXAMPLES / "vertical_farm_row_3x1.yaml"
CELL = EXAMPLES / "water_rail_cell_2020_petg.yaml"


@pytest.fixture(scope="module")
def row_ctx():
    catalog = load_catalog()
    asm = load_assembly(ROW)
    instances = _inject_shared(asm, catalog)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in instances.items()}
    findings, poses, _ = _joint_findings(asm, states)
    return catalog, asm, states, findings, poses


def test_water_report_row_rollup(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    water = build_water_report(states, findings, asm=asm, poses=poses)
    row = water["row"]
    assert row["kind"] == "tilted_flush_row"
    assert row["modules_flush"] is True
    assert row["stair_step"] is False
    assert row["slope_deg"] == pytest.approx(1.5)
    assert row["slope_source"] == "mounted_profile"
    assert row["cells"] == 3
    # total virtual drop over the whole floor path — positive, real
    assert row["total_virtual_drop_mm"] > 10.0
    kinds = [h["type"] for h in row["handovers"]]
    assert kinds.count("lap_flow") == 2
    assert kinds.count("drip") == 2
    for h in row["handovers"]:
        assert h["status"] == "pass", h
        if h["type"] == "lap_flow":
            assert abs(h["dz_mm"]) <= 0.05  # flush means flush
    assert row["standing_water_under_mount"] == "none"
    assert row["lap_seam_leak"] == "controlled"
    assert set(row["drips_clear_of"]) == {"profiles", "magnets", "dry_zones"}
    assert row["orphan_fluid_ports"] == "none"
    # VF-4.2 honesty: the skeleton rail does not contain top-water overflow
    oc = row["overflow_containment"]
    assert oc["status"] == "absent"
    assert oc["path"] == "drains_through_skeleton"
    assert "VF-5" in oc["planned_fix"]


def test_water_report_channel_is_level(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    water = build_water_report(states, findings, asm=asm, poses=poses)
    ch = water["channel"]
    assert ch["slope_deg"] == 0.0
    assert ch["drop_mm"] == 0.0
    assert ch["depth_inlet_mm"] == ch["depth_outlet_mm"]
    lap = water["lap_handover"]
    assert lap["lip_len_mm"] == pytest.approx(4.0)
    assert lap["face_gap_mm"] == pytest.approx(0.4)


def test_frame_report_flush(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    frame = build_frame_report(asm, states, findings)
    assert frame["slope_source"] == "physical_mount"
    assert frame["slope_deg"] == pytest.approx(1.5)
    assert frame["full_profile_seating"] is True
    assert frame["span_gap_mm"] == 0
    assert frame["stair_step"] is False
    assert frame["modules_flush"] is True
    assert frame["drainage_verdict"] == "pass"
    for prof in frame["carrier"]:
        assert prof["slope_deg"] == 0.0  # the MODEL is straight
        assert "straight" in prof["geometry"]
    for rail in frame["rails"]:
        assert rail["contact"] == "full_length"
        assert len(rail["perched_on"]) == 2
    magnets = frame["magnet_installation"]
    assert magnets["method"] == "press_fit_dry_face"
    assert magnets["water_exposed"] is False
    assert magnets["role"] == "alignment_only"
    assert magnets["count"] == 12


def test_bom_profiles_magnets_and_mount_note(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    bom = build_bom(asm, states, catalog)
    hardware = {h["item"]: h for h in bom["hardware"]}
    profile = next(v for k, v in hardware.items() if "aluminum profile" in k)
    assert profile["qty"] == 2
    assert "standard straight" in profile["item"]
    assert "1.5" in profile["note"] and "mount the WHOLE row" in profile["note"]
    magnet = next(v for k, v in hardware.items() if "magnet" in k)
    assert magnet["qty"] == 12  # 3 rails x 4 sealed pockets
    assert "alignment only" in magnet["note"]
    assert "coated" in magnet["note"] or "epoxy" in magnet["note"]
    printed = {p["archetype"]: p for p in bom["printed_parts"]}
    assert printed["water_rail_v1"]["qty"] == 3
    assert "aluminum_profile_ref_v1" not in printed  # reference, never printed


def test_single_cell_report_shape_unchanged():
    catalog = load_catalog()
    asm = load_assembly(CELL)
    instances = _inject_shared(asm, catalog)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in instances.items()}
    findings, poses, _ = _joint_findings(asm, states)
    water = build_water_report(states, findings, asm=asm, poses=poses)
    assert water["mode"] == "transient_pulse"
    assert water["storage"] == "forbidden"
    assert water["channel"]["slope_deg"] == 0.0
    assert "row" not in water  # no water joints — no row story
    frame = build_frame_report(asm, states, findings)
    assert frame is None  # no carrier — no frame story


# -- VF-5A: the root chamber row -----------------------------------------------

ROW_RC = EXAMPLES / "vertical_farm_row_3x1_root_chamber.yaml"


def test_root_chamber_row_contains_overflow_and_drains():
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    findings, poses, _ = _joint_findings(asm, states)
    checks = {}
    for f in findings:
        checks.setdefault(f.check, []).append(f.status.value)
    assert checks["assembly.collector_catches_root_drainage"] == ["pass"]
    water = build_water_report(states, findings, asm=asm, poses=poses)
    row = water["row"]
    oc = row["overflow_containment"]
    assert oc["status"] == "contained"
    assert oc["return"] == "passive_root_drainage_return"
    rm = row["cassette_removal"]
    assert "roots" in rm["mid_cycle"]
    # the rails really are root chambers
    r1 = states["rail_1"].report
    assert r1.passed("form.root_chamber_ok")
    assert r1.passed("form.no_secondary_water_channel")  # troughs exempt


def test_root_chamber_row_endcaps_dock_magnetically():
    """VF-6: the collector and inlet cap magnetically dock onto the terminal
    modules' end wall tops — the seating check proves both mates."""
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    findings, poses, _ = _joint_findings(asm, states)
    docks = [f for f in findings if f.check == "assembly.endcap_docks_to_rail"]
    assert len(docks) == 2  # collector (front) + cap (back)
    for f in docks:
        assert f.status.value == "pass", f.message
        assert f.measured < 1.0
    # only the terminal rails carry dock pockets; the middle one does not
    assert states["rail_1"].form.frame["dock_pocket_count"] == 2
    assert states["rail_2"].form.frame["dock_pocket_count"] == 0
    assert states["rail_3"].form.frame["dock_pocket_count"] == 2
    assert states["collector"].report.passed("form.dock_pockets_dry")
    assert states["cap"].report.passed("form.dock_pockets_dry")
