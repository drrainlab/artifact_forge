"""Interface applicators — fastening hardware pockets and slots. Every
placement derives from the target region and is filtered against keepouts;
the compiler cuts exactly what survives.
"""

from __future__ import annotations

from typing import Any

from ..core.findings import Finding
from ..form.part import BoreFeature, CutBoxFeature, PartForm
from ..form.regions import Box3
from ..form.section import Pt
from ..product.archetype import ArchetypeSpec
from ..product.instance import ModifierUse
from . import register_applicator
from .common import fail, note, plate_window


@register_applicator("add_magnet_pockets")
def add_magnet_pockets(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    """Blind cylindrical pockets for press-in disc magnets, entered from
    the chosen face (bottom = hidden mounting magnets)."""
    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    d = params.get("magnet_d", 6.0) + params.get("fit_clearance", 0.15) * 2.0
    depth = params.get("magnet_h", 2.0) + 0.2
    count = int(round(params.get("count", 2)))
    face = params.get("face", "bottom")
    if depth >= pw.depth - 0.6:
        return [
            fail(
                use.id,
                f"pocket depth {depth:.1f} leaves < 0.6 mm skin in a "
                f"{pw.depth:.1f} mm plate",
            )
        ]
    min_web = form.params.get("min_web", 3.0)
    inner = pw.window.shrunk(d / 2.0 + max(2.0, min_web + 0.5))
    if inner.width < 0 or inner.height < 0:
        return [fail(use.id, "region too small for magnet pockets")]
    along_u = inner.width >= inner.height
    span_len = inner.width if along_u else inner.height
    placed = 0
    skipped = 0
    for i in range(count):
        # Interior distribution — candidates never sit at the window ends,
        # where they inevitably collide with edge screws.
        t = (i + 1) / (count + 1)
        u = inner.u0 + t * span_len if along_u else (inner.u0 + inner.u1) / 2
        v = (inner.v0 + inner.v1) / 2 if along_u else inner.v0 + t * span_len
        p = Pt(u, v)
        if any(k.shape.distance(p) <= d / 2.0 + k.clearance + 1.0 for k in pw.keepouts):
            skipped += 1
            continue
        z_bottom_face = pw.z_top - pw.depth
        if face == "bottom":
            span = (z_bottom_face, z_bottom_face + depth)
            overshoot = (1.0, 0.0)  # blind: entered from below
        else:
            span = (pw.z_top - depth, pw.z_top)
            overshoot = (0.0, 1.0)
        form.bores.append(
            BoreFeature(
                f"magnet_pocket_{placed}", "Z", (u, v, 0.0), d, span,
                overshoot=overshoot,
            )
        )
        placed += 1
    if placed == 0:
        return [fail(use.id, "no magnet pocket cleared the keepouts")]
    msg = f"{placed} magnet pocket(s) ({face} face) on {use.target}"
    if skipped:
        msg += f"; {skipped} skipped over keepouts"
    return [note(use.id, msg)]


@register_applicator("add_zip_tie_slots")
def add_zip_tie_slots(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    """A pair of through slots flanking the region center — a zip tie
    threads down one, under the bridge, up the other."""
    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    tie_w = params.get("tie_w", 4.8)
    slot_l = tie_w + 1.2
    slot_t = params.get("tie_t", 1.6) + 0.8
    bridge = params.get("bridge_w", 8.0)
    cu = (pw.window.u0 + pw.window.u1) / 2.0
    cv = (pw.window.v0 + pw.window.v1) / 2.0
    z0, z1 = pw.z_top - pw.depth - 1.0, pw.z_top + 1.0
    slots = []
    for side in (-1.0, 1.0):
        u_c = cu + side * (bridge / 2.0 + slot_t / 2.0)
        box = Box3(
            u_c - slot_t / 2.0, cv - slot_l / 2.0, z0,
            u_c + slot_t / 2.0, cv + slot_l / 2.0, z1,
        )
        corners = [Pt(box.x0, box.y0), Pt(box.x1, box.y1), Pt(box.x0, box.y1), Pt(box.x1, box.y0)]
        if any(
            any(k.shape.distance(p) <= k.clearance + 0.5 or k.shape.contains(p) for p in corners)
            for k in pw.keepouts
        ):
            return [fail(use.id, "zip-tie slots would violate a keepout")]
        if not (pw.window.contains(corners[0]) and pw.window.contains(corners[1])):
            return [fail(use.id, "region too small for the slot pair")]
        slots.append(box)
    for i, box in enumerate(slots):
        form.cutboxes.append(CutBoxFeature(f"zip_slot_{i}", box))
    return [note(use.id, f"zip-tie slot pair (bridge {bridge:g} mm) on {use.target}")]


@register_applicator("add_strap_slots")
def add_strap_slots(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    """A pair of WIDE through slots in a strap tab (wave P2 wearable
    closure): the strap runs along the extrusion axis, so the slot pair
    flanks the strap bar along the tab's outward axis and each slot spans
    the strap width along X. Every slot corner is additionally guarded
    against the arm circle — a strap cut can never breach the body cavity."""
    import math as _math

    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    strap_w = params.get("strap_w", 25.0)
    slot_len = strap_w + 1.2  # along X: the strap must slide through
    slot_t = params.get("strap_t", 2.0) + 1.2  # along Y: thickness + slack
    bridge = params.get("bridge_w", 8.0)
    cu = (pw.window.u0 + pw.window.u1) / 2.0
    cv = (pw.window.v0 + pw.window.v1) / 2.0
    z0, z1 = pw.z_top - pw.depth - 1.0, pw.z_top + 1.0
    arm_r = form.frame.get("arm_r_inner")
    slots: list[Box3] = []
    for side in (-1.0, 1.0):
        v_c = cv + side * (bridge / 2.0 + slot_t / 2.0)
        box = Box3(
            cu - slot_len / 2.0, v_c - slot_t / 2.0, z0,
            cu + slot_len / 2.0, v_c + slot_t / 2.0, z1,
        )
        corners = [Pt(box.x0, box.y0), Pt(box.x1, box.y1),
                   Pt(box.x0, box.y1), Pt(box.x1, box.y0)]
        if any(
            any(k.shape.distance(p) <= k.clearance + 0.5 or k.shape.contains(p)
                for p in corners)
            for k in pw.keepouts
        ):
            return [fail(use.id, "strap slots would violate a keepout")]
        if not (pw.window.contains(corners[0]) and pw.window.contains(corners[1])):
            return [fail(
                use.id,
                f"tab {use.target!r} too small for a {strap_w:g} mm strap pair",
            )]
        if arm_r is not None:
            # nearest point of the (y, z) rectangle to the arm center (0, 0)
            ny = min(max(0.0, box.y0), box.y1)
            nz = min(max(0.0, box.z0), box.z1)
            if _math.hypot(ny, nz) < arm_r + 0.5:
                return [fail(
                    use.id,
                    f"strap slot on {use.target!r} would cut into the arm "
                    f"circle (r={arm_r:g})",
                )]
        slots.append(box)
    for i, box in enumerate(slots):
        form.cutboxes.append(CutBoxFeature(f"strap_slot_{use.target}_{i}", box))
    return [note(
        use.id,
        f"strap slot pair ({strap_w:g} mm strap, bar {bridge:g} mm) on "
        f"{use.target}",
    )]
