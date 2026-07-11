"""Text relief form checks — printable stroke width and stamp-die
mirroring, measured analytically from the frame keys text_emboss
publishes (the glyph solids come later, at compile time)."""
from __future__ import annotations

import math

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_text import MIN_STROKE_EMBOSS, MIN_STROKE_ENGRAVE

_finding = make_finding


def check_min_stroke_width_ok(form: PartForm) -> Finding:
    """The thinnest glyph stem (conservative per the bundled font) must
    survive the nozzle: two extrusion widths raised, one engraved."""
    check = "form.min_stroke_width_ok"
    f = form.frame
    if "text_stroke_est" not in f:
        return _finding(check, True, "n/a — no text relief on this part",
                        critical=False)
    stroke = f["text_stroke_est"]
    need = MIN_STROKE_EMBOSS if f["text_is_emboss"] > 0 else MIN_STROKE_ENGRAVE
    ok = stroke >= need - 1e-9
    return _finding(
        check, ok,
        f"estimated stroke {stroke:.2f} {'≥' if ok else '<'} printable "
        f"{need:g} ({'raised' if f['text_is_emboss'] > 0 else 'engraved'})",
        measured=stroke, limit=need)


def check_stamp_mirrored_ok(form: PartForm) -> Finding:
    """A stamp die must be mirrored relief — the op refuses to build one
    otherwise; this check re-measures the published frame so the promise
    survives any future op."""
    check = "form.stamp_mirrored_ok"
    f = form.frame
    if "text_stamp_duty" not in f:
        return _finding(check, True, "n/a — no text relief on this part",
                        critical=False)
    if f["text_stamp_duty"] < 1.0:
        return _finding(check, True, "label duty — mirroring not required")
    ok = f["text_mirrored"] > 0 and f["text_is_emboss"] > 0
    return _finding(
        check, ok,
        "stamp die is mirrored relief" if ok else
        "stamp duty without mirrored relief — the impression reads backwards")


register_probe("form.min_stroke_width_ok")(
    lambda form, ctx: check_min_stroke_width_ok(form))
register_probe("form.stamp_mirrored_ok")(
    lambda form, ctx: check_stamp_mirrored_ok(form))


def check_svg_relief_printable(form: PartForm) -> Finding:
    """Every SVG relief's TRUE narrowest feature (measured on the
    flattened polygons, not estimated) must survive the nozzle."""
    check = "form.svg_relief_printable"
    f = form.frame
    rows = [k[: -len("_svg_min_width")] for k in f
            if k.endswith("_svg_min_width")]
    if not rows:
        return _finding(check, True, "n/a — no svg relief on this part",
                        critical=False)
    problems: list[str] = []
    worst, need_worst = math.inf, 0.0
    for name in rows:
        mw = f[f"{name}_svg_min_width"]
        need = (MIN_STROKE_EMBOSS if f[f"{name}_svg_is_emboss"] > 0
                else MIN_STROKE_ENGRAVE)
        if mw < worst:
            worst, need_worst = mw, need
        if mw < need - 1e-9:
            problems.append(
                f"{name}: narrowest feature {mw:.2f} < printable {need:g}")
    if problems:
        return _finding(check, False, "; ".join(problems),
                        measured=worst, limit=need_worst)
    return _finding(
        check, True,
        f"{len(rows)} svg relief(s), narrowest feature {worst:.2f} clears "
        "the nozzle",
        measured=worst, limit=need_worst)


register_probe("form.svg_relief_printable")(
    lambda form, ctx: check_svg_relief_printable(form))
