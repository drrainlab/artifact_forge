"""SVG relief — the path flattener's guards and the printable-width
check, measured on real op-built forms."""
from __future__ import annotations

import pytest

from artifact_forge_ng.form.checks_text import check_svg_relief_printable
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState
from artifact_forge_ng.form.svg_path import svg_path_to_polygons

TRIANGLE = "M 0 0 L 10 0 L 5 8 Z"
ARROW = "M 0 8 L 12 8 L 12 2 L 24 10 L 12 18 L 12 12 L 0 12 Z"


def test_triangle_flattens_and_scales():
    polys, mw = svg_path_to_polygons(TRIANGLE, 20.0)
    assert len(polys) == 1
    xs = [x for x, _ in polys[0]]
    assert max(xs) - min(xs) == pytest.approx(20.0)
    assert mw > 10.0


def test_curves_flatten_by_arc_length():
    polys, _ = svg_path_to_polygons(
        "M 0 0 C 10 -10 20 0 10 12 C 0 0 -10 0 0 0 Z", 24.0)
    assert len(polys[0]) > 50  # a real polyline, not a chord


def test_open_subpath_refused():
    with pytest.raises(RecipeError, match="OPEN"):
        svg_path_to_polygons("M 0 0 L 10 0 L 5 8", 20.0)


def test_nested_subpaths_refused():
    with pytest.raises(RecipeError, match="NEST"):
        svg_path_to_polygons(
            "M 0 0 L 10 0 L 10 10 L 0 10 Z M 2 2 L 8 2 L 8 8 L 2 8 Z", 20.0)


def test_path_noise_refused():
    with pytest.raises(RecipeError, match="noise"):
        svg_path_to_polygons(
            "M 0 0 L 100 0 L 100 100 L 0 100 Z M 200 200 L 201 200 L 201 201 Z",
            30.0)


def _svg_op(st: RecipeState, **over) -> None:
    p = {"path": ARROW, "width": 32.0, "depth": 1.6, "mode": "emboss",
         "mirror": "yes", "duty": "stamp", "face": "bottom",
         "cx": 0.0, "cy": 0.0, "z": 0.0, "rotate": 0.0}
    p.update(over)
    RECIPE_OPS["svg_relief"].apply(st, p, "motif")


def _die() -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 60.0, "w": 36.0, "t": 6.0, "corner_r": 4.0}, "die")
    return st


def test_svg_stamp_measures_true_min_width():
    st = _die()
    _svg_op(st)
    assert st.frame["motif_svg_paths"] == 1.0
    assert st.frame["motif_svg_min_width"] > 4.0
    assert check_svg_relief_printable(st).status.value == "pass"
    tr = st.text_reliefs[0]
    assert tr.polygons and tr.mirror and tr.direction == "down"


def test_tiny_motif_fails_printable_check():
    st = _die()
    # the arrow's shaft is 4/24 of the width: at 4 mm wide it is ~0.7 mm
    _svg_op(st, width=4.0, duty="label", mirror="no")
    finding = check_svg_relief_printable(st)
    assert finding.status.value == "fail"
    assert "narrowest feature" in finding.message


def test_unmirrored_svg_stamp_refused():
    st = _die()
    with pytest.raises(RecipeError, match="MIRRORED"):
        _svg_op(st, mirror="no")
