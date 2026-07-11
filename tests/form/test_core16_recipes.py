"""Core-expansion wave (Core-U/M/X): every new archetype builds from its
example through the pre-CAD pipeline with zero FAIL findings, plus the
sharp per-family edges that guard the new ops."""
from __future__ import annotations

from pathlib import Path

import pytest

from artifact_forge_ng.form.checks_cuts import check_cuts_respect_keepouts
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"

WAVE_EXAMPLES = [
    # stage 1
    "foot_m6_square_40",
    "foot_m8_round_50",
    "bench_leveling_foot_m8",
    "angle_bracket_40x40",
    "angle_bracket_60x40_gusset",
    "shelf_corner_25x25_m3",
    "rpi4_tray",
    "esp32_devkit_tray",
    "proto_tray_90x70",
    "strap_mount_25mm",
    "strap_mount_50mm",
    # stage 2
    "kitchen_drawer_bin_3cell",
    "desk_drawer_bin_4cell",
    "screw_bin_small",
    "light_chain_spool_100",
    "wire_spool_60",
    "herb_pot_90",
    "floor_pot_180",
    "net_pot_50",
    "net_pot_75",
    "net_pot_100",
    "squircle_pot_110",
    "window_box_pot_180",
    # stage 3
    "star_knob_m5_40",
    "jig_knob_m6_50",
    "camera_knob_quarter20",
    "dowel_guide_8mm_3hole",
    "shelf_pin_guide_5mm",
    "cell_holder_18650_2x2",
    "cell_holder_aa_1x4",
    "cell_holder_21700_1x3",
    "pegboard_base_single_hook",
    "pegboard_base_metric_plate",
    "trellis_tee_8mm",
    "trellis_cross_10mm",
    "trellis_elbow_6mm",
    "trellis_a_frame_8mm",
    "maker_initials_stamp",
    "leather_stamp_gb",
    "clay_pattern_stamp",
    "logo_stamp_arrow",
    # deferral wave
    "tank_plug_m20",
    "tank_plug_m12",
    "tank_port_plate_m20",
    "ratchet_wheel_40_24t",
    "ratchet_wheel_60_36t_round",
    "coupler_5_8_stepper",
    "coupler_6_6_long",
    "card_case_blank_120",
    "glasses_pouch_blank_160",
    "rail_slider_camera_16",
    "rail_slider_branch_20",
    "hinge_leaf_a_60",
    "hinge_leaf_b_60",
    "friction_hinge_leaf_m5",
    "cup_holder_post_20",
    "cup_holder_post_25_tall",
    "step_drill_guide_8_5",
    "chair_foot_press_25x2",
    "stool_foot_press_19x1.5",
    "table_foot_press_30x2",
    # stage 4
    "hose_tee_12mm",
    "hose_elbow_12mm",
    "hose_cross_10mm",
    "reducing_tee_16_12",
    "rod_clamp_15mm_lower",
    "rod_clamp_15mm_upper",
    "mic_boom_clamp_19mm_lower",
    "rod_clamp_15mm_quarter20_lower",
]


@pytest.mark.parametrize("example", WAVE_EXAMPLES)
def test_example_builds_with_zero_fails(example):
    state = run_pre_cad(EXAMPLES / f"{example}.yaml", None)
    fails = [f for f in state.report.findings if f.status.value == "fail"]
    assert fails == [], "; ".join(f"{f.check}: {f.message}" for f in fails)


# -- furniture foot -------------------------------------------------------------


def test_foot_nut_trap_deeper_than_pad_refused():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 40.0, "w": 40.0, "t": 7.0, "corner_r": 4.0}, "pad")
    with pytest.raises(RecipeError, match="deeper than the plate"):
        RECIPE_OPS["nut_trap"].apply(
            st, {"screw": "M8", "clearance": 0.25, "cx": 0.0, "cy": 0.0}, "nut")


def test_foot_example_publishes_nut_af():
    state = run_pre_cad(EXAMPLES / "foot_m8_round_50.yaml", None)
    # m8 across-flats 13 + 2 * 0.25 clearance
    assert state.form.frame["leg_nut_af"] == pytest.approx(13.5)


def test_press_foot_fit_measured():
    from artifact_forge_ng.form.checks_pots import check_foot_press_fit_ok

    state = run_pre_cad(EXAMPLES / "chair_foot_press_25x2.yaml", None)
    f = state.form.frame
    assert f["foot_spigot_d"] == pytest.approx(21.25)  # tube_id + press
    assert check_foot_press_fit_ok(state.form).status.value == "pass"
    assert "tube_axis" in state.form.datums


def test_press_foot_loose_spigot_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="press"):
        RECIPE_OPS["foot_body"].apply(
            st, {"pad_d": 40.0, "pad_t": 8.0, "tube_id": 21.0, "press": 0.02,
                 "spigot_l": 0.0, "pad_recess_d": 0.0, "pad_recess_t": 0.8},
            "foot")


def test_press_foot_short_spigot_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="rocks out"):
        RECIPE_OPS["foot_body"].apply(
            st, {"pad_d": 40.0, "pad_t": 8.0, "tube_id": 21.0, "press": 0.25,
                 "spigot_l": 6.0, "pad_recess_d": 0.0, "pad_recess_t": 0.8},
            "foot")


# -- hinge leaves --------------------------------------------------------------------


def _leaf(**over) -> RecipeState:
    st = RecipeState()
    p = {"leaf_l": 60.0, "leaf_w": 25.0, "t": 3.0, "corner_r": 3.0,
         "knuckle_d": 8.0, "knuckles": 5, "side": "a", "mode": "pin",
         "gap": 0.4, "pin_d": 3.0, "pin_clearance": 0.35, "screw": "m4"}
    p.update(over)
    RECIPE_OPS["hinge_leaf"].apply(st, p, "leaf")
    return st


def test_hinge_sides_interleave_complementarily():
    a, b = _leaf(side="a"), _leaf(side="b")
    assert a.frame["hinge_knuckles_mine"] == 3.0
    assert b.frame["hinge_knuckles_mine"] == 2.0
    ax = sorted(p.z0 for p in a.pins)
    bx = sorted(p.z0 for p in b.pins)
    # b's segments land exactly in a's gaps (shared pitch grid)
    assert all(x not in ax for x in bx)
    from artifact_forge_ng.form.checks_hinge import (
        check_hinge_knuckle_geometry_ok, check_hinge_pin_fit_ok)
    assert check_hinge_pin_fit_ok(a).status.value == "pass"
    assert check_hinge_knuckle_geometry_ok(b).status.value == "pass"


def test_even_knuckles_refused():
    with pytest.raises(RecipeError, match="odd"):
        _leaf(knuckles=4)


def test_tight_pin_fails_fit_check():
    from artifact_forge_ng.form.checks_hinge import check_hinge_pin_fit_ok

    st = _leaf(pin_clearance=0.2)
    st.frame["hinge_bore_d"] = st.frame["hinge_pin_d"] + 0.1  # binds
    assert check_hinge_pin_fit_ok(st).status.value == "fail"


# -- modeled threads ------------------------------------------------------------------


def test_thread_pair_compensates_both_sides():
    from artifact_forge_ng.form.checks_thread import check_thread_spec_ok

    plug = run_pre_cad(EXAMPLES / "tank_plug_m20.yaml", None)
    port = run_pre_cad(EXAMPLES / "tank_port_plate_m20.yaml", None)
    fp, fo = plug.form.frame, port.form.frame
    assert fp["plug_thread_major"] == pytest.approx(19.8)   # M20 - 0.2
    assert fo["port_thread_major"] == pytest.approx(20.2)   # M20 + 0.2
    assert fp["plug_thread_turns"] >= 4.0
    assert check_thread_spec_ok(plug.form).status.value == "pass"
    tr = plug.form.threads[0]
    assert not tr.internal and port.form.threads[0].internal
    # the presence probe walks the mid-ridge helix
    pts = tr.helix_points()
    assert len(pts) > 50 and pts[0][2] == pytest.approx(tr.z0)


def test_thread_too_few_turns_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="turns"):
        RECIPE_OPS["threaded_plug_body"].apply(
            st, {"thread": "m20", "fit_compensation": 0.2, "stud_l": 7.0,
                 "grip_d": 36.0, "grip_h": 8.0}, "plug")


def test_unknown_thread_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="printable coarse table"):
        RECIPE_OPS["threaded_plug_body"].apply(
            st, {"thread": "m3", "fit_compensation": 0.2, "stud_l": 12.0,
                 "grip_d": 36.0, "grip_h": 8.0}, "plug")


# -- ratchet wheel --------------------------------------------------------------------


def test_ratchet_teeth_asymmetric_and_measured():
    from artifact_forge_ng.form.checks_ratchet import check_ratchet_teeth_ok

    state = run_pre_cad(EXAMPLES / "ratchet_wheel_40_24t.yaml", None)
    f = state.form.frame
    assert f["ratchet_teeth"] == 24.0
    assert f["ratchet_r_tip"] - f["ratchet_r_root"] == pytest.approx(2.5)
    assert f["ratchet_steep_frac"] <= 0.15
    assert check_ratchet_teeth_ok(state.form).status.value == "pass"
    # the section carries 2 points per tooth
    assert len(state.form.section.outer.segments) == 48


def test_ratchet_worm_ramp_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="steep_frac"):
        RECIPE_OPS["ratchet_wheel_body"].apply(
            st, {"wheel_d": 40.0, "teeth": 24, "tooth_depth": 2.5,
                 "steep_frac": 0.4, "t": 6.0, "socket": "square",
                 "shaft_sq": 8.0, "fit_clearance": 0.25}, "wheel")


def test_ratchet_serration_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="pitch"):
        RECIPE_OPS["ratchet_wheel_body"].apply(
            st, {"wheel_d": 22.0, "teeth": 40, "tooth_depth": 1.5,
                 "steep_frac": 0.08, "t": 6.0, "socket": "square",
                 "shaft_sq": 6.0, "fit_clearance": 0.25}, "wheel")


# -- shaft coupler --------------------------------------------------------------------


def test_coupler_measures_both_bores():
    from artifact_forge_ng.form.checks_connector import check_coupler_bores_ok

    state = run_pre_cad(EXAMPLES / "coupler_5_8_stepper.yaml", None)
    f = state.form.frame
    assert f["coupler_bore_a"] == pytest.approx(5.25)
    assert f["coupler_bore_b"] == pytest.approx(8.25)
    assert f["coupler_depth_a"] + f["coupler_depth_b"] + f["coupler_mid_web"]         == pytest.approx(25.0)
    assert check_coupler_bores_ok(state.form).status.value == "pass"
    assert {"shaft_a", "shaft_b"} <= set(state.form.datums)


def test_coupler_short_engagement_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="engagement"):
        RECIPE_OPS["shaft_coupler_body"].apply(
            st, {"shaft_d_a": 8.0, "shaft_d_b": 8.0, "fit_clearance": 0.25,
                 "body_d": 0.0, "length": 18.0, "mid_web": 3.0,
                 "set_screw": "m4"}, "coupler")


# -- living hinge --------------------------------------------------------------------


def test_living_hinge_web_measured():
    from artifact_forge_ng.form.checks_hinge import check_living_hinge_web_ok

    state = run_pre_cad(EXAMPLES / "card_case_blank_120.yaml", None)
    f = state.form.frame
    assert f["lh_web_t"] == pytest.approx(0.5)
    assert check_living_hinge_web_ok(state.form).status.value == "pass"
    assert "fold_line" in state.form.datums
    # the groove starts exactly at the web — the keepout guards below it
    groove = next(c for c in state.form.cutboxes if "groove" in c.name)
    assert groove.box.z0 == pytest.approx(0.5)


def test_living_hinge_torn_web_refused():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 120.0, "w": 70.0, "t": 1.6, "corner_r": 4.0}, "blank")
    with pytest.raises(RecipeError, match="web"):
        RECIPE_OPS["living_hinge_groove"].apply(
            st, {"web_t": 0.15, "groove_w": 3.0, "at_x": 0.0}, "fold")


# -- rail slider ---------------------------------------------------------------------


def test_slider_groove_mates_the_clamp_rail():
    """The shoe's groove keys are the dovetail_rail FEMALE contract —
    sized from the camera clamp's own rail numbers plus the clearance."""
    state = run_pre_cad(EXAMPLES / "rail_slider_camera_16.yaml", None)
    f = state.form.frame
    assert f["groove_top_w"] == pytest.approx(16.35)
    assert f["groove_bottom_w"] < f["groove_top_w"]  # a real dovetail
    assert f["groove_depth"] == pytest.approx(5.3)
    assert "rail_slot" in state.form.datums


def test_slider_flat_angle_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="rail_angle"):
        RECIPE_OPS["rail_slider_body"].apply(
            st, {"rail_top_w": 16.0, "rail_h": 5.0, "rail_angle": 0.0,
                 "slide_clearance": 0.35, "vert_clearance": 0.3,
                 "travel": 30.0, "wall": 3.0, "ceiling_t": 4.0}, "shoe")


def test_slider_short_travel_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="yaws"):
        RECIPE_OPS["rail_slider_body"].apply(
            st, {"rail_top_w": 16.0, "rail_h": 5.0, "rail_angle": 10.0,
                 "slide_clearance": 0.35, "vert_clearance": 0.3,
                 "travel": 15.0, "wall": 3.0, "ceiling_t": 4.0}, "shoe")


# -- cup holder / square post sleeve ------------------------------------------------


def _cup_with_sleeve(**over) -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["pot_body"].apply(
        st, {"top_d": 88.0, "bottom_d": 74.0, "h": 70.0, "wall": 2.4,
             "floor_t": 3.0, "floor_raise": 6.0}, "cup")
    p = {"post_w": 20.0, "fit_clearance": 0.5, "sleeve_h": 40.0, "z": 10.0,
         "wall": 3.0, "dir": "+x", "set_screw": "m4"}
    p.update(over)
    RECIPE_OPS["square_post_sleeve"].apply(st, p, "sleeve")
    return st


def test_post_sleeve_publishes_measured_frame():
    from artifact_forge_ng.form.checks_wallmount import (
        check_post_sleeve_engagement_ok, check_post_sleeve_fit_ok,
        check_post_sleeve_walls_ok)

    st = _cup_with_sleeve()
    assert st.frame["sleeve_channel_w_eff"] == pytest.approx(20.5)
    assert check_post_sleeve_fit_ok(st).status.value == "pass"
    assert check_post_sleeve_engagement_ok(st).status.value == "pass"
    assert check_post_sleeve_walls_ok(st).status.value == "pass"
    assert "post_axis" in st.datums
    # the arc-front collar: one additive poly loft riding the wall
    lofts = [pl for pl in st.poly_lofts if not pl.cut]
    assert len(lofts) == 1
    assert len(lofts[0].bottom) == len(lofts[0].top)


def test_post_sleeve_loose_clearance_refused():
    with pytest.raises(RecipeError, match="fit_clearance"):
        _cup_with_sleeve(fit_clearance=1.5)


def test_post_sleeve_past_the_pot_refused():
    with pytest.raises(RecipeError, match="runs past the pot"):
        _cup_with_sleeve(z=45.0, sleeve_h=40.0)


def test_post_sleeve_short_engagement_refused():
    with pytest.raises(RecipeError, match="rocks on the post"):
        _cup_with_sleeve(sleeve_h=25.0)


def test_post_too_wide_refused():
    # needs a tall vessel: a wide post also demands a tall sleeve, and
    # the height guard would fire first on the default cup
    st = RecipeState()
    RECIPE_OPS["pot_body"].apply(
        st, {"top_d": 100.0, "bottom_d": 80.0, "h": 120.0, "wall": 2.4,
             "floor_t": 3.0, "floor_raise": 6.0}, "cup")
    with pytest.raises(RecipeError, match="too wide"):
        RECIPE_OPS["square_post_sleeve"].apply(
            st, {"post_w": 70.0, "fit_clearance": 0.5, "sleeve_h": 110.0,
                 "z": 0.0, "wall": 3.0, "dir": "+x", "set_screw": "m4"},
            "sleeve")


# -- angle bracket ----------------------------------------------------------------


def _bracket(**over) -> RecipeState:
    st = RecipeState()
    p = {"leg_a": 40.0, "leg_b": 40.0, "width": 30.0, "t": 4.0,
         "gusset": 12.0, "screw": "M4", "holes_per_leg": 2, "hole_inset": 8.0}
    p.update(over)
    RECIPE_OPS["angle_bracket_body"].apply(st, p, "body")
    return st


def test_bracket_cuts_holes_in_both_legs():
    st = _bracket()
    axes = {b.name: b.axis for b in st.bores}
    assert axes == {"body_a_0": "Z", "body_a_1": "Z",
                    "body_b_0": "X", "body_b_1": "X"}
    assert st.frame["leg_a_len"] == 40.0
    assert st.print_orientation == "side_profile"


def test_bracket_short_leg_refused():
    with pytest.raises(RecipeError, match="too short for holes"):
        _bracket(leg_b=15.0, gusset=0.0, t=4.0, hole_inset=8.0, screw="M5")


def test_bracket_crowded_holes_refused():
    with pytest.raises(RecipeError, match="webs under 3"):
        _bracket(leg_a=41.0, leg_b=41.0, holes_per_leg=3, gusset=8.0)


def test_bracket_gusset_past_leg_refused():
    with pytest.raises(RecipeError, match="gusset"):
        _bracket(gusset=40.0)


def test_bracket_gusset_shapes_section():
    plain = _bracket(gusset=0.0)
    webbed = _bracket(gusset=12.0)
    # the diagonal web adds one segment to the L-polyline
    assert len(webbed.section.outer.segments) == len(plain.section.outer.segments) + 1


# -- pcb tray ---------------------------------------------------------------------


def test_tray_bosses_rise_from_floor_not_rim():
    state = run_pre_cad(EXAMPLES / "proto_tray_90x70.yaml", None)
    form = state.form
    bosses = [r for r in form.ribs if "standoffs" in r.name]
    assert len(bosses) == 4
    floor_t = form.frame["floor_t"]
    for b in bosses:
        assert b.box.z0 == pytest.approx(floor_t - 0.6)
    # pilots stay inside the boss column — the floor keepout is untouched
    assert check_cuts_respect_keepouts(form).status.value == "pass"


# -- strap mount ------------------------------------------------------------------


def test_strap_slot_into_screw_keepout_fails():
    from artifact_forge_ng.form.part import CutBoxFeature
    from artifact_forge_ng.form.regions import Box3

    state = run_pre_cad(EXAMPLES / "strap_mount_25mm.yaml", None)
    form = state.form
    rogue = CutBoxFeature(name="greedy_slot", box=Box3(-35, -3, -1, 35, 3, 6))
    form.cutboxes.append(rogue)
    try:
        assert check_cuts_respect_keepouts(form).status.value == "fail"
    finally:
        form.cutboxes.remove(rogue)


def test_strap_mount_keeps_center_bar():
    state = run_pre_cad(EXAMPLES / "strap_mount_50mm.yaml", None)
    cuts = {c.name: c.box for c in state.form.cutboxes}
    # solid bar between the paired slots
    assert cuts["strap_slot_a"].x1 < cuts["strap_slot_b"].x0
    assert cuts["strap_slot_b"].x0 - cuts["strap_slot_a"].x1 == pytest.approx(10.0)
    # the interface datum the strap_slot_pair port binds to
    assert "strap_center" in state.form.datums


# -- organizer bin ----------------------------------------------------------------


def _bin_shell(l=120.0, w=80.0, h=40.0, wall=2.4, floor_t=3.0) -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["rounded_box_shell"].apply(
        st, {"l": l, "w": w, "h": h, "wall": wall, "floor_t": floor_t,
             "corner_r": 5.0}, "shell")
    return st


def test_bin_crowded_dividers_refused():
    st = _bin_shell()
    with pytest.raises(RecipeError, match="cells along X"):
        RECIPE_OPS["bin_dividers"].apply(
            st, {"nx": 6, "ny": 0, "divider_t": 2.0, "height": 0.0,
                 "min_cell": 20.0}, "dividers")


def test_bin_dividers_weld_into_walls_and_floor():
    st = _bin_shell()
    RECIPE_OPS["bin_dividers"].apply(
        st, {"nx": 2, "ny": 1, "divider_t": 2.0, "height": 0.0,
             "min_cell": 20.0}, "dividers")
    from artifact_forge_ng.form.checks_organizer import check_dividers_span_cavity
    assert check_dividers_span_cavity(st).status.value == "pass"
    assert len([r for r in st.ribs if "_div_" in r.name]) == 3


def test_deep_lip_on_thin_floor_refused():
    st = _bin_shell(floor_t=2.4)
    with pytest.raises(RecipeError, match="severs the wall"):
        RECIPE_OPS["stacking_lip"].apply(
            st, {"lip_h": 4.0, "lip_wall": 1.6, "clearance": 0.3}, "lip")


def test_scoop_too_deep_refused():
    st = _bin_shell(h=25.0)
    with pytest.raises(RecipeError, match="floor"):
        RECIPE_OPS["finger_scoop"].apply(
            st, {"scoop_d": 30.0, "drop": 2.0, "face": "+y", "offset": 0.0},
            "scoop")


# -- spool ------------------------------------------------------------------------


def test_spool_flat_flanges_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="out-reach the barrel"):
        RECIPE_OPS["spool_body"].apply(
            st, {"flange_d": 52.0, "barrel_d": 50.0, "barrel_l": 40.0,
                 "flange_t": 4.0, "bore_d": 8.0}, "spool")


def test_spool_slot_ligament_refused():
    st = RecipeState()
    RECIPE_OPS["spool_body"].apply(
        st, {"flange_d": 60.0, "barrel_d": 28.0, "barrel_l": 30.0,
             "flange_t": 4.0, "bore_d": 8.0}, "spool")
    with pytest.raises(RecipeError, match="ligament"):
        RECIPE_OPS["flange_slot_pattern"].apply(
            st, {"count": 16, "slot_w": 6.0, "flange": "top",
                 "r_inner": 0.0}, "ties")


# -- pots -------------------------------------------------------------------------


def test_pot_upside_down_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="open upward"):
        RECIPE_OPS["pot_body"].apply(
            st, {"top_d": 60.0, "bottom_d": 80.0, "h": 80.0, "wall": 2.4,
                 "floor_t": 3.0, "floor_raise": 6.0}, "pot")


def test_pot_without_drains_fails_check():
    from artifact_forge_ng.form.checks_pots import check_pot_floor_drains

    st = RecipeState()
    RECIPE_OPS["pot_body"].apply(
        st, {"top_d": 90.0, "bottom_d": 70.0, "h": 85.0, "wall": 2.4,
             "floor_t": 3.0, "floor_raise": 6.0}, "pot")
    assert check_pot_floor_drains(st).status.value == "fail"
    RECIPE_OPS["bore_pattern"].apply(
        st, {"kind": "bolt_circle", "d": 7.0, "count": 4, "bc_d": 35.0,
             "nx": 2, "ny": 2, "spacing": 20.0, "spacing_y": 0.0,
             "cx": 0.0, "cy": 0.0, "z_top": 9.0, "through": 3.0}, "drains")
    assert check_pot_floor_drains(st).status.value == "pass"


def test_squircle_pot_measures_its_wall():
    from artifact_forge_ng.form.checks_pots import check_se_wall_ok

    state = run_pre_cad(EXAMPLES / "squircle_pot_110.yaml", None)
    f = state.form.frame
    assert f["se_exponent"] == 4.0
    assert f["se_min_wall"] >= 0.9 * f["pot_wall"]
    assert check_se_wall_ok(state.form).status.value == "pass"
    lofts = {pl.name: pl for pl in state.form.poly_lofts}
    assert set(lofts) == {"pot_body", "pot_cavity", "pot_foot_void"}
    assert lofts["pot_cavity"].cut and lofts["pot_foot_void"].cut
    assert len(lofts["pot_body"].bottom) == len(lofts["pot_body"].top)


def test_squircle_pot_undercut_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="open upward"):
        RECIPE_OPS["superellipse_pot_body"].apply(
            st, {"top_w": 80.0, "top_l": 80.0, "bottom_w": 100.0,
                 "bottom_l": 80.0, "h": 80.0, "wall": 2.4, "floor_t": 3.0,
                 "floor_raise": 6.0, "exponent": 4.0}, "pot")


def test_squircle_exponent_band_refused():
    st = RecipeState()
    with pytest.raises(RecipeError, match="exponent"):
        RECIPE_OPS["superellipse_pot_body"].apply(
            st, {"top_w": 100.0, "top_l": 80.0, "bottom_w": 90.0,
                 "bottom_l": 70.0, "h": 80.0, "wall": 2.4, "floor_t": 3.0,
                 "floor_raise": 6.0, "exponent": 9.0}, "pot")


def test_net_pot_slots_stay_inside_band():
    state = run_pre_cad(EXAMPLES / "net_pot_75.yaml", None)
    f = state.form.frame
    assert f["wall_slot_z0"] >= f["net_floor_t"] + 1.5
    assert f["wall_slot_z1"] <= f["net_rim_z"] - f["net_flange_t"] - 1.5
    assert f["floor_open_ratio"] > 0.2


# -- drill guide: namespaced rows -----------------------------------------------------


def test_two_row_guide_measures_both_rows():
    from artifact_forge_ng.form.checks_jig import check_bushing_fit_ok

    state = run_pre_cad(EXAMPLES / "step_drill_guide_8_5.yaml", None)
    f = state.form.frame
    assert f["bushings_bushing_od"] == 8.0
    assert f["bushings_b_bushing_od"] == 5.0
    finding = check_bushing_fit_ok(state.form)
    assert finding.status.value == "pass"
    assert "2 row(s)" in finding.message


# -- battery cell holder ------------------------------------------------------------


def test_cell_lip_bite_band_enforced():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 60.0, "w": 60.0, "t": 16.0, "corner_r": 4.0}, "block")
    with pytest.raises(RecipeError, match="lip bite"):
        RECIPE_OPS["cell_pocket_grid"].apply(
            st, {"cell": "18650", "nx": 1, "ny": 1, "pitch": 0.0,
                 "fit_clearance": 0.4, "lip_w": 2.0, "lip_h": 1.2,
                 "pocket_depth": 12.0, "slot_w": 4.0, "slot_l": 10.0,
                 "cx": 0.0, "cy": 0.0}, "cells")


def test_cell_holder_publishes_lip_keys():
    state = run_pre_cad(EXAMPLES / "cell_holder_18650_2x2.yaml", None)
    f = state.form.frame
    assert f["cell_grid_nx"] == 2.0 and f["cell_grid_ny"] == 2.0
    assert 0.6 <= f["cell_lip_bite"] <= 2.5
    assert f["cells_0_lip_r"] > 0


# -- pegboard -----------------------------------------------------------------------


def test_peg_too_short_refused():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 60.0, "w": 60.0, "t": 5.0, "corner_r": 4.0}, "plate")
    with pytest.raises(RecipeError, match="never passes"):
        RECIPE_OPS["peg_pattern"].apply(
            st, {"board": "imperial_quarter", "cols": 1, "rows": 1,
                 "peg_len": 4.0, "hook": "up", "hook_len": 8.0,
                 "anti_lift": 1, "cx": 0.0, "cy": 0.0}, "pegs")


def test_hooked_pattern_without_antilift_fails_check():
    from artifact_forge_ng.form.checks_pegboard import check_peg_engagement_ok

    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 60.0, "w": 60.0, "t": 5.0, "corner_r": 4.0}, "plate")
    RECIPE_OPS["peg_pattern"].apply(
        st, {"board": "imperial_quarter", "cols": 1, "rows": 1,
             "peg_len": 0.0, "hook": "up", "hook_len": 8.0,
             "anti_lift": 0, "cx": 0.0, "cy": 0.0}, "pegs")
    finding = check_peg_engagement_ok(st)
    assert finding.status.value == "fail"
    assert "anti-lift" in finding.message


# -- connectors ---------------------------------------------------------------------


def test_duplicate_socket_dir_refused():
    st = RecipeState()
    RECIPE_OPS["multi_socket_hub"].apply(st, {"hub_d": 22.0, "hub_h": 24.0}, "hub")
    arm = {"dir": "+x", "enabled": 1, "rod_d": 8.0, "depth": 0.0,
           "wall": 3.0, "clearance": 0.3, "fit": "slip",
           "set_screw": "none", "z": 0.0}
    RECIPE_OPS["socket_arm"].apply(st, arm, "east")
    with pytest.raises(RecipeError, match="already occupies"):
        RECIPE_OPS["socket_arm"].apply(st, dict(arm), "east2")


def test_socket_arm_isolated_by_construction():
    """socket_arm bores from the OUTER mouth inward — its blind end sits
    at r_hub + wall, never near the center. The isolation check must
    PASS here; its FAIL branch guards future center-reaching ops (the
    tube tee), measured below on a bare frame."""
    from artifact_forge_ng.form.checks_connector import check_socket_bores_isolated

    st = RecipeState()
    RECIPE_OPS["multi_socket_hub"].apply(st, {"hub_d": 22.0, "hub_h": 24.0}, "hub")
    for d, op_id in (("+x", "east"), ("-x", "west")):
        RECIPE_OPS["socket_arm"].apply(
            st, {"dir": d, "enabled": 1, "rod_d": 8.0, "depth": 16.0,
                 "wall": 3.0, "clearance": 0.3, "fit": "slip",
                 "set_screw": "none", "z": 0.0}, op_id)
    assert check_socket_bores_isolated(st).status.value == "pass"
    assert st.frame["east_inner_dist"] == pytest.approx(14.0)


def test_socket_isolation_check_fails_on_merged_ends():
    from artifact_forge_ng.form.checks_connector import check_socket_bores_isolated

    st = RecipeState()
    st.frame.update({
        "east_socket_depth": 16.0, "east_rod_d": 8.0,
        "east_socket_bore_d": 8.3, "east_wall_eff": 3.0,
        "east_inner_dist": 2.0,
        "west_socket_depth": 16.0, "west_rod_d": 8.0,
        "west_socket_bore_d": 8.3, "west_wall_eff": 3.0,
        "west_inner_dist": 2.0,
    })
    assert check_socket_bores_isolated(st).status.value == "fail"


def test_toggled_off_arm_port_is_honestly_unbuilt():
    """The rod_socket ports ride the optional+absent-datum mechanism: an
    elbow's two missing arms leave their ports un-built with a note,
    never a frame_exists FAIL; the full cross anchors all four."""
    from artifact_forge_ng.form.checks_interfaces import (
        check_interface_frame_exists)

    class _Ctx:
        pass

    elbow = run_pre_cad(EXAMPLES / "trellis_elbow_6mm.yaml", None)
    cross = run_pre_cad(EXAMPLES / "trellis_cross_10mm.yaml", None)
    finding_e = [f for f in elbow.report.findings
                 if f.check == "interface.frame_exists"][0]
    finding_c = [f for f in cross.report.findings
                 if f.check == "interface.frame_exists"][0]
    assert finding_e.status.value == "pass"
    assert "not built on this instance" in finding_e.message
    assert finding_c.status.value == "pass"
    assert "4 interface(s)" in finding_c.message


def test_diagonal_brace_builds_oriented_features():
    import math

    state = run_pre_cad(EXAMPLES / "trellis_a_frame_8mm.yaml", None)
    form = state.form
    brace_pins = [p for p in form.pins if p.axis == "ANGLED"]
    brace_bores = [b for b in form.bores if b.axis == "ANGLED"]
    assert len(brace_pins) == 1 and len(brace_bores) == 1
    dx, dy, dz = brace_pins[0].direction
    assert math.hypot(dx, dy, dz) == pytest.approx(1.0)
    assert dz == pytest.approx(math.sin(math.radians(45)))
    assert "socket_diag" in form.datums
    assert form.frame["diag_elevation_deg"] == 45.0


def test_flat_diagonal_refused():
    st = RecipeState()
    RECIPE_OPS["multi_socket_hub"].apply(st, {"hub_d": 24.0, "hub_h": 30.0}, "hub")
    with pytest.raises(RecipeError, match="elevation"):
        RECIPE_OPS["angled_socket_arm"].apply(
            st, {"azimuth_deg": 0.0, "elevation_deg": 15.0, "enabled": 1,
                 "rod_d": 8.0, "depth": 0.0, "wall": 3.0, "clearance": 0.3,
                 "fit": "slip", "z": 0.0}, "diag")


def test_angled_printable_check_measures_frame():
    from artifact_forge_ng.form.checks_connector import (
        check_angled_arm_printable)

    st = RecipeState()
    st.frame["diag_elevation_deg"] = 12.0
    assert check_angled_arm_printable(st).status.value == "fail"
    st.frame["diag_elevation_deg"] = 45.0
    assert check_angled_arm_printable(st).status.value == "pass"


def test_disabled_arm_is_a_noop():
    st = RecipeState()
    RECIPE_OPS["multi_socket_hub"].apply(st, {"hub_d": 22.0, "hub_h": 24.0}, "hub")
    RECIPE_OPS["socket_arm"].apply(
        st, {"dir": "+y", "enabled": 0, "rod_d": 8.0, "depth": 0.0,
             "wall": 3.0, "clearance": 0.3, "fit": "slip",
             "set_screw": "none", "z": 0.0}, "north")
    assert st.frame["socket_count"] == 0.0
    assert not st.pins


# -- text relief / stamp ------------------------------------------------------------


def test_unmirrored_stamp_refused():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 60.0, "w": 25.0, "t": 6.0, "corner_r": 4.0}, "die")
    with pytest.raises(RecipeError, match="MIRRORED"):
        RECIPE_OPS["text_emboss"].apply(
            st, {"text": "FORGE", "size": 10.0, "depth": 1.6,
                 "mode": "emboss", "mirror": "no", "duty": "stamp",
                 "face": "bottom", "cx": 0.0, "cy": 0.0, "z": 0.0,
                 "rotate": 0.0}, "legend")


def test_tiny_text_fails_stroke_check():
    from artifact_forge_ng.form.checks_text import check_min_stroke_width_ok

    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 60.0, "w": 25.0, "t": 6.0, "corner_r": 4.0}, "die")
    RECIPE_OPS["text_emboss"].apply(
        st, {"text": "tiny", "size": 5.0, "depth": 1.0,
             "mode": "emboss", "mirror": "no", "duty": "label",
             "face": "top", "cx": 0.0, "cy": 0.0, "z": 0.0,
             "rotate": 0.0}, "legend")
    assert check_min_stroke_width_ok(st).status.value == "fail"


def test_stamp_example_resolves_string_param():
    state = run_pre_cad(EXAMPLES / "leather_stamp_gb.yaml", None)
    tr = state.form.text_reliefs[0]
    assert tr.text == "GB"
    assert tr.mirror is True
    assert tr.direction == "down"
    assert tr.plane_z == 0.0


# -- tube connector -----------------------------------------------------------------


def _tee(**over) -> RecipeState:
    st = RecipeState()
    p = {"config": "tee", "run_d_a": 12.0, "run_d_b": 0.0, "branch_d": 0.0,
         "spigot_len": 28.0, "branch_len": 24.0, "wall": 2.4,
         "barb_h": 0.8, "barb_count": 3, "flange_t": 8.0, "flange_lip": 3.0}
    p.update(over)
    RECIPE_OPS["tee_body"].apply(st, p, "tee")
    return st


def test_tee_branch_bore_meets_the_run():
    from artifact_forge_ng.form.checks_connector import (
        check_branch_path_connected, check_tube_wall_ok)

    st = _tee()
    assert check_branch_path_connected(st).status.value == "pass"
    assert check_tube_wall_ok(st).status.value == "pass"
    assert st.frame["tee_branch_count"] == 1.0
    bores = {b.name for b in st.bores}
    assert "tee_px_bore" in bores


def test_cross_grows_both_branches():
    st = _tee(config="cross")
    assert st.frame["tee_branch_count"] == 2.0
    assert {p.name for p in st.pins} == {"tee_px_spigot", "tee_mx_spigot"}


def test_tee_tiny_branch_refused():
    with pytest.raises(RecipeError, match="branch bore"):
        _tee(branch_d=8.0, wall=2.4)


def test_elbow_caps_the_run_past_the_branch():
    from artifact_forge_ng.form.checks_connector import check_tube_run_open

    st = _tee(config="elbow")
    f = st.frame
    assert f["run_capped"] == 1.0
    # the blind bore tops above the branch junction + margin
    assert f["run_bore_top"] >= f["tee_branch_z"] + f["tee_branch_bore_d"] / 2 + 1.5
    assert check_tube_run_open(st).status.value == "pass"
    # one spigot only — the barb check judges the sides that exist
    assert "spigot_d_b" not in f
    from artifact_forge_ng.form.checks_spare import check_barb_retention_ok
    assert check_barb_retention_ok(st).status.value == "pass"


def test_shallow_elbow_cap_fails_run_open():
    from artifact_forge_ng.form.checks_connector import check_tube_run_open

    st = _tee(config="elbow")
    st.frame["run_bore_top"] = st.frame["tee_branch_z"]  # junction sticks out
    assert check_tube_run_open(st).status.value == "fail"


# -- camera rod clamp ---------------------------------------------------------------


def test_rod_clamp_pair_shares_the_split_clamp_law():
    lower = run_pre_cad(EXAMPLES / "rod_clamp_15mm_lower.yaml", None)
    upper = run_pre_cad(EXAMPLES / "rod_clamp_15mm_upper.yaml", None)
    # saddle center sits compression_gap/2 beyond each mating plane
    assert lower.form.frame["saddle_r"] == pytest.approx(7.5)
    assert upper.form.frame["saddle_r"] == pytest.approx(7.5)
    # the upper half carries the accessory rail
    assert "rail_interface" in {r.name for r in upper.form.regions}
