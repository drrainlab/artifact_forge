"""IR unit tests for the vertical farm joints on op-built forms: the
healthy rail+cassette pair seats within the Cassette Interface Standard,
the healthy rail pair lines up — and every surgical desync (loose seat,
flooding window, damming window, off-center channel, flipped module)
fails with a named reason, before any CAD."""

import pytest

from artifact_forge_ng.assembly.joints import (
    _removable_insert_ir,
    _tongue_groove_ir,
    JOINT_TYPES,
    compute_pose,
)
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.assembly import JointUse

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
    RECIPE_OPS["tongue_groove_edges"].apply(
        st, {"tongue_w": 6.0, "tongue_h": 4.0, "tongue_len": 3.6,
             "clearance": 0.4, "z0": 4.0, "bottom_margin": 0.4}, "edges")
    return _to_form(st, name)


def cassette_form(name="cassette", drop=1.5, window_w=12.0) -> PartForm:
    st = RecipeState()
    RECIPE_OPS["substrate_tray_body"].apply(
        st, {"cassette_l": 220.0, "cassette_w": 220.0, "h": 26.0,
             "wall": 2.4, "floor_t": 2.0, "corner_r": 3.0}, "tray")
    RECIPE_OPS["contact_window"].apply(
        st, {"window_w": window_w, "window_l": 60.0, "drop": drop,
             "cx": 0.0, "cy": 0.0}, "window")
    return _to_form(st, name)


def _to_form(st: RecipeState, name: str) -> PartForm:
    return PartForm(
        name=name, params={}, frame=st.frame, section=st.section,
        width=st.width, style=MOLDED_UTILITY_PART, channels=st.channels,
        cutboxes=st.cutboxes, ribs=st.ribs, fields=st.fields,
        regions=st.regions, datums=st.datums,
    )


def seat_joint(**params) -> JointUse:
    return JointUse(type="removable_insert", a="rail.cassette_seat",
                    b="cassette.seat", rotate=[0, 0, 0], params=params)


def line_joint(rotate=(0, 0, 0)) -> JointUse:
    return JointUse(type="tongue_groove", a="rail_a.line_east",
                    b="rail_b.line_west", rotate=list(rotate))


def test_joint_types_registered():
    assert "removable_insert" in JOINT_TYPES
    assert "tongue_groove" in JOINT_TYPES


def test_cassette_seats_in_rail():
    rail, cassette = rail_form(), cassette_form()
    joint = seat_joint()
    pose = compute_pose(joint, rail, cassette)
    findings = _removable_insert_ir(rail, cassette, pose, joint)
    assert all(f.status.value == "pass" for f in findings), findings[0].message
    assert "drain gap" in findings[0].message


def test_loose_seat_fails():
    rail = rail_form(seat_clearance=2.0)  # rail sized for a rattling fit
    cassette = cassette_form()
    joint = seat_joint()
    pose = compute_pose(joint, rail, cassette)
    findings = _removable_insert_ir(rail, cassette, pose, joint)
    assert findings[0].status.value == "fail"
    assert "gap" in findings[0].message


def test_flooding_window_fails():
    rail, cassette = rail_form(), cassette_form(drop=3.5)
    joint = seat_joint()
    pose = compute_pose(joint, rail, cassette)
    findings = _removable_insert_ir(rail, cassette, pose, joint)
    assert findings[0].status.value == "fail"
    assert "reach" in findings[0].message


def test_wide_window_fails_containment():
    rail, cassette = rail_form(), cassette_form(window_w=20.0)
    joint = seat_joint()
    pose = compute_pose(joint, rail, cassette)
    findings = _removable_insert_ir(rail, cassette, pose, joint)
    assert findings[0].status.value == "fail"
    assert "does not fit inside" in findings[0].message


def test_missing_interface_keys_fail():
    rail = rail_form()
    bare = cassette_form()
    bare.frame.pop("window_cx")
    joint = seat_joint()
    pose = compute_pose(joint, rail, bare)
    findings = _removable_insert_ir(rail, bare, pose, joint)
    assert findings[0].status.value == "fail"
    assert "Cassette Interface Standard" in findings[0].message


def test_two_rails_line_up():
    a, b = rail_form("rail_a"), rail_form("rail_b")
    joint = line_joint()
    pose = compute_pose(joint, a, b)
    findings = _tongue_groove_ir(a, b, pose, joint)
    assert all(f.status.value == "pass" for f in findings), findings[0].message
    assert pose.translate[0] == pytest.approx(248.0)


def test_offset_channel_fails_line():
    a = rail_form("rail_a")
    b = rail_form("rail_b")
    b.frame["channel_center_x"] = 2.0  # desynced channel position
    joint = line_joint()
    pose = compute_pose(joint, a, b)
    findings = _tongue_groove_ir(a, b, pose, joint)
    assert findings[0].status.value == "fail"
    assert "centerlines offset" in findings[0].message


def test_flipped_module_fails_line():
    a, b = rail_form("rail_a"), rail_form("rail_b")
    joint = line_joint(rotate=(0, 0, 180))
    pose = compute_pose(joint, a, b)
    findings = _tongue_groove_ir(a, b, pose, joint)
    assert findings[0].status.value == "fail"


def test_tight_groove_fails_line():
    a = rail_form("rail_a")
    b = rail_form("rail_b")
    # rebuild B with a tighter groove
    b2 = RecipeState()
    p = dict(RAIL_PARAMS)
    RECIPE_OPS["water_rail_body"].apply(b2, p, "body")
    RECIPE_OPS["tongue_groove_edges"].apply(
        b2, {"tongue_w": 6.0, "tongue_h": 4.0, "tongue_len": 3.6,
             "clearance": 0.15, "z0": 4.0, "bottom_margin": 0.4}, "edges")
    b = _to_form(b2, "rail_b")
    joint = line_joint()
    pose = compute_pose(joint, a, b)
    findings = _tongue_groove_ir(a, b, pose, joint)
    assert findings[0].status.value == "fail"
    assert "clearance" in findings[0].message
