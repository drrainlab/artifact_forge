"""VF-3 row-level reports at the IR level: the water report gains the row
rollup (cascade kind, per-cell drops, handover chain, total drop, orphan
verdict) while keeping the single-cell shape backward compatible; BOM-lite
derives printed parts and hardware from the assembly itself."""

from pathlib import Path

import pytest

from artifact_forge_ng.assembly.bom import build_bom
from artifact_forge_ng.assembly.pipeline import (
    _inject_shared,
    _joint_findings,
    load_assembly,
)
from artifact_forge_ng.assembly.water_report import build_water_report
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.pipeline import pre_cad_from_instance

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
ROW = EXAMPLES / "vertical_farm_row_3x1_petg.yaml"
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


def test_row_water_report_rollup(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    water = build_water_report(states, findings, asm=asm, poses=poses)
    assert water is not None
    row = water["row"]
    assert row["kind"] == "fluid_cascade"
    assert row["z_step_policy"] == "datum_handover"
    assert row["rack_mounting"] == "deferred"
    assert row["cells"] == 3
    assert len(row["handovers"]) == 4
    assert all(h["status"] == "pass" for h in row["handovers"])
    assert row["handovers"][0]["from"] == "cap"
    assert row["handovers"][-1]["to"] == "collector"
    assert row["orphan_fluid_ports"] == "none"
    assert len(row["saddle_mounts"]) == 2
    # cascade: 3 cells x ~5.41 internal drop + 2 x 2.5 handover steps
    assert row["total_drop_mm"] == pytest.approx(3 * 5.41 + 2 * 2.5, abs=0.1)
    for cell in row["cell_details"]:
        assert cell["cassette_contact"] == "pulse_only"


def test_single_cell_report_shape_unchanged(row_ctx):
    """The cell golden keeps its VF-1 top-level fields (backward compat)."""
    catalog, *_ = row_ctx
    asm = load_assembly(CELL)
    instances = _inject_shared(asm, catalog)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in instances.items()}
    findings, poses, _ = _joint_findings(asm, states)
    water = build_water_report(states, findings, asm=asm, poses=poses)
    assert water["channel"]["slope_deg"] == pytest.approx(1.25)
    assert water["contact_window"]["verdict"] == "pulse_only"
    # no fluid joints in the cell -> no row rollup pretence
    assert "row" not in water


def test_bom_lite_derived(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    bom = build_bom(asm, states, catalog)
    printed = {e["archetype"]: e for e in bom["printed_parts"]}
    assert printed["water_rail_v1"]["qty"] == 3
    assert printed["coco_cassette_v1"]["qty"] == 3
    assert printed["inlet_cap_v1"]["qty"] == 1
    assert printed["collector_endcap_v1"]["qty"] == 1
    items = {h["item"]: h for h in bom["hardware"]}
    assert items["silicone tube"]["qty"] == 2  # feed + drain
    assert "9" in items["silicone tube"]["note"]
    assert items["aluminum profile 2020"]["qty"] == 6  # 2 per module x 3
    assert "not the final rack" in items["aluminum profile 2020"]["note"]
    assert bom["print"]["materials"] == ["PETG"]
    assert bom["print"]["bed_min_mm"] == [250.0, 250.0, 250.0]
    # no screws in the row -> no phantom screw lines
    assert not any("screw" in h["item"] for h in bom["hardware"])


# -- VF-4: frame report + BOM with the aluminum carrier -------------------------

CARRIED = EXAMPLES / "vertical_farm_carried_smoke.yaml"


@pytest.fixture(scope="module")
def carried_ctx():
    catalog = load_catalog()
    asm = load_assembly(CARRIED)
    instances = _inject_shared(asm, catalog)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in instances.items()}
    findings, poses, _ = _joint_findings(asm, states)
    return catalog, asm, states, findings, poses


def test_frame_report(carried_ctx):
    from artifact_forge_ng.assembly.frame_report import build_frame_report

    catalog, asm, states, findings, poses = carried_ctx
    frame = build_frame_report(asm, states, findings)
    assert frame is not None
    assert frame["support_verdict"] == "pass"
    assert frame["pitch_verdict"] == "pass"
    assert frame["slope_verdict"] == "pass"
    prof = frame["carrier"][0]
    assert prof["size"] == "2020"
    assert prof["slope_deg"] == pytest.approx(1.827, abs=0.01)
    assert "reference proxy" in prof["geometry"]
    assert frame["rails"][0]["perched_on"] == ["profile_e"]
    assert frame["rails"][0]["contact"] == "upstream_edge"
    assert "VF-4.1" in frame["scope"]


def test_frame_report_absent_without_carrier(row_ctx):
    from artifact_forge_ng.assembly.frame_report import build_frame_report

    catalog, asm, states, findings, poses = row_ctx
    assert build_frame_report(asm, states, findings) is None


def test_bom_carried_profile_line(carried_ctx):
    catalog, asm, states, findings, poses = carried_ctx
    bom = build_bom(asm, states, catalog)
    printed = {e["archetype"] for e in bom["printed_parts"]}
    # the reference profile is NOT a printed part
    assert "aluminum_profile_ref_v1" not in printed
    items = {h["item"]: h for h in bom["hardware"]}
    line = items["aluminum profile 2020, standard straight, cut to length"]
    assert line["qty"] == 1
    assert line["length_mm"] == pytest.approx(280.0)
    assert "reference proxy" in line["note"]
    assert "NOT a wedge-cut" in line["note"]
    # the old per-slot heuristic must NOT double count
    assert "aluminum profile 2020" not in items or \
        items.get("aluminum profile 2020") is None
    # print rollup ignores the aluminum
    assert bom["print"]["materials"] == ["PETG"]
