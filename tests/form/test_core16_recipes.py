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
    assert cuts["slot_a"].x1 < cuts["slot_b"].x0  # solid bar between slots
    assert cuts["slot_b"].x0 - cuts["slot_a"].x1 == pytest.approx(10.0)


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


def test_net_pot_slots_stay_inside_band():
    state = run_pre_cad(EXAMPLES / "net_pot_75.yaml", None)
    f = state.form.frame
    assert f["wall_slot_z0"] >= f["net_floor_t"] + 1.5
    assert f["wall_slot_z1"] <= f["net_rim_z"] - f["net_flange_t"] - 1.5
    assert f["floor_open_ratio"] > 0.2
