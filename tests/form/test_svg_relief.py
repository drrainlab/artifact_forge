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
    polys, holes, mw = svg_path_to_polygons(TRIANGLE, 20.0)
    assert len(polys) == 1 and not holes
    xs = [x for x, _ in polys[0]]
    assert max(xs) - min(xs) == pytest.approx(20.0)
    assert mw > 10.0


def test_curves_flatten_by_arc_length():
    polys, _, _ = svg_path_to_polygons(
        "M 0 0 C 10 -10 20 0 10 12 C 0 0 -10 0 0 0 Z", 24.0)
    assert len(polys[0]) > 50  # a real polyline, not a chord


def test_open_subpath_refused():
    with pytest.raises(RecipeError, match="OPEN"):
        svg_path_to_polygons("M 0 0 L 10 0 L 5 8", 20.0)


def test_nested_subpath_is_a_hole():
    """An O: the counter becomes a hole tied to its outline, and the
    min width is the RING web (outline-to-hole), not the outline span."""
    polys, holes, mw = svg_path_to_polygons(
        "M 0 0 L 10 0 L 10 10 L 0 10 Z M 2 2 L 8 2 L 8 8 L 2 8 Z", 20.0)
    assert len(polys) == 1
    assert len(holes) == 1 and holes[0][0] == 0
    # ring web = (10-8)/10 * 20mm / ... : outer 20mm wide, hole 12mm,
    # web = (20-12)/2 = 4mm — NOT the 20mm the outline alone would claim
    assert mw == pytest.approx(4.0, abs=0.2)


def test_island_inside_a_hole_is_solid_again():
    """Even-odd depth 2: a copyright-style dot inside the counter is an
    outline again (its own prism), not a hole of a hole."""
    polys, holes, _ = svg_path_to_polygons(
        "M 0 0 L 20 0 L 20 20 L 0 20 Z "
        "M 2 2 L 18 2 L 18 18 L 2 18 Z "
        "M 8 8 L 12 8 L 12 12 L 8 12 Z", 40.0)
    assert len(polys) == 2      # outer frame + island
    assert len(holes) == 1 and holes[0][0] == 0


def test_sibling_holes_measure_their_web():
    """A B-like glyph: two counters in one outline — the bar between
    them is a real web the printer must lay down."""
    _, holes, mw = svg_path_to_polygons(
        "M 0 0 L 20 0 L 20 20 L 0 20 Z "
        "M 4 4 L 16 4 L 16 9 L 4 9 Z "
        "M 4 11 L 16 11 L 16 16 L 4 16 Z", 20.0)
    assert len(holes) == 2
    assert mw == pytest.approx(2.0, abs=0.2)  # the 2mm bar between counters


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
    assert st.frame["motif_svg_holes"] == 0.0
    assert st.frame["motif_svg_min_width"] > 4.0
    assert check_svg_relief_printable(st).status.value == "pass"
    tr = st.text_reliefs[0]
    assert tr.polygons and tr.mirror and tr.direction == "down"


def test_svg_stamp_with_counter_builds_and_measures_ring():
    """An O-motif die: the hole reaches the IR feature and the frame
    reports the ring web as the printable min width."""
    st = _die()
    _svg_op(st, path="M 0 0 L 24 0 L 24 24 L 0 24 Z "
                     "M 6 6 L 18 6 L 18 18 L 6 18 Z", width=24.0)
    assert st.frame["motif_svg_holes"] == 1.0
    assert st.frame["motif_svg_min_width"] == pytest.approx(6.0, abs=0.2)
    tr = st.text_reliefs[0]
    assert tr.holes and tr.holes[0][0] == 0


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


# -- mode cutout: through light slits with stencil bridges ---------------------------


def _plate() -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 60.0, "w": 60.0, "t": 2.4, "corner_r": 4.0}, "face")
    return st


RING = ("M 0 0 L 24 0 L 24 24 L 0 24 Z "
        "M 6 6 L 18 6 L 18 18 L 6 18 Z")


def test_cutout_pierces_and_bridges_every_hole():
    """A ring cut through the plate would drop its middle — the op
    generates ONE stencil bridge per enclosed hole region and the
    feature depth overshoots the plate (a real through cut)."""
    st = _plate()
    _svg_op(st, path=RING, width=30.0, mode="cutout", duty="label",
            face="top", mirror="no")
    tr = st.text_reliefs[0]
    assert st.frame["motif_svg_bridges"] == 1.0
    assert len(tr.bridges) == 1 and tr.bridges[0][0] == 0
    assert tr.depth > 2.4                     # pierces the 2.4 plate
    assert tr.mode == "engrave"               # IR reuses the engrave path
    # the bridge rect spans the ring web: its long side ≥ web + overshoot
    rect = tr.bridges[0][1]
    import math
    side = max(math.hypot(rect[1][0] - rect[0][0], rect[1][1] - rect[0][1]),
               math.hypot(rect[3][0] - rect[0][0], rect[3][1] - rect[0][1]))
    web = 30.0 * (6.0 / 24.0) / 2.0           # scaled ring web 3.75
    assert side >= web


def test_membrane_alias_is_engrave():
    st = _plate()
    _svg_op(st, path=RING, width=30.0, mode="membrane", duty="label",
            face="top", mirror="no", depth=1.2)
    tr = st.text_reliefs[0]
    assert tr.mode == "engrave" and tr.depth == 1.2 and not tr.bridges


def test_cutout_refuses_flimsy_bridge():
    st = _plate()
    with pytest.raises(RecipeError, match="bridge_w"):
        _svg_op(st, path=RING, width=30.0, mode="cutout", duty="label",
                face="top", mirror="no", bridge_w=0.4)


def test_cutout_requires_top_face():
    st = _plate()
    with pytest.raises(RecipeError, match="face: top"):
        _svg_op(st, path=RING, width=30.0, mode="cutout", duty="label",
                face="bottom", mirror="no")
