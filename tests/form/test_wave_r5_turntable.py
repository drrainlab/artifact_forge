"""Wave R5 (mechanics & wow), tier-1: the bearing seat is a stepped bore
with a real lip, and the phyllotaxis spiral is deterministic and
keepout-respecting."""

from pathlib import Path

import math

import pytest

from artifact_forge_ng.form.recipe_ops import BEARINGS, RECIPE_OPS, RecipeError, RecipeState
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture(scope="module")
def state():
    return run_pre_cad(EXAMPLES / "bearing_turntable_base.yaml", None)


def test_turntable_ir_green(state):
    fails = [f for f in state.report.findings if f.status.value == "fail"]
    assert fails == []


def test_seat_is_a_stepped_bore_with_lip(state):
    form = state.form
    bores = {b.name: b for b in form.bores}
    pocket, through = bores["seat_pocket"], bores["seat_through"]
    od, bw, _ = BEARINGS["608"]
    assert pocket.d == pytest.approx(od)  # press fit: no clearance added
    assert through.d < pocket.d - 2.0  # the lip ring is real material
    # the pocket CUTTER (span grown by overshoot) must stop exactly at the
    # lip, never nibble it
    cutter_bottom = pocket.span[0] - pocket.overshoot[0]
    assert cutter_bottom == pytest.approx(form.width - bw)
    assert form.frame["seat_lip_z1"] == pytest.approx(form.width - bw)


def test_phyllotaxis_is_deterministic_and_respects_keepouts(state):
    form = state.form
    field = form.fields[0]
    assert field.pattern == "round"
    assert len(field.centers) > 60
    # deterministic: rebuilding gives the same spiral bit for bit
    again = run_pre_cad(EXAMPLES / "bearing_turntable_base.yaml", None)
    assert again.form.fields[0].centers == field.centers
    # no hole may touch the bearing seat or a screw
    seat_r = form.bores[0].d / 2.0
    hole_r = field.cell / 2.0
    for hx, hy in field.centers:
        assert math.hypot(hx, hy) > seat_r + hole_r, "hole inside the seat"
        for i in range(4):
            sx = form.frame[f"screws_{i}_x"]
            sy = form.frame[f"screws_{i}_y"]
            assert math.hypot(hx - sx, hy - sy) > hole_r + 2.0


def test_thin_plate_refuses_the_bearing():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 80.0, "w": 80.0, "t": 7.5, "corner_r": 5.0}, "plate"
    )
    with pytest.raises(RecipeError, match="too thin"):
        RECIPE_OPS["bearing_seat"].apply(
            st, {"bearing": "608", "fit": "press", "cx": 0.0, "cy": 0.0,
                 "lip_w": 1.5}, "seat",
        )


def test_lip_cannot_cover_inner_race():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 80.0, "w": 80.0, "t": 10.0, "corner_r": 5.0}, "plate"
    )
    with pytest.raises(RecipeError, match="inner race"):
        RECIPE_OPS["bearing_seat"].apply(
            st, {"bearing": "608", "fit": "press", "cx": 0.0, "cy": 0.0,
                 "lip_w": 7.0}, "seat",
        )
