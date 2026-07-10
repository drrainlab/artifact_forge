"""The drip fluid_joint physics after the VF correction: rails mate FLUSH
(no step between modules — that is lap_flow_joint's contract now); the only
surviving fall is the FEED datum the inlet cap's tower targets. Plus the
actionable wrong-direction message, the receiver-width rule, the joint
ordering guard and the assembly meta passthrough."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.joints import (
    compute_pose,
)
from artifact_forge_vf.joints import (
    _fluid_joint_ir,
)
from artifact_forge_ng.assembly.pipeline import (
    AssemblyFailure,
    run_assembly_validate,
)
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState
from artifact_forge_vf.ops import FALL_ENTRY
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.assembly import JointUse

EXAMPLES = Path(__file__).parents[1] / "examples" / "vertical_farm"
CELL = EXAMPLES / "water_rail_cell_2020_petg.yaml"

RAIL_PARAMS = dict(
    module_l=248.0, module_w=248.0, body_h=30.0,
    channel_w=16.0, channel_d=5.0, channel_bottom_r=1.2,
    cassette_l=220.0, cassette_w=220.0,
    seat_depth=14.0, seat_clearance=0.75,
    module_pitch=250.0, corner_r=4.0, face_gap=0.4,
)


def rail_form(name="rail", **over) -> PartForm:
    st = RecipeState()
    p = dict(RAIL_PARAMS)
    p.update(over)
    RECIPE_OPS["water_rail_body"].apply(st, p, "body")
    RECIPE_OPS["lap_outlet_lip"].apply(
        st, {"lip_len": 4.0, "lip_t": 1.4}, "lap_out")
    RECIPE_OPS["lap_inlet_receiver"].apply(
        st, {"pocket_len": 6.0, "side_clearance": 0.4}, "lap_in")
    return PartForm(
        name=name, params={}, frame=st.frame, section=st.section,
        width=st.width, style=MOLDED_UTILITY_PART, channels=st.channels,
        cutboxes=st.cutboxes, ribs=st.ribs, regions=st.regions,
        datums=st.datums,
    )


def cap_like_form(name="cap") -> PartForm:
    """A part carrying ONLY the outlet half of the fluid contract — what
    the VF-3 inlet cap publishes."""
    form = rail_form(name)
    for key in ("channel_floor_z_inlet", "channel_y_inlet"):
        form.frame.pop(key)
    return form


def fluid(a="rail_a.outlet", b="rail_b.inlet") -> JointUse:
    return JointUse(type="fluid_joint", a=a, b=b, rotate=[0, 0, 0])


def test_flush_datums_encode_no_step():
    """VF correction: rail-to-rail datums mate at dZ = 0 — the cascade
    step is gone from the geometry. The drip joint still verifies (a zero
    fall is not uphill), but rows hand over via lap_flow_joint."""
    a, b = rail_form("rail_a"), rail_form("rail_b")
    joint = fluid()
    pose = compute_pose(joint, a, b)
    assert pose.translate[2] == pytest.approx(0.0)
    assert pose.translate[1] == pytest.approx(-(248.0 + 0.4))
    findings = _fluid_joint_ir(a, b, pose, joint)
    assert findings[0].status.value == "pass", findings[0].message
    assert findings[0].measured == pytest.approx(0.0)


def test_feed_datum_keeps_the_only_fall():
    """The inlet cap's drip tower targets rail.feed — FALL_ENTRY above the
    receiving floor. Mating any outlet onto feed lands the receiver
    exactly that far below: gravity pumps at the row entry, and ONLY
    there."""
    a, b = rail_form("rail_a"), rail_form("rail_b")
    joint = JointUse(type="fluid_joint", a="rail_a.outlet", b="rail_b.feed",
                     rotate=[0, 0, 0])
    pose = compute_pose(joint, a, b)
    assert pose.translate[2] == pytest.approx(-FALL_ENTRY)
    findings = _fluid_joint_ir(a, b, pose, joint)
    assert findings[0].status.value == "pass", findings[0].message
    assert "downhill" in findings[0].message
    assert findings[0].measured == pytest.approx(FALL_ENTRY)


def test_uphill_handover_fails():
    a, b = rail_form("rail_a"), rail_form("rail_b")
    b.datums["inlet"]["at"][2] = a.datums["outlet"]["at"][2] - 20.0  # B lands high
    joint = fluid()
    pose = compute_pose(joint, a, b)
    findings = _fluid_joint_ir(a, b, pose, joint)
    assert findings[0].status.value == "fail"
    assert "UPHILL" in findings[0].message


def test_narrow_receiver_spills():
    a = rail_form("rail_a")
    b = rail_form("rail_b", channel_w=12.0)
    joint = fluid()
    findings = _fluid_joint_ir(a, b, compute_pose(joint, a, b), joint)
    assert findings[0].status.value == "fail"
    assert "spills" in findings[0].message


def test_narrow_giver_into_wide_receiver_is_fine():
    """The adapter case: a 12mm spout hands into the 16mm rail channel."""
    a = rail_form("rail_a", channel_w=12.0)
    b = rail_form("rail_b")
    joint = fluid()
    findings = _fluid_joint_ir(a, b, compute_pose(joint, a, b), joint)
    assert findings[0].status.value == "pass", findings[0].message


def test_wrong_direction_fails_with_actionable_message():
    """a: must carry the OUTLET half; a cap-like part on the b: side lacks
    the inlet keys and the message says exactly what to fix."""
    rail, cap = rail_form("rail"), cap_like_form("cap")
    joint = JointUse(type="fluid_joint", a="rail.inlet", b="cap.outlet",
                     rotate=[0, 0, 0])
    pose = compute_pose(joint, rail, cap)
    findings = _fluid_joint_ir(rail, cap, pose, joint)
    assert findings[0].status.value == "fail"
    assert "OUTLET-carrying part" in findings[0].message
    assert "cap" in findings[0].message


def test_rail_ports_flow_axis_is_minus_y():
    catalog = load_catalog()
    ports = {s.id: s for s in catalog.archetypes["water_rail_v1"].interfaces}
    assert ports["inlet"].frame.axis == "-Y"
    assert ports["outlet"].frame.axis == "-Y"


def test_rail_publishes_corridor_width():
    form = rail_form()
    assert form.frame["corridor_w"] == pytest.approx(20.0)


def _mutate(tmp_path, patch) -> Path:
    doc = yaml.safe_load(CELL.read_text())
    patch(doc)
    out = tmp_path / CELL.name
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return out


def test_misordered_joints_fail_the_ordering_guard(tmp_path):
    def patch(doc):
        doc["joints"] = list(reversed(doc["joints"]))  # snap before insert

    try:
        report = run_assembly_validate(_mutate(tmp_path, patch), None)
    except AssemblyFailure as exc:
        report = exc.report
    poses_msgs = [j["message"] for j in report["joints"]
                  if j["check"] == "assembly.joint_pose"]
    assert any("chain order" in m for m in poses_msgs)


def test_meta_passes_through_to_the_report(tmp_path):
    def patch(doc):
        doc["meta"] = {"row_kind": "tilted_flush_row",
                       "mounting_policy": "tilted_flush_profile"}

    report = run_assembly_validate(_mutate(tmp_path, patch), None)
    assert report["meta"]["row_kind"] == "tilted_flush_row"
