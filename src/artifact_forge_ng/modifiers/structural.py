"""Structural applicators — the ADDITIVE half of the modifier kernel.
Ribs add material; they still respect keepouts (a rib over a countersink
buries the screw head) and are verified PRESENT by a solid-fraction probe,
so a rib that failed to weld is a loud finding, never silent air.
"""

from __future__ import annotations

from typing import Any

from ..core.findings import Finding
from ..form.part import PartForm, RibFeature
from ..form.regions import Box3
from ..form.section import Pt
from ..product.archetype import ArchetypeSpec
from ..product.instance import ModifierUse
from . import register_applicator
from .common import fail, note, plate_window

#: A rib must sink into its host by the weld rule.
RIB_WELD = 0.6


@register_applicator("add_ribs")
def add_ribs(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    """Parallel stiffening bars across the region's SHORT dimension, on the
    top face, keepout-filtered."""
    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    rib_w = params.get("rib_w", 2.5)
    rib_h = params.get("rib_h", 3.0)
    count = int(round(params.get("count", 3)))
    margin = params.get("edge_margin", 3.0)
    inner = pw.window.shrunk(margin)
    if inner.width <= 0 or inner.height <= 0:
        return [fail(use.id, "region too small for ribs")]
    # bars run along the shorter side, distributed along the longer one
    along_u = inner.width >= inner.height
    span_len = inner.width if along_u else inner.height
    placed = 0
    skipped = 0
    for i in range(count):
        t = 0.5 if count == 1 else i / (count - 1)
        pos = (inner.u0 if along_u else inner.v0) + t * span_len
        if along_u:
            box = Box3(pos - rib_w / 2, inner.v0, pw.z_top - RIB_WELD,
                       pos + rib_w / 2, inner.v1, pw.z_top + rib_h)
        else:
            box = Box3(inner.u0, pos - rib_w / 2, pw.z_top - RIB_WELD,
                       inner.u1, pos + rib_w / 2, pw.z_top + rib_h)
        samples = [
            Pt(box.x0, box.y0), Pt(box.x1, box.y1),
            Pt(box.x0, box.y1), Pt(box.x1, box.y0),
            Pt((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2),
        ]
        if any(
            any(k.shape.distance(p) <= k.clearance + 0.5 or k.shape.contains(p) for p in samples)
            for k in pw.keepouts
        ):
            skipped += 1
            continue
        form.ribs.append(RibFeature(f"rib_{placed}", box))
        placed += 1
    if placed == 0:
        return [fail(use.id, "no rib cleared the keepouts")]
    msg = f"{placed} rib(s) {rib_w:g}x{rib_h:g} on {use.target}"
    if skipped:
        msg += f"; {skipped} skipped over keepouts"
    return [note(use.id, msg)]
