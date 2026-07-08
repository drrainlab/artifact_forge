"""lap_flow_joint IR (VF correction): two corrected rails mated
outlet-on-inlet land FLUSH — floors coplanar, controlled face gap, lip
3-6 into the through receiver, deliberate tip slot — and every broken
variant fails with a named problem. Plus the MountContextSpec schema:
the machine-checked declaration that the mounted row supplies the slope."""

import pytest

from artifact_forge_ng.assembly.joints import JOINT_TYPES, compute_pose
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.assembly import (
    AssemblyInstance,
    JointUse,
    MountContextSpec,
)
from artifact_forge_ng.product.interfaces import INTERFACE_TYPES

RAIL_PARAMS = dict(
    module_l=248.0, module_w=248.0, body_h=30.0,
    channel_w=16.0, channel_d=5.0, channel_bottom_r=1.2,
    cassette_l=220.0, cassette_w=220.0,
    seat_depth=14.0, seat_clearance=0.75,
    module_pitch=250.0, corner_r=4.0,
    face_gap=0.4, lightweight=True, lw_rib=2.0,
    profile="2020", profile_inset=24.0,
)


def build_rail(name: str, **over) -> PartForm:
    st = RecipeState()
    p = dict(RAIL_PARAMS)
    p.update(over)
    RECIPE_OPS["water_rail_body"].apply(st, p, "body")
    RECIPE_OPS["lap_outlet_lip"].apply(st, {"lip_len": 4.0, "lip_t": 1.4}, "lap_out")
    RECIPE_OPS["lap_inlet_receiver"].apply(
        st, {"pocket_len": 6.0, "side_clearance": 0.4}, "lap_in")
    return PartForm(
        name=name, params={"cassette_l": 220.0, "cassette_w": 220.0},
        frame=st.frame, section=st.section, width=st.width,
        style=MOLDED_UTILITY_PART,
        channels=st.channels, cutboxes=st.cutboxes, bores=st.bores,
        ribs=st.ribs, regions=st.regions, datums=st.datums,
    )


def lap_joint(a: str = "up.outlet", b: str = "down.inlet") -> JointUse:
    return JointUse(type="lap_flow_joint", a=a, b=b, rotate=[0, 0, 0])


def run_lap(form_a: PartForm, form_b: PartForm, joint: JointUse | None = None):
    joint = joint or lap_joint()
    pose = compute_pose(joint, form_a, form_b)
    findings = JOINT_TYPES["lap_flow_joint"].ir_check(form_a, form_b, pose, joint)
    assert len(findings) == 1
    return findings[0], pose


def test_lap_flow_registered_and_realizes_fluid_ports():
    assert "lap_flow_joint" in JOINT_TYPES
    assert "lap_flow_joint" in INTERFACE_TYPES["fluid_inlet"].joints
    assert "lap_flow_joint" in INTERFACE_TYPES["fluid_outlet"].joints
    # the drip joint stays — cap and collector still hand over by falling
    assert "fluid_joint" in INTERFACE_TYPES["fluid_inlet"].joints


def test_flush_pair_passes():
    a, b = build_rail("up"), build_rail("down")
    finding, pose = run_lap(a, b)
    assert finding.status is Status.PASS, finding.message
    # the mate itself: dZ = 0 and the flush pitch march
    assert pose.translate[2] == pytest.approx(0.0, abs=1e-9)
    assert pose.translate[1] == pytest.approx(-(248.0 + 0.4))
    assert "dZ +0.00" in finding.message


def test_wrong_datum_order_named():
    a, b = build_rail("up"), build_rail("down")
    finding, _ = run_lap(a, b, lap_joint(a="up.inlet", b="down.outlet"))
    assert finding.status is Status.FAIL
    assert "upstream OUTLET" in finding.message


def test_missing_lap_keys_named():
    a, b = build_rail("up"), build_rail("down")
    b.frame.pop("lap_pocket_len")
    finding, _ = run_lap(a, b)
    assert finding.status is Status.FAIL
    assert "lap_pocket_len" in finding.message


def test_stair_step_rejected():
    """The old cascade: the downstream rail a step lower — the lap check
    kills exactly the geometry the correction replaced."""
    a, b = build_rail("up"), build_rail("down")
    joint = lap_joint()
    pose = compute_pose(joint, a, b)
    pose = type(pose)(rotate=pose.rotate,
                      translate=(pose.translate[0], pose.translate[1],
                                 pose.translate[2] - 7.91))
    finding = JOINT_TYPES["lap_flow_joint"].ir_check(a, b, pose, joint)[0]
    assert finding.status is Status.FAIL
    assert "stair step" in finding.message or "not coplanar" in finding.message


def test_face_gap_out_of_band_rejected():
    a = build_rail("up", face_gap=0.6)
    b = build_rail("down", face_gap=0.6)
    joint = lap_joint()
    pose = compute_pose(joint, a, b)
    # push the modules 1.0 apart — outside 0.3..0.6
    pose = type(pose)(rotate=pose.rotate,
                      translate=(pose.translate[0], pose.translate[1] - 0.4,
                                 pose.translate[2]))
    finding = JOINT_TYPES["lap_flow_joint"].ir_check(a, b, pose, joint)[0]
    assert finding.status is Status.FAIL
    assert "face gap" in finding.message


def test_short_lip_rejected():
    a, b = build_rail("up"), build_rail("down")
    a.frame["lap_lip_len"] = 3.0  # overlap 2.6 < 3.0
    finding, _ = run_lap(a, b)
    assert finding.status is Status.FAIL
    assert "overlap" in finding.message


def test_tight_receiver_rejected():
    a, b = build_rail("up"), build_rail("down")
    b.frame["lap_pocket_w"] = a.frame["lap_lip_w"] + 0.2  # 0.1/side
    finding, _ = run_lap(a, b)
    assert finding.status is Status.FAIL
    assert "clearance" in finding.message


def test_sealed_slot_rejected():
    """A pocket barely longer than the overlap closes the deliberate seam
    slot — hermetic module joints are forbidden BY DESIGN, including by
    accident."""
    a, b = build_rail("up"), build_rail("down")
    b.frame["lap_pocket_len"] = 3.9  # slot 0.3 < 0.5
    finding, _ = run_lap(a, b)
    assert finding.status is Status.FAIL
    assert "slot" in finding.message


def test_narrow_receiver_channel_rejected():
    a = build_rail("up")
    b = build_rail("down", channel_w=14.0)
    finding, _ = run_lap(a, b)
    assert finding.status is Status.FAIL
    assert "narrower" in finding.message


# -- MountContextSpec: the mount IS the slope ---------------------------------


def _asm_body(mount=None) -> dict:
    body = {
        "schema": "assembly/v1",
        "id": "t",
        "root": "a",
        "parts": [
            {"ref": "a", "product": _product("a")},
            {"ref": "b", "product": _product("b")},
        ],
        "joints": [{"type": "lap_flow_joint", "a": "a.outlet", "b": "b.inlet",
                    "rotate": [0, 0, 0]}],
    }
    if mount is not None:
        body["mount_context"] = mount
    return body


def _product(pid: str) -> dict:
    return {
        "schema": "product/v1", "id": pid,
        "archetype": "water_rail_v1@2", "params": {},
        "manufacturing": {"material": "PETG", "support_policy": "none"},
    }


def test_mount_context_parses():
    asm = AssemblyInstance.model_validate(
        _asm_body({"type": "tilted_flush_row", "slope_deg": 1.5,
                   "slope_source": "mounted straight 2020 profile"}))
    assert isinstance(asm.mount_context, MountContextSpec)
    assert asm.mount_context.slope_deg == 1.5
    assert asm.mount_context.slope_axis == "Y"
    assert asm.mount_context.slope_direction == "inlet_to_outlet"


def test_mount_context_optional():
    asm = AssemblyInstance.model_validate(_asm_body())
    assert asm.mount_context is None


def test_mount_context_schema_band():
    with pytest.raises(Exception, match="0..3"):
        AssemblyInstance.model_validate(
            _asm_body({"type": "tilted_flush_row", "slope_deg": 5.0}))


def test_mount_context_type_is_closed():
    with pytest.raises(Exception):
        AssemblyInstance.model_validate(
            _asm_body({"type": "wall_wedge", "slope_deg": 1.5}))
