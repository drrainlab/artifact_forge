"""Layered-SVG flattening (luminance painter model) — the OCC-backed
importer that turns colored illustrations into single-level stamp
motifs. CAD-marked: booleans need the backend."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.cad
cq = pytest.importorskip("cadquery")

from artifact_forge_ng.cad.svg_flatten import flatten_svg_layers  # noqa: E402
from artifact_forge_ng.form.recipe_ops_core import RecipeError  # noqa: E402
from artifact_forge_ng.form.svg_path import svg_path_to_polygons  # noqa: E402

#: two overlapping dark squares on a light background, a white counter
#: punched through the overlap, a dark island inside the counter — every
#: painter rule in one file
LAYERED = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60">
<path d="M 0 0 L 100 0 L 100 60 L 0 60 Z" fill="#8EFD01"/>
<path d="M 10 10 L 55 10 L 55 50 L 10 50 Z" fill="#222222"/>
<path d="M 45 10 L 90 10 L 90 50 L 45 50 Z" fill="#5A12BF"/>
<path d="M 40 22 L 60 22 L 60 38 L 40 38 Z" fill="white"/>
<path d="M 47 27 L 53 27 L 53 33 L 47 33 Z" fill="black"/>
</svg>"""


def test_layered_art_flattens_to_union_with_counter():
    path, info = flatten_svg_layers(LAYERED, motif_w=60.0)
    assert info["ink_layers"] == 3 and info["paper_layers"] == 2
    outlines, holes, mw = svg_path_to_polygons(path, 60.0)
    # union of the two squares + the island; the white punch is a hole
    assert len(outlines) == 2
    assert len(holes) == 1
    assert mw > 0.8  # printable at 60mm — no boolean slivers survive


def test_background_falls_away():
    """The light full-canvas layer must not become geometry: the motif
    bbox is the squares' bbox, not the canvas."""
    path, _ = flatten_svg_layers(LAYERED, motif_w=60.0)
    outlines, _, _ = svg_path_to_polygons(path, 60.0)
    # at 60mm wide the union of squares (10..90 raw = 80 raw) fills the
    # width; the canvas (100 raw) would have made the motif 20% wider
    xs = [x for poly in outlines for x, _ in poly]
    assert max(xs) - min(xs) == pytest.approx(60.0, abs=0.5)


def test_all_light_art_refused():
    with pytest.raises(RecipeError, match="lighter than the ink"):
        flatten_svg_layers(
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path d="M 0 0 L 10 0 L 10 10 L 0 10 Z" fill="white"/></svg>',
            motif_w=40.0)


def test_stroke_only_art_refused():
    with pytest.raises(RecipeError, match="no filled"):
        flatten_svg_layers(
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<path d="M 0 0 L 10 0" fill="none" stroke="black"/></svg>',
            motif_w=40.0)
