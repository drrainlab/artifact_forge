"""VF-3 adapters at the IR level: the op-built inlet cap and collector
pass their own checks, the full fluid chain cap -> rail -> collector poses
downhill, and saddle_hang verifies the physical hang in the same pose —
while never satisfying a fluid port (auxiliary verification joint)."""

import pytest

from artifact_forge_ng.assembly.joints import (
    _fluid_joint_ir,
    _saddle_hang_ir,
    JOINT_TYPES,
    compute_pose,
)
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_water import (
    check_collector_drain_bore_supportless,
    check_collector_receiver_matches_final_lap,
    check_collector_tray_drains,
    check_hose_bore_ok,
    check_no_standing_water_ir,
    check_receiver_open_top_cleanable,
    check_spout_drop_path_ok,
)
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.assembly import JointUse
from artifact_forge_ng.product.interfaces import INTERFACE_TYPES

RAIL_PARAMS = dict(
    module_l=248.0, module_w=248.0, body_h=30.0,
    channel_w=16.0, channel_d=5.0, channel_bottom_r=1.2,
    cassette_l=220.0, cassette_w=220.0,
    seat_depth=14.0, seat_clearance=0.75,
    module_pitch=250.0, corner_r=4.0,
)

CAP_PARAMS = dict(
    cap_w=64.0, cap_h=22.0, tube_od=9.0, bore_clearance=0.4,
    rail_wall_t=13.25, saddle_fit=0.4, saddle_depth=8.0,
    hang_drop=16.5, spout_w=14.0, rail_channel_w=16.0, corner_r=3.0,
)

COLLECTOR_PARAMS = dict(
    tray_w=20.0, tube_od=9.0, bore_clearance=0.4,
    rail_wall_t=13.25, saddle_fit=0.4, hang_drop=20.4,
    tongue_w=14.0, rail_channel_w=16.0, tray_slope_deg=1.5,
    catch_fall=8.5, lip_overhang=4.0, capture_depth=8.0, corner_r=3.0,
)


def _to_form(st: RecipeState, name: str) -> PartForm:
    return PartForm(
        name=name, params={}, frame=st.frame, section=st.section,
        width=st.width, style=MOLDED_UTILITY_PART, channels=st.channels,
        cutboxes=st.cutboxes, bores=st.bores, ribs=st.ribs,
        regions=st.regions, datums=st.datums,
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
    return _to_form(st, name)


def cap_form(name="cap", **over) -> PartForm:
    st = RecipeState()
    p = dict(CAP_PARAMS)
    p.update(over)
    RECIPE_OPS["inlet_cap_body"].apply(st, p, "cap")
    return _to_form(st, name)


def collector_form(name="collector", **over) -> PartForm:
    st = RecipeState()
    p = dict(COLLECTOR_PARAMS)
    p.update(over)
    RECIPE_OPS["collector_endcap_body"].apply(st, p, "collector")
    return _to_form(st, name)


# -- op outputs pass their own checks -----------------------------------------

def test_cap_op_satisfies_checks():
    form = cap_form()
    for check in (check_hose_bore_ok, check_spout_drop_path_ok,
                  check_no_standing_water_ir):
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)
    assert "spout" in form.datums and "tube_in" in form.datums


def test_collector_op_satisfies_checks():
    form = collector_form()
    for check in (check_hose_bore_ok, check_collector_tray_drains,
                  check_collector_receiver_matches_final_lap,
                  check_receiver_open_top_cleanable,
                  check_collector_drain_bore_supportless,
                  check_no_standing_water_ir):
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)
    assert "catch" in form.datums and "drain_out" in form.datums


# -- VF-4.1: the collector is an end receiver ---------------------------------


def test_narrow_mouth_rejected():
    form = collector_form()
    form.frame["receiver_mouth_w"] = form.frame["receiver_lip_w"] + 1.0
    f = check_collector_receiver_matches_final_lap(form)
    assert f.status is Status.FAIL and "envelope" in f.message


def test_shallow_capture_rejected():
    form = collector_form()
    form.frame["receiver_capture_depth"] = 5.0
    f = check_collector_receiver_matches_final_lap(form)
    assert f.status is Status.FAIL


def test_lip_tip_too_close_to_apron_rejected():
    form = collector_form()
    form.frame["receiver_lip_overhang"] = 7.0  # 1.0 to the apron < 2
    f = check_collector_receiver_matches_final_lap(form)
    assert f.status is Status.FAIL and "apron" in f.message


def test_capture_depth_band_enforced_at_op():
    from artifact_forge_ng.form.recipe_ops import RecipeError
    with pytest.raises(RecipeError):
        collector_form(capture_depth=5.0)
    with pytest.raises(RecipeError):
        collector_form(capture_depth=8.0, lip_overhang=6.5)  # tip margin < 2


def test_ceiling_over_capture_zone_rejected():
    from artifact_forge_ng.form.part import RibFeature
    from artifact_forge_ng.form.regions import Box3
    form = collector_form()
    dz = form.frame["handover_dz"]
    form.ribs.append(RibFeature("bridge", Box3(-8.0, -6.0, dz + 5.0,
                                               8.0, -2.0, dz + 8.0)))
    f = check_receiver_open_top_cleanable(form)
    assert f.status is Status.FAIL and "roofs the capture zone" in f.message


def test_wall_apron_rejected():
    form = collector_form()
    form.frame["receiver_apron_z"] = 6.0  # a wall, not a curb
    f = check_receiver_open_top_cleanable(form)
    assert f.status is Status.FAIL and "biofilm" in f.message


def test_round_horizontal_drain_rejected():
    from dataclasses import replace
    form = collector_form()
    form.bores[:] = [replace(b, roof="round") for b in form.bores]
    f = check_collector_drain_bore_supportless(form)
    assert f.status is Status.FAIL and "sags" in f.message


def test_cap_refuses_wide_spout():
    from artifact_forge_ng.form.recipe_ops import RecipeError
    with pytest.raises(RecipeError):
        cap_form(spout_w=15.0)


# -- the fluid chain ------------------------------------------------------------

def test_cap_feeds_rail_downhill():
    """The cap targets the FEED port — the only surviving fall in the
    corrected row."""
    cap, rail = cap_form(), rail_form()
    joint = JointUse(type="fluid_joint", a="cap.spout", b="rail.feed",
                     rotate=[0, 0, 0])
    pose = compute_pose(joint, cap, rail)
    findings = _fluid_joint_ir(cap, rail, pose, joint)
    assert findings[0].status.value == "pass", findings[0].message
    # narrow spout into the wide rail channel — the receiver rule
    assert cap.frame["channel_w"] < rail.frame["channel_w"]


def test_rail_feeds_collector_downhill():
    """The collector catches at the LAST rail's drain_edge — the lap lip
    tip. Water leaves the lip TOP (the floor plane) and falls
    catch_fall + lip_t to the tray floor."""
    rail, coll = rail_form(), collector_form()
    joint = JointUse(type="fluid_joint", a="rail.drain_edge", b="collector.catch",
                     rotate=[0, 0, 0])
    pose = compute_pose(joint, rail, coll)
    findings = _fluid_joint_ir(rail, coll, pose, joint)
    assert findings[0].status.value == "pass", findings[0].message
    assert findings[0].measured == pytest.approx(8.5 + 1.4, abs=0.01)


# -- saddle_hang ------------------------------------------------------------------

def test_saddle_hang_is_auxiliary():
    """The verification joint must never realize a fluid port."""
    assert "saddle_hang" in JOINT_TYPES
    assert "saddle_hang" not in INTERFACE_TYPES["fluid_inlet"].joints
    assert "saddle_hang" not in INTERFACE_TYPES["fluid_outlet"].joints


def test_cap_saddle_hangs_on_back_wall():
    rail, cap = rail_form(), cap_form()
    joint = JointUse(type="saddle_hang", a="rail.feed", b="cap.spout",
                     rotate=[0, 0, 0])
    pose = compute_pose(joint, rail, cap)
    findings = _saddle_hang_ir(rail, cap, pose, joint)
    assert findings[0].status.value == "pass", findings[0].message
    assert "straddles" in findings[0].message


def test_collector_saddle_hangs_on_front_wall():
    rail, coll = rail_form(), collector_form()
    joint = JointUse(type="saddle_hang", a="rail.drain_edge", b="collector.catch",
                     rotate=[0, 0, 0])
    pose = compute_pose(joint, rail, coll)
    findings = _saddle_hang_ir(rail, coll, pose, joint)
    assert findings[0].status.value == "pass", findings[0].message


def test_wrong_wall_thickness_fails_saddle():
    """A cap built for a thinner wall no longer straddles this rail."""
    rail = rail_form()
    cap = cap_form(rail_wall_t=9.0)
    joint = JointUse(type="saddle_hang", a="rail.feed", b="cap.spout",
                     rotate=[0, 0, 0])
    pose = compute_pose(joint, rail, cap)
    findings = _saddle_hang_ir(rail, cap, pose, joint)
    assert findings[0].status.value == "fail"
    assert "straddle" in findings[0].message


def test_floating_saddle_fails():
    """A cap with a mismatched hang_drop floats above the wall top."""
    rail = rail_form()
    cap = cap_form(hang_drop=12.0)
    joint = JointUse(type="saddle_hang", a="rail.feed", b="cap.spout",
                     rotate=[0, 0, 0])
    pose = compute_pose(joint, rail, cap)
    findings = _saddle_hang_ir(rail, cap, pose, joint)
    assert findings[0].status.value == "fail"
    assert "floats or clips" in findings[0].message
