"""Wave R2 (enclosure core), tier-1: shell walls are a checked contract,
bosses carry their own keepouts, the interior cavity does not veto floor
vents, and the port table is closed."""

from pathlib import Path

import pytest

from artifact_forge_ng.form.recipe_ops import PORT_SIZES, RECIPE_OPS, RecipeError, RecipeState
from artifact_forge_ng.form.validators import check_shell_walls_ok
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture(scope="module")
def state():
    return run_pre_cad(EXAMPLES / "esp32_box_base.yaml", None)


def test_enclosure_ir_green(state):
    fails = [f for f in state.report.findings if f.status.value == "fail"]
    assert fails == []
    form = state.form
    assert len(form.ribs) == 4  # bosses
    assert len(form.bores) == 4  # pilots
    names = {c.name for c in form.cutboxes}
    assert "shell_interior" in names and "port" in names


def test_floor_vents_survive_the_interior_cut(state):
    """The z-aware keepout rule: the cavity above the floor is not a
    keepout for slots cut THROUGH the floor — but the bosses are."""
    form = state.form
    field = form.fields[0]
    assert field.polygons, "vent slots were all vetoed"
    boss_x = form.frame["bosses_0_x"]
    boss_y = form.frame["bosses_0_y"]
    for poly in field.polygons:
        for px, py in poly:
            assert not (abs(px - boss_x) < 5.5 and abs(py - boss_y) < 5.5), (
                "vent slot cut into a boss keepout"
            )


def test_shell_walls_check_catches_greedy_cavity(state):
    from artifact_forge_ng.form.part import CutBoxFeature
    from artifact_forge_ng.form.regions import Box3

    form = state.form
    good = check_shell_walls_ok(form)
    assert good.status.value == "pass"
    # sabotage: replace the interior with one that eats a wall
    original = form.cutboxes[0]
    assert original.name == "shell_interior"
    b = original.box
    form.cutboxes[0] = CutBoxFeature(
        name="shell_interior", box=Box3(b.x0, b.y0, b.z0, b.x1 + 2.0, b.y1, b.z1)
    )
    try:
        bad = check_shell_walls_ok(form)
        assert bad.status.value == "fail"
        assert "wall thinned" in bad.message
    finally:
        form.cutboxes[0] = original


def test_pilot_cannot_pierce_the_floor():
    decl = RECIPE_OPS["boss_pattern"]
    st = RecipeState()
    RECIPE_OPS["rounded_box_shell"].apply(
        st, {"l": 60.0, "w": 40.0, "h": 20.0, "wall": 2.4, "floor_t": 3.0,
             "corner_r": 5.0}, "shell",
    )
    with pytest.raises(RecipeError, match="pierce the floor"):
        decl.apply(st, {"sx": 40.0, "sy": 24.0, "cx": 0.0, "cy": 0.0,
                        "boss": 7.0, "height": 4.0, "pilot_d": 4.0,
                        "pilot_depth": 8.0}, "bosses")


def test_unknown_port_refused():
    st = RecipeState()
    RECIPE_OPS["rounded_box_shell"].apply(
        st, {"l": 60.0, "w": 40.0, "h": 20.0, "wall": 2.4, "floor_t": 3.0,
             "corner_r": 5.0}, "shell",
    )
    with pytest.raises(RecipeError, match="unknown port"):
        RECIPE_OPS["port_cutout"].apply(
            st, {"port": "warp_conduit", "face": "+y", "offset": 0.0,
                 "z": 10.0, "clearance": 0.4}, "port",
        )
    assert "usb_c" in PORT_SIZES
