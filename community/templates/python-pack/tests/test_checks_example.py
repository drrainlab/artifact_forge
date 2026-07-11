"""PASS / FAIL / n-a branches on real op-built forms."""
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState

from af_pack_example_python.checks.checks_example import check_example_edge_margin_ok


def _plate_with_hole(spacing: float) -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 60.0, "w": 30.0, "t": 4.0, "corner_r": 3.0}, "plate")
    RECIPE_OPS["hole_pattern"].apply(
        st, {"kind": "line", "screw": "M4", "count": 2, "spacing": spacing,
             "bc_d": 40.0, "cx": 0.0, "cy": 0.0, "cs_face": "top",
             "z_top": 0.0, "through": 0.0}, "holes")
    return st


def test_pass_branch():
    assert check_example_edge_margin_ok(_plate_with_hole(30.0)).status is Status.PASS


def test_fail_branch():
    assert check_example_edge_margin_ok(_plate_with_hole(52.0)).status is Status.FAIL


def test_na_branch():
    st = RecipeState()
    f = check_example_edge_margin_ok(st)
    assert f.status is Status.PASS and "n/a" in f.message
