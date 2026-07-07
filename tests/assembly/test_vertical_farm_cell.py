"""Vertical Farm cell acceptance at the IR level (no CAD import): the
golden assembly validates, the Cassette Interface Standard rides the
shared params, and shared-level mutations fail exactly the joint that owns
the defect. (The CAD build acceptance lives in tests/cad/.)"""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.pipeline import (
    AssemblyFailure,
    load_assembly,
    run_assembly_validate,
)

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
CELL = EXAMPLES / "water_rail_cell_2020_petg.yaml"
LINE = EXAMPLES / "two_cell_line_petg.yaml"


def mutate(tmp_path, src: Path, patch) -> Path:
    doc = yaml.safe_load(src.read_text())
    patch(doc)
    out = tmp_path / src.name
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return out


def joint_status(report: dict, check: str) -> str:
    hits = [j["status"] for j in report["joints"] if j["check"] == check]
    assert hits, f"{check} did not run"
    return hits[0]


def test_golden_cell_validates():
    report = run_assembly_validate(CELL, None)
    assert report["status"] == "pass"
    assert joint_status(report, "assembly.removable_insert_ir") == "pass"
    assert joint_status(report, "assembly.snap_joint_ir") == "pass"
    # the chained frame pose composes through the seated cassette
    frame_pose = next(p for p in report["assembly_pose"] if p["part"] == "frame")
    assert frame_pose["translate"][2] == pytest.approx(45.0)


def test_golden_line_validates():
    report = run_assembly_validate(LINE, None)
    assert report["status"] == "pass"
    assert joint_status(report, "assembly.tongue_groove_ir") == "pass"


def test_shared_params_reach_all_parts():
    asm = load_assembly(CELL)
    assert asm.shared["cassette_l"] == "220mm"
    # one number, three consumers — desync unrepresentable
    for ref in ("rail", "cassette"):
        part = next(p for p in asm.parts if p.ref == ref)
        assert "cassette_l" not in part.product.params


def test_loose_clearance_clamped_by_resolver(tmp_path):
    """Defense in depth: a 2mm seat clearance never reaches the joint —
    the archetype band clamps it to 1mm (WARN) and the seated fit stays
    legal. (The unclamped joint-level failure is pinned in
    tests/assembly/test_vertical_farm_joints.py.)"""
    def patch(doc):
        doc["shared"]["seat_clearance"] = "2mm"

    report = run_assembly_validate(mutate(tmp_path, CELL, patch), None)
    assert report["status"] == "pass"
    assert joint_status(report, "assembly.removable_insert_ir") == "pass"
    msg = next(j["message"] for j in report["joints"]
               if j["check"] == "assembly.removable_insert_ir")
    assert "1 clearance" in msg  # the clamped value, not the requested 2


def test_flooding_window_clamped_by_resolver(tmp_path):
    """Same defense for the window: 4mm drop clamps to the 2mm band edge —
    pulse-only contact survives the attack."""
    def patch(doc):
        cassette = next(p for p in doc["parts"] if p["ref"] == "cassette")
        cassette["product"]["params"]["window_drop"] = "4mm"

    report = run_assembly_validate(mutate(tmp_path, CELL, patch), None)
    assert report["status"] == "pass"
    reach = next(j["measured"] for j in report["joints"]
                 if j["check"] == "assembly.removable_insert_ir")
    assert reach <= 2.0 + 1e-6


def test_misplaced_snap_windows_fail(tmp_path):
    """A LEGAL-band snap_top_offset that no longer meets the frame's hook
    lips is exactly what the pose-level snap check exists for."""
    def patch(doc):
        cassette = next(p for p in doc["parts"] if p["ref"] == "cassette")
        cassette["product"]["params"]["snap_top_offset"] = "12mm"

    try:
        report = run_assembly_validate(mutate(tmp_path, CELL, patch), None)
    except AssemblyFailure as exc:
        report = exc.report
    assert joint_status(report, "assembly.snap_joint_ir") == "fail"


def test_desynced_channel_fails_line(tmp_path):
    def patch(doc):
        rail_b = next(p for p in doc["parts"] if p["ref"] == "rail_b")
        rail_b["product"]["params"]["module_w"] = "240mm"

    report = None
    try:
        report = run_assembly_validate(mutate(tmp_path, LINE, patch), None)
    except AssemblyFailure as exc:
        report = exc.report
    assert report is not None
    assert joint_status(report, "assembly.tongue_groove_ir") == "fail"


def test_flipped_module_fails_line(tmp_path):
    def patch(doc):
        doc["joints"][0]["rotate"] = [0, 0, 180]

    try:
        report = run_assembly_validate(mutate(tmp_path, LINE, patch), None)
    except AssemblyFailure as exc:
        report = exc.report
    assert joint_status(report, "assembly.tongue_groove_ir") == "fail"
