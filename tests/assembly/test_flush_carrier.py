"""Flush-row carrier checks (VF correction), unit-level on hand-posed
states: one plane + flush pitch, drainage proven against the declared
mount (missing / out-of-band / reversed FAILS), FULL seating on straight
profiles (span gap zero is a check, not a note), magnet coaxiality and
the cassette-removability rollup."""

import math
from types import SimpleNamespace

import pytest

from artifact_forge_ng.assembly.carrier import carrier_findings
from artifact_forge_ng.assembly.joints import Pose
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.assembly import JointUse, MountContextSpec

FLUSH_PITCH = 248.4


def rail_form(name: str, magnets: bool = False) -> PartForm:
    st = RecipeState()
    p = dict(
        module_l=248.0, module_w=248.0, body_h=30.0,
        channel_w=16.0, channel_d=5.0, channel_bottom_r=1.2,
        cassette_l=220.0, cassette_w=220.0,
        seat_depth=14.0, seat_clearance=0.75,
        module_pitch=250.0, corner_r=4.0, face_gap=0.4,
    )
    RECIPE_OPS["water_rail_body"].apply(st, p, "body")
    RECIPE_OPS["lap_outlet_lip"].apply(st, {"lip_len": 4.0, "lip_t": 1.4}, "lap_out")
    RECIPE_OPS["lap_inlet_receiver"].apply(
        st, {"pocket_len": 6.0, "side_clearance": 0.4}, "lap_in")
    RECIPE_OPS["edge_magnet_pockets"].apply(
        st, {"enabled": magnets, "magnet_d": 6.0, "magnet_t": 2.0,
             "fit_clearance": 0.2, "x_offset": 60.0, "z_center": 8.0}, "magnets")
    RECIPE_OPS["profile_seat_slot"].apply(
        st, {"profile": "2020", "clearance": 0.2, "depth": 6.0, "inset": 24.0},
        "profile_slots")
    return PartForm(
        name=name, params={}, frame=st.frame, section=st.section,
        width=st.width, style=MOLDED_UTILITY_PART, channels=st.channels,
        cutboxes=st.cutboxes, bores=st.bores, ribs=st.ribs,
        regions=st.regions, datums=st.datums,
    )


def profile_form(name: str, stations: int = 3) -> PartForm:
    st = RecipeState()
    RECIPE_OPS["profile_ref_body"].apply(
        st, {"size": "2020", "length": 780.0, "slope_deg": 0.0,
             "station_pitch": FLUSH_PITCH, "stations": stations,
             "station_edge": 20.0}, "profile")
    return PartForm(
        name=name, params={}, frame=st.frame, section=st.section,
        width=st.width, style=MOLDED_UTILITY_PART, channels=st.channels,
        cutboxes=st.cutboxes, regions=st.regions, datums=st.datums,
    )


def _state(form: PartForm, object_class: str) -> SimpleNamespace:
    return SimpleNamespace(
        form=form,
        archetype=SimpleNamespace(object_class=object_class, interfaces=[]),
    )


def make_row(*, magnets: bool = False, mount=MountContextSpec(
        type="tilted_flush_row", slope_deg=1.5),
        dz_2: float = 0.0, pitch: float = FLUSH_PITCH,
        with_profiles: bool = True, profile_dz: float = 0.0):
    """Three flush rails (rail_1 at origin, marching -Y), optionally two
    straight profiles seated under the groove datums."""
    states = {
        f"rail_{k}": _state(rail_form(f"rail_{k}", magnets), "water_rail")
        for k in (1, 2, 3)
    }
    poses = {
        "rail_1": Pose(rotate=(0, 0, 0), translate=(0.0, 0.0, 0.0)),
        "rail_2": Pose(rotate=(0, 0, 0), translate=(0.0, -pitch, dz_2)),
        "rail_3": Pose(rotate=(0, 0, 0), translate=(0.0, -2.0 * pitch, 0.0)),
    }
    joints = [
        JointUse(type="lap_flow_joint", a="rail_1.outlet", b="rail_2.inlet",
                 rotate=[0, 0, 0]),
        JointUse(type="lap_flow_joint", a="rail_2.outlet", b="rail_3.inlet",
                 rotate=[0, 0, 0]),
    ]
    parts = [SimpleNamespace(ref=r) for r in states]
    if with_profiles:
        for label, sign in (("e", 1.0), ("w", -1.0)):
            ref = f"profile_{label}"
            states[ref] = _state(profile_form(ref), "hardware_reference")
            parts.append(SimpleNamespace(ref=ref))
            # seat datum: x = +-100, y = 123.5, z = 6 (slot depth). station_1
            # at profile-local y = 370, z = 20. Full seating => profile top
            # (20 + tz) == seat z (6): tz = -14; align station under seat.
            poses[ref] = Pose(rotate=(0, 0, 0),
                              translate=(sign * 100.0, 123.5 - 370.0,
                                         -14.0 + profile_dz))
            for k in (1, 2, 3):
                joints.append(JointUse(
                    type="profile_perch",
                    a=f"rail_{k}.seat_{label}", b=f"{ref}.ridge_{k}",
                    rotate=[0, 0, 0]))
    asm = SimpleNamespace(parts=parts, joints=joints, mount_context=mount,
                          meta={})
    return asm, states, poses


def by_check(findings) -> dict:
    return {f.check: f for f in findings}


def test_flush_row_all_green():
    asm, states, poses = make_row()
    checks = by_check(carrier_findings(asm, states, poses))
    for name in ("assembly.row_flush_aligned", "assembly.row_drains_under_mount",
                 "assembly.profile_support_full_length",
                 "assembly.magnet_alignment_ok"):
        assert checks[name].status is Status.PASS, (name, checks[name].message)
    assert "no standing water" in checks["assembly.row_drains_under_mount"].message


def test_stair_step_fails_flush():
    asm, states, poses = make_row(dz_2=-7.91)
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.row_flush_aligned"].status is Status.FAIL
    assert "stair step" in checks["assembly.row_flush_aligned"].message


def test_wrong_pitch_fails_flush():
    asm, states, poses = make_row(pitch=250.0)
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.row_flush_aligned"].status is Status.FAIL
    assert "flush pitch" in checks["assembly.row_flush_aligned"].message


def test_missing_mount_context_fails_drainage():
    asm, states, poses = make_row(mount=None)
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.row_drains_under_mount"]
    assert f.status is Status.FAIL
    assert "mount_context" in f.message


@pytest.mark.parametrize("slope", [0.5, 2.5])
def test_out_of_band_mount_fails(slope):
    asm, states, poses = make_row(mount=MountContextSpec(
        type="tilted_flush_row", slope_deg=slope))
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.row_drains_under_mount"].status is Status.FAIL


@pytest.mark.parametrize("slope", [1.0, 2.0])
def test_band_edges_pass(slope):
    asm, states, poses = make_row(mount=MountContextSpec(
        type="tilted_flush_row", slope_deg=slope))
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.row_drains_under_mount"].status is Status.PASS


def test_reversed_row_fails_drainage():
    """Rails marching +Y (against the declared inlet_to_outlet fall):
    the virtual path climbs and the check names it."""
    asm, states, poses = make_row(with_profiles=False)
    poses["rail_2"] = Pose(rotate=(0, 0, 0), translate=(0.0, FLUSH_PITCH, 0.0))
    poses["rail_3"] = Pose(rotate=(0, 0, 0), translate=(0.0, 2 * FLUSH_PITCH, 0.0))
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.row_drains_under_mount"]
    assert f.status is Status.FAIL
    assert "climbs" in f.message


def test_total_virtual_drop_matches_geometry():
    asm, states, poses = make_row()
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.row_drains_under_mount"]
    span = 2 * FLUSH_PITCH + 248.0  # first inlet face to last outlet face
    assert f.measured == pytest.approx(span * math.tan(math.radians(1.5)), abs=0.1)


def test_floating_rail_fails_full_seating():
    asm, states, poses = make_row(profile_dz=-1.0)  # profiles drop 1mm
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.profile_support_full_length"]
    assert f.status is Status.FAIL
    assert "full seating broken" in f.message


def test_sloped_profile_model_rejected():
    asm, states, poses = make_row()
    states["profile_e"].form.frame["profile_slope_deg"] = 1.827
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.profile_support_full_length"]
    assert f.status is Status.FAIL
    assert "STANDARD STRAIGHT" in f.message


def test_unperched_rail_fails():
    asm, states, poses = make_row()
    asm.joints = [j for j in asm.joints if j.a != "rail_2.seat_e"]
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.profile_support_full_length"].status is Status.FAIL


def test_magnets_aligned_and_mutated():
    asm, states, poses = make_row(magnets=True)
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.magnet_alignment_ok"]
    assert f.status is Status.PASS
    assert "4 magnet pair(s)" in f.message
    # shift one rail's pockets — coaxiality breaks
    states["rail_2"].form.frame["magnet_x_offset"] = 62.0
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.magnet_alignment_ok"].status is Status.FAIL


def test_magnets_absent_is_na_pass():
    asm, states, poses = make_row(magnets=False)
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.magnet_alignment_ok"]
    assert f.status is Status.PASS
    assert "nothing to align" in f.message


def test_no_row_joints_no_story():
    asm, states, poses = make_row(with_profiles=False)
    asm.joints = []
    assert carrier_findings(asm, states, poses) == []


# -- VF-4.1: the collector is an END RECEIVER (pose truths) ---------------------


def collector_form(name: str = "collector", **over) -> PartForm:
    st = RecipeState()
    p = dict(
        tray_w=20.0, tube_od=9.0, bore_clearance=0.4,
        rail_wall_t=13.25, saddle_fit=0.4, hang_drop=20.4,
        tongue_w=14.0, rail_channel_w=16.0, tray_slope_deg=1.5,
        catch_fall=8.5, lip_overhang=4.0, capture_depth=8.0, corner_r=3.0,
    )
    p.update(over)
    RECIPE_OPS["collector_endcap_body"].apply(st, p, "collector")
    return PartForm(
        name=name, params={"catch_fall": p["catch_fall"]}, frame=st.frame,
        section=st.section, width=st.width, style=MOLDED_UTILITY_PART,
        channels=st.channels, cutboxes=st.cutboxes, bores=st.bores,
        ribs=st.ribs, regions=st.regions, datums=st.datums,
    )


def make_row_with_collector(*, shift_x: float = 0.0, shift_y: float = 0.0):
    asm, states, poses = make_row(with_profiles=False)
    form = collector_form()
    states["collector"] = _state(form, "water_collector")
    asm.parts.append(SimpleNamespace(ref="collector"))
    # mate catch onto rail_3.drain_edge (rail_3 at y = -2*pitch, z = 0)
    rail_3 = states["rail_3"].form
    drain = rail_3.datums["drain_edge"]["at"]
    catch = form.datums["catch"]["at"]
    poses["collector"] = Pose(rotate=(0, 0, 0), translate=(
        drain[0] - catch[0] + shift_x,
        drain[1] - catch[1] - 2 * FLUSH_PITCH + shift_y,
        drain[2] - catch[2]))
    return asm, states, poses


def test_collector_captures_final_lip():
    asm, states, poses = make_row_with_collector()
    checks = by_check(carrier_findings(asm, states, poses))
    cap = checks["assembly.collector_captures_drain_edge"]
    assert cap.status is Status.PASS, cap.message
    assert "end receiver" in cap.message
    env = checks["assembly.collector_mouth_envelopes_outlet_lip"]
    assert env.status is Status.PASS, env.message
    rem = checks["assembly.collector_removable_by_hand"]
    assert rem.status is Status.PASS, rem.message


def test_shifted_collector_fails_capture():
    """Pull the collector 4 outward: the lip tip leaves the mouth."""
    asm, states, poses = make_row_with_collector(shift_y=-4.5)
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.collector_captures_drain_edge"].status is Status.FAIL


def test_offset_collector_fails_envelope():
    asm, states, poses = make_row_with_collector(shift_x=2.0)
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.collector_mouth_envelopes_outlet_lip"].status is Status.FAIL


def test_roofed_lip_fails_removable():
    from artifact_forge_ng.form.part import RibFeature
    from artifact_forge_ng.form.regions import Box3
    asm, states, poses = make_row_with_collector()
    coll = states["collector"].form
    dz = coll.frame["handover_dz"]
    coll.ribs.append(RibFeature("cap_bar", Box3(-8.0, -3.5, dz + 6.0,
                                                8.0, -0.5, dz + 9.0)))
    checks = by_check(carrier_findings(asm, states, poses))
    assert checks["assembly.collector_removable_by_hand"].status is Status.FAIL


def test_no_collector_no_capture_findings():
    asm, states, poses = make_row(with_profiles=False)
    checks = by_check(carrier_findings(asm, states, poses))
    assert "assembly.collector_captures_drain_edge" not in checks


# -- VF-5: the collector catches the root-chamber drainage ---------------------


def root_chamber_rail(name: str) -> PartForm:
    st = RecipeState()
    p = dict(
        module_l=248.0, module_w=248.0, body_h=30.0,
        channel_w=16.0, channel_d=5.0, channel_bottom_r=1.2,
        cassette_l=220.0, cassette_w=220.0, seat_depth=14.0, seat_clearance=0.75,
        module_pitch=250.0, corner_r=4.0, face_gap=0.4,
        under_cassette="root_chamber", trough_w=26.0, trough_rib=6.0, trough_depth=12.0,
    )
    RECIPE_OPS["water_rail_body"].apply(st, p, "body")
    RECIPE_OPS["lap_outlet_lip"].apply(st, {"lip_len": 4.0, "lip_t": 1.4}, "lap_out")
    RECIPE_OPS["lap_inlet_receiver"].apply(
        st, {"pocket_len": 6.0, "side_clearance": 0.4}, "lap_in")
    return PartForm(
        name=name, params={}, frame=st.frame, section=st.section, width=st.width,
        style=MOLDED_UTILITY_PART, channels=st.channels, cutboxes=st.cutboxes,
        bores=st.bores, ribs=st.ribs, regions=st.regions, datums=st.datums)


def _row_with_collector(collector: PartForm):
    rail = root_chamber_rail("rail_1")
    states = {"rail_1": _state(rail, "water_rail"),
              "collector": _state(collector, "water_collector")}
    poses = {"rail_1": Pose(rotate=(0, 0, 0), translate=(0.0, 0.0, 0.0))}
    drain = rail.datums["drain_edge"]["at"]
    catch = collector.datums["catch"]["at"]
    poses["collector"] = Pose(rotate=(0, 0, 0), translate=(
        drain[0] - catch[0], drain[1] - catch[1], drain[2] - catch[2]))
    asm = SimpleNamespace(
        parts=[SimpleNamespace(ref="rail_1"), SimpleNamespace(ref="collector")],
        joints=[JointUse(type="lap_flow_joint", a="rail_1.outlet", b="rail_1.inlet",
                         rotate=[0, 0, 0])],  # a dummy lap so carrier engages
        mount_context=MountContextSpec(type="tilted_flush_row", slope_deg=1.5),
        meta={})
    return asm, states, poses


def test_wide_collector_catches_root_drainage():
    asm, states, poses = _row_with_collector(collector_form(tray_w=170.0))
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.collector_catches_root_drainage"]
    assert f.status is Status.PASS, f.message
    assert "lands in the tray" in f.message


def test_narrow_collector_spills_root_drainage():
    asm, states, poses = _row_with_collector(collector_form(tray_w=20.0))
    checks = by_check(carrier_findings(asm, states, poses))
    f = checks["assembly.collector_catches_root_drainage"]
    assert f.status is Status.FAIL and "spills" in f.message


def test_skeleton_rail_no_root_drainage_check():
    asm, states, poses = make_row_with_collector()  # skeleton rails
    checks = by_check(carrier_findings(asm, states, poses))
    assert "assembly.collector_catches_root_drainage" not in checks
