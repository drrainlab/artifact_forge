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
