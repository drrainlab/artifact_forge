"""VF-3.0 core: the fluid cascade physics on op-built rails (datum-on-datum
handover drops the downstream part below the upstream lip), the actionable
wrong-direction message, the receiver-width rule, the joint ordering guard
and the assembly meta passthrough."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.joints import _fluid_joint_ir, compute_pose
from artifact_forge_ng.assembly.pipeline import (
    AssemblyFailure,
    run_assembly_validate,
)
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState
from artifact_forge_ng.form.recipe_ops_water import FALL_ENTRY
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.assembly import JointUse

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
CELL = EXAMPLES / "water_rail_cell_2020_petg.yaml"

RAIL_PARAMS = dict(
    module_l=248.0, module_w=248.0, body_h=30.0,
    channel_w=16.0, channel_d=5.0, slope_deg=1.25, channel_bottom_r=1.2,
    cassette_l=220.0, cassette_w=220.0,
    seat_depth=14.0, seat_clearance=0.75,
    module_pitch=250.0, corner_r=4.0,
)


def rail_form(name="rail", **over) -> PartForm:
    st = RecipeState()
    p = dict(RAIL_PARAMS)
    p.update(over)
    RECIPE_OPS["water_rail_body"].apply(st, p, "body")
    RECIPE_OPS["overflow_lip"].apply(
        st, {"lip_h": 2.0, "air_gap": 1.5, "lip_r": 0.4}, "lip")
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


def test_cascade_datums_encode_the_step():
    """outlet datum = the lip, inlet datum = receiving floor + FALL_ENTRY —
    mating them puts the downstream rail one cascade step lower."""
    a, b = rail_form("rail_a"), rail_form("rail_b")
    joint = fluid()
    pose = compute_pose(joint, a, b)
    # drop = z(outlet datum) - z(inlet datum) = 5.59 - 13.5 = -7.91
    expected = (a.datums["outlet"]["at"][2] - b.datums["inlet"]["at"][2])
    assert pose.translate[2] == pytest.approx(expected)
    assert pose.translate[2] < -5.0  # a real step DOWN
    findings = _fluid_joint_ir(a, b, pose, joint)
    assert findings[0].status.value == "pass", findings[0].message
    assert "downhill" in findings[0].message
    # the downhill margin is exactly FALL_ENTRY by construction
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
        doc["meta"] = {"row_kind": "fluid_cascade",
                       "mounting_policy": "not_final_rack"}

    report = run_assembly_validate(_mutate(tmp_path, patch), None)
    assert report["meta"]["row_kind"] == "fluid_cascade"
