"""Registry-completion ops, tier-1: nut trap hex orientation, heatset
sizing from the table, wire exits, counterbores, the raceway profile."""

from pathlib import Path

import math

import pytest

from artifact_forge_ng.core.fasteners import screw_spec
from artifact_forge_ng.form.profiles import build_open_c_channel_profile
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.form.validators import check_profile_closed, check_wall_thickness
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


def _plate(t: float = 8.0) -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 100.0, "w": 60.0, "t": t, "corner_r": 5.0}, "plate"
    )
    return st


def test_nut_trap_hexagon_is_flat_to_flat():
    st = _plate()
    RECIPE_OPS["nut_trap"].apply(
        st, {"screw": "M4", "clearance": 0.25, "cx": 0.0, "cy": 0.0}, "nut"
    )
    hexagon = st.fields[0].polygons[0]
    af = screw_spec("M4")["nut_af"] + 0.5
    # flat-to-flat across X (vertices at 30+60k degrees): width == af
    xs = [p[0] for p in hexagon]
    assert max(xs) - min(xs) == pytest.approx(af, abs=1e-6)
    ys = [p[1] for p in hexagon]
    assert max(ys) - min(ys) == pytest.approx(af * 2 / math.sqrt(3), abs=1e-6)


def test_heatset_pocket_sized_from_table():
    st = _plate()
    RECIPE_OPS["heatset_insert_pocket"].apply(
        st, {"screw": "M3", "depth": 5.0, "spacing": 40.0, "cx": 0.0, "cy": 0.0},
        "inserts",
    )
    assert all(b.d == screw_spec("M3")["heatset"] for b in st.bores)
    with pytest.raises(RecipeError, match="pierce"):
        RECIPE_OPS["heatset_insert_pocket"].apply(
            _plate(t=5.0),
            {"screw": "M3", "depth": 5.0, "spacing": 40.0, "cx": 0.0, "cy": 0.0},
            "x",
        )


def test_wire_exit_requires_a_shell():
    with pytest.raises(RecipeError, match="rounded_box_shell"):
        RECIPE_OPS["wire_exit"].apply(
            _plate(), {"cable_d": 5.0, "clearance": 0.5, "drop": 3.0,
                       "face": "+x", "offset": 0.0}, "w",
        )


def test_counterbore_holes_marked_cylinder():
    st = _plate()
    RECIPE_OPS["counterbore_hole_pattern"].apply(
        st, {"kind": "line", "screw": "M4", "count": 2, "spacing": 60.0,
             "bc_d": 40.0, "cx": 0.0, "cy": 0.0, "cs_face": "top",
             "z_top": 0.0, "through": 0.0}, "cb",
    )
    assert all(h.head_style == "cylinder" for h in st.holes)


def test_open_c_channel_profile():
    profile, frame = build_open_c_channel_profile(24.0, 16.0, 2.5, MOLDED_UTILITY_PART)
    assert check_profile_closed(profile.outer).status.value == "pass"
    assert frame["outer_w"] == pytest.approx(29.0)
    assert frame["slot_floor_v"] == pytest.approx(2.5)


def test_showcase_examples_ir_green():
    for name in ("fastener_plate_demo", "junction_box_60", "raceway_200"):
        state = run_pre_cad(EXAMPLES / f"{name}.yaml", None)
        fails = [f for f in state.report.findings if f.status.value == "fail"]
        assert fails == [], (name, fails)


def test_raceway_wall_measured():
    state = run_pre_cad(EXAMPLES / "raceway_200.yaml", None)
    assert check_wall_thickness(state.form).status.value == "pass"
    assert state.form.print_orientation == "as_modeled"
