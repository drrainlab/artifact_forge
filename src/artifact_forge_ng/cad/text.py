"""Text-to-solid for TextReliefFeature — OCC's font engine via cadquery,
locked to ONE bundled face (system font lookup is nondeterministic across
machines; a stamp die must render identically everywhere).

Font: DejaVu Sans (Bitstream Vera license — free, redistributable;
LICENSE_DEJAVU ships next to the .ttf)."""
from __future__ import annotations

from pathlib import Path

import cadquery as cq

from ..form.part import TextReliefFeature

FONT_PATH = Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf"
FONT_NAME = "DejaVu Sans"

#: Conservative stroke-width factor for DejaVu Sans regular: the thinnest
#: stem of a glyph is about this fraction of the cap height. The analytic
#: min-stroke check multiplies text size by this — no CAD needed.
STROKE_FACTOR = 0.09


def build_text_solid(tr: TextReliefFeature) -> cq.Workplane:
    """The glyph solid, positioned in world coordinates. Emboss: bottom
    welds 0.4 into the host face; engrave: top overshoots 1.0 above it —
    the caller welds or cuts."""
    if tr.direction == "up":
        if tr.mode == "emboss":
            z0 = tr.plane_z - 0.4
            height = tr.depth + 0.4
        else:
            z0 = tr.plane_z - tr.depth
            height = tr.depth + 1.0
    else:  # bottom-face relief: the stamp die's world
        if tr.mode == "emboss":
            z0 = tr.plane_z - tr.depth
            height = tr.depth + 0.4
        else:
            z0 = tr.plane_z - 1.0
            height = tr.depth + 1.0
    glyphs = (
        cq.Workplane("XY")
        .text(
            tr.text, tr.size, height,
            font=FONT_NAME, fontPath=str(FONT_PATH),
            combine=False, halign="center", valign="center",
        )
    )
    if tr.mirror:
        glyphs = glyphs.mirror(mirrorPlane="YZ")
    if abs(tr.rotate_deg) > 1e-9:
        glyphs = glyphs.rotate((0, 0, 0), (0, 0, 1), tr.rotate_deg)
    return glyphs.translate((tr.at[0], tr.at[1], z0))
