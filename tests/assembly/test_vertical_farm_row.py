"""VF-3 row acceptance at the IR level (no CAD): the 3-cell fluid cascade
validates end-to-end — chain poses step downhill, every fluid handover
passes, required fluid ports are mated by REALIZING joints only, and the
row honestly names itself a cascade. Mutations: misordered chain, rotated
cell, saddle-only mating (auxiliary must not satisfy required ports)."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.pipeline import (
    AssemblyFailure,
    run_assembly_validate,
)

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
ROW = EXAMPLES / "vertical_farm_row_3x1_petg.yaml"
SMOKE = EXAMPLES / "vertical_farm_row_smoke.yaml"


def mutate(tmp_path, src: Path, patch) -> Path:
    doc = yaml.safe_load(src.read_text())
    patch(doc)
    out = tmp_path / src.name
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return out


def checks_of(report, name):
    return [j for j in report["joints"] if j["check"] == name]


@pytest.fixture(scope="module")
def row_report():
    return run_assembly_validate(ROW, None)


def test_row_validates(row_report):
    assert row_report["status"] == "pass"
    assert row_report["meta"]["row_kind"] == "fluid_cascade"


def test_row_cascade_steps_downhill(row_report):
    z = {p["part"]: (0.0 if p.get("transform") == "identity"
                     else p["translate"][2])
         for p in row_report["assembly_pose"]}
    # every rail sits lower than the previous one; the collector lowest
    assert z["rail_1"] < z["cap"] - 5.0
    assert z["rail_2"] < z["rail_1"] - 5.0
    assert z["rail_3"] < z["rail_2"] - 5.0
    assert z["collector"] < z["rail_3"]
    # and the cells march along -Y (the flow axis), one module each
    y = {p["part"]: (0.0 if p.get("transform") == "identity"
                     else p["translate"][1])
         for p in row_report["assembly_pose"]}
    assert y["rail_2"] == pytest.approx(y["rail_1"] - 248.0)
    assert y["rail_3"] == pytest.approx(y["rail_2"] - 248.0)


def test_all_fluid_handovers_pass(row_report):
    fluid = checks_of(row_report, "assembly.fluid_joint_ir")
    assert len(fluid) == 4  # cap->r1, r1->r2, r2->r3, r3->collector
    assert all(f["status"] == "pass" for f in fluid), fluid
    assert all("downhill" in f["message"] for f in fluid)


def test_saddles_verified(row_report):
    saddles = checks_of(row_report, "assembly.saddle_hang_ir")
    assert len(saddles) == 2
    assert all(s["status"] == "pass" for s in saddles), saddles


def test_no_orphan_required_ports(row_report):
    orphan = checks_of(row_report, "assembly.no_orphan_ports")
    assert orphan and orphan[0]["status"] == "pass"


def test_smoke_assembly_validates():
    report = run_assembly_validate(SMOKE, None)
    assert report["status"] == "pass"
    assert len(checks_of(report, "assembly.fluid_joint_ir")) == 2


# Mutations run on the 4-part SMOKE assembly — same semantics as the full
# row at half the form-building cost.

def test_misordered_chain_fails(tmp_path):
    def patch(doc):
        # the cassette insert listed before its rail is posed
        joints = doc["joints"]
        joints.insert(0, joints.pop(2))

    try:
        report = run_assembly_validate(mutate(tmp_path, SMOKE, patch), None)
    except AssemblyFailure as exc:
        report = exc.report
    msgs = [j["message"] for j in report["joints"]
            if j["check"] == "assembly.joint_pose"]
    assert any("chain order" in m for m in msgs)


def test_rotated_cell_fails(tmp_path):
    def patch(doc):
        fluid = next(j for j in doc["joints"]
                     if j["type"] == "fluid_joint" and j["b"] == "rail.inlet")
        fluid["rotate"] = [0, 0, 180]

    try:
        report = run_assembly_validate(mutate(tmp_path, SMOKE, patch), None)
    except AssemblyFailure as exc:
        report = exc.report
    assert report["status"] == "fail"


def test_saddle_alone_leaves_ports_orphan(tmp_path):
    """The auxiliary verification joint must never satisfy a required
    fluid port — a row 'held together' by saddles alone fails no_orphan."""
    def patch(doc):
        for j in doc["joints"]:
            if j["type"] == "fluid_joint":
                j["type"] = "saddle_hang"

    try:
        report = run_assembly_validate(mutate(tmp_path, SMOKE, patch), None)
    except AssemblyFailure as exc:
        report = exc.report
    orphan = [j for j in report["joints"]
              if j["check"] == "assembly.no_orphan_ports"]
    assert orphan and any(o["status"] == "fail" for o in orphan)
