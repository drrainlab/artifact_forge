"""Text recipe op — glyphs as geometry on a horizontal face: raised
labels, engraved markings, mirrored stamp dies. The op carries the FIRST
free-text ("string") param in the registry; the glyph solid itself is
compiled from one bundled font (cad/text.py), the analytic checks read
the footprint estimate — no CAD at IR time.
Measurement contract: :mod:`artifact_forge_ng.form.checks_text`."""
from __future__ import annotations

from typing import Any

from .part import TextReliefFeature
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from ..product.archetype import RegionRole

#: DejaVu Sans thinnest-stem factor (see cad/text.py) and the printable
#: stroke floors: an embossed stroke needs two extrusion widths, an
#: engraved groove one nozzle width with slack.
STROKE_FACTOR = 0.09
MIN_STROKE_EMBOSS = 0.8
MIN_STROKE_ENGRAVE = 0.5


def _text_emboss(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    state.require_base("text_emboss")
    text = str(p["text"])
    if not text.strip():
        raise RecipeError("text_emboss needs non-empty text")
    size, depth = p["size"], p["depth"]
    mode = p["mode"]
    if mode not in ("emboss", "engrave"):
        raise RecipeError(f"mode {mode!r} not in (emboss, engrave)")
    mirror = p["mirror"]
    if mirror not in ("yes", "no"):
        raise RecipeError(f"mirror {mirror!r} not in (yes, no)")
    duty = p["duty"]
    if duty not in ("label", "stamp"):
        raise RecipeError(f"duty {duty!r} not in (label, stamp)")
    if duty == "stamp" and (mirror != "yes" or mode != "emboss"):
        raise RecipeError(
            "a stamp die must be MIRRORED RELIEF (mirror: yes, mode: "
            "emboss) — an unmirrored die prints its impression backwards")
    t = state.width
    face = p["face"]
    if face == "top":
        direction = "up"
        z = p["z"] if p["z"] > 1e-9 else t
    elif face == "bottom":
        # a stamp die: glyphs under the body, printed face-down on the bed
        direction = "down"
        z = p["z"]  # 0.0 = the part's underside
    else:
        raise RecipeError(f"face {face!r} not in (top, bottom)")
    if mode == "engrave" and depth >= t - 0.6:
        raise RecipeError(f"engrave depth {depth:g} pierces the {t:g} part")

    name = op_id or "text"
    tr = TextReliefFeature(
        name=name, text=text, at=(p["cx"], p["cy"]), plane_z=z,
        size=size, depth=depth, mode=mode,
        mirror=(mirror == "yes"), rotate_deg=p["rotate"],
        direction=direction,
    )
    state.text_reliefs.append(tr)
    w, h = tr.footprint()
    sign = 1.0 if direction == "up" else -1.0
    grow = depth if mode == "emboss" else 0.0
    sink = depth if mode == "engrave" else 0.0
    # glyphs are sacred: no field/modifier may eat the text band
    state.regions.append(Region(
        f"{name}_band", RegionRole.FASTENER_KEEPOUT,
        Box3(p["cx"] - w / 2.0, p["cy"] - h / 2.0,
             min(z - sign * sink, z + sign * grow),
             p["cx"] + w / 2.0, p["cy"] + h / 2.0,
             max(z - sign * sink, z + sign * grow))))
    state.frame.update(
        text_size=size, text_depth=depth,
        text_mirrored=1.0 if mirror == "yes" else 0.0,
        text_is_emboss=1.0 if mode == "emboss" else 0.0,
        text_stamp_duty=1.0 if duty == "stamp" else 0.0,
        text_stroke_est=size * STROKE_FACTOR,
        text_len=float(len(text)),
        text_band_w=w, text_band_h=h, text_plane_z=z,
    )


_register(RecipeOpDecl(
    name="text_emboss",
    kind="feature",
    params={
        "text": ("string", None),
        "size": ("length", 8.0),
        "depth": ("length", 1.2),
        "mode": ("choice", "emboss"),
        "mirror": ("choice", "no"),
        "duty": ("choice", "label"),
        "face": ("choice", "top"),
        "cx": ("length", 0.0),
        "cy": ("length", 0.0),
        "z": ("length", 0.0),
        "rotate": ("number", 0.0),
    },
    validators=(
        "form.min_stroke_width_ok",
        "form.stamp_mirrored_ok",
        "topology.text_relief_present",
    ),
    apply=_text_emboss,
    description="text as geometry on a horizontal face: raised label, "
                "engraved marking or mirrored stamp die (duty: stamp)",
))


def _svg_relief(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """An SVG path as geometry on a horizontal face — logos, ornaments,
    pattern dies. The path is flattened to polygons AT THE IR LEVEL
    (svg_path.py guards: closed subpaths, no holes, no path noise), so
    the printable-width check measures real numbers before any CAD."""
    from .svg_path import svg_path_to_polygons

    state.require_base("svg_relief")
    path_data = str(p["path"])
    width, depth = p["width"], p["depth"]
    mode = p["mode"]
    if mode not in ("emboss", "engrave"):
        raise RecipeError(f"mode {mode!r} not in (emboss, engrave)")
    mirror = p["mirror"]
    if mirror not in ("yes", "no"):
        raise RecipeError(f"mirror {mirror!r} not in (yes, no)")
    duty = p["duty"]
    if duty not in ("label", "stamp"):
        raise RecipeError(f"duty {duty!r} not in (label, stamp)")
    if duty == "stamp" and (mirror != "yes" or mode != "emboss"):
        raise RecipeError(
            "a stamp die must be MIRRORED RELIEF (mirror: yes, mode: "
            "emboss) — an unmirrored die prints its impression backwards")
    t = state.width
    face = p["face"]
    if face == "top":
        direction = "up"
        z = p["z"] if p["z"] > 1e-9 else t
    elif face == "bottom":
        direction = "down"
        z = p["z"]
    else:
        raise RecipeError(f"face {face!r} not in (top, bottom)")
    if mode == "engrave" and depth >= t - 0.6:
        raise RecipeError(f"engrave depth {depth:g} pierces the {t:g} part")

    polygons, min_width = svg_path_to_polygons(path_data, width)
    name = op_id or "svg"
    tr = TextReliefFeature(
        name=name, text=f"<svg:{len(polygons)} paths>",
        at=(p["cx"], p["cy"]), plane_z=z,
        size=width, depth=depth, mode=mode,
        mirror=(mirror == "yes"), rotate_deg=p["rotate"],
        direction=direction, polygons=polygons,
    )
    state.text_reliefs.append(tr)
    w, h = tr.footprint()
    sign = 1.0 if direction == "up" else -1.0
    grow = depth if mode == "emboss" else 0.0
    sink = depth if mode == "engrave" else 0.0
    state.regions.append(Region(
        f"{name}_band", RegionRole.FASTENER_KEEPOUT,
        Box3(p["cx"] - w / 2.0, p["cy"] - h / 2.0,
             min(z - sign * sink, z + sign * grow),
             p["cx"] + w / 2.0, p["cy"] + h / 2.0,
             max(z - sign * sink, z + sign * grow))))
    state.frame.update({
        f"{name}_svg_min_width": min_width,
        f"{name}_svg_is_emboss": 1.0 if mode == "emboss" else 0.0,
        f"{name}_svg_paths": float(len(polygons)),
    })
    state.frame.update(
        text_mirrored=1.0 if mirror == "yes" else 0.0,
        text_is_emboss=1.0 if mode == "emboss" else 0.0,
        text_stamp_duty=1.0 if duty == "stamp" else 0.0,
    )


_register(RecipeOpDecl(
    name="svg_relief",
    kind="feature",
    params={
        "path": ("string", None),
        "width": ("length", 30.0),
        "depth": ("length", 1.2),
        "mode": ("choice", "emboss"),
        "mirror": ("choice", "no"),
        "duty": ("choice", "label"),
        "face": ("choice", "top"),
        "cx": ("length", 0.0),
        "cy": ("length", 0.0),
        "z": ("length", 0.0),
        "rotate": ("number", 0.0),
    },
    validators=(
        "form.svg_relief_printable",
        "form.stamp_mirrored_ok",
        "topology.text_relief_present",
    ),
    apply=_svg_relief,
    description="SVG path data as relief geometry (closed hole-free "
                "subpaths, flattened and width-measured at the IR level)",
))
