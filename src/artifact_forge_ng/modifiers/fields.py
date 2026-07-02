"""Field applicators — honeycomb, grid slots, voronoi. Each resolves its
target region into a window, derives keepouts, and emits a FieldFeature
whose cells are FINAL at the IR level; the compiler cuts exactly those and
nothing else.
"""

from __future__ import annotations

from typing import Any

from ..core.findings import Finding
from ..form.fields import apply_field_with_keepouts
from ..form.part import FieldFeature, PartForm
from ..form.voronoi import voronoi_cells
from ..product.archetype import ArchetypeSpec
from ..product.instance import ModifierUse
from . import register_applicator
from .common import fail, note, plate_window


def _depth_for(cut_mode: str, window_depth: float, recess_depth: float) -> float:
    if cut_mode == "recess":
        return min(recess_depth, max(0.4, window_depth - 0.8))
    return window_depth  # through


@register_applicator("add_hex_perforation")
def add_hex_perforation(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    cell = params.get("cell_d", 5.0)
    cut_mode = params.get("cut_mode", "through")
    field = apply_field_with_keepouts(
        window=pw.window,
        keepouts=list(pw.keepouts),
        cell=cell,
        wall_gap=params.get("wall_gap", 1.5),
        margin=params.get("edge_margin", max(4.0, cell)),
        plane_z=pw.z_top,
        depth=_depth_for(cut_mode, pw.depth, params.get("recess_depth", 1.2)),
    )
    form.fields.append(field)
    return [
        note(use.id, f"{len(field.centers)} hex cells ({cut_mode}) on {use.target}")
    ]


@register_applicator("add_grid_slot_field")
def add_grid_slot_field(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    """Parallel slots across the window, each a rectangle polygon kept only
    if fully clear of the keepouts."""
    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    slot_w = params.get("slot_w", 4.0)
    web = params.get("web", 2.5)
    margin = params.get("edge_margin", 4.0)
    cut_mode = params.get("cut_mode", "through")
    inner = pw.window.shrunk(margin)
    if inner.width <= 0 or inner.height <= 0:
        form.fields.append(
            FieldFeature(
                plane_z=pw.z_top, centers=(), cell=slot_w,
                depth=pw.depth, pattern="slots", window=pw.window,
                keepouts=pw.keepouts, min_ligament=web,
            )
        )
        return [note(use.id, "window smaller than margins — zero slots (honest)")]
    # slots run along the window's longer side
    along_u = inner.width >= inner.height
    polygons: list[tuple[tuple[float, float], ...]] = []
    pitch = slot_w + web
    pos = (inner.v0 if along_u else inner.u0) + slot_w / 2.0
    end = (inner.v1 if along_u else inner.u1) - slot_w / 2.0
    from ..form.regions import Region2D  # noqa: F401  (typing aid)
    from ..form.section import Pt

    while pos <= end + 1e-9:
        if along_u:
            rect = [
                (inner.u0, pos - slot_w / 2), (inner.u1, pos - slot_w / 2),
                (inner.u1, pos + slot_w / 2), (inner.u0, pos + slot_w / 2),
            ]
        else:
            rect = [
                (pos - slot_w / 2, inner.v0), (pos + slot_w / 2, inner.v0),
                (pos + slot_w / 2, inner.v1), (pos - slot_w / 2, inner.v1),
            ]
        samples = [Pt(x, y) for x, y in rect] + [
            Pt((rect[0][0] + rect[2][0]) / 2, (rect[0][1] + rect[2][1]) / 2)
        ]
        clear = all(
            all(k.shape.distance(p) > k.clearance + web / 2 for p in samples)
            for k in pw.keepouts
        )
        if clear:
            polygons.append(tuple(rect))
        pos += pitch
    form.fields.append(
        FieldFeature(
            plane_z=pw.z_top,
            centers=(),
            cell=slot_w,
            depth=_depth_for(cut_mode, pw.depth, params.get("recess_depth", 1.2)),
            pattern="slots",
            window=pw.window,
            keepouts=pw.keepouts,
            polygons=tuple(polygons),
            min_ligament=web,
        )
    )
    return [note(use.id, f"{len(polygons)} slots ({cut_mode}) on {use.target}")]


@register_applicator("add_voronoi_field")
def add_voronoi_field(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    seed = int(round(params.get("seed", 42)))
    ligament = params.get("min_ligament", 1.6)
    cut_mode = params.get("cut_mode", "through")
    cells = voronoi_cells(
        pw.window,
        list(pw.keepouts),
        seed=seed,
        sites=int(round(params.get("sites", 18))),
        min_ligament=ligament,
        edge_margin=params.get("edge_margin", 3.0),
        relax_iterations=int(round(params.get("relax_iterations", 2))),
    )
    form.fields.append(
        FieldFeature(
            plane_z=pw.z_top,
            centers=(),
            cell=0.0,
            depth=_depth_for(cut_mode, pw.depth, params.get("recess_depth", 1.2)),
            pattern="voronoi",
            window=pw.window,
            keepouts=pw.keepouts,
            polygons=tuple(tuple(c) for c in cells),
            min_ligament=ligament,
        )
    )
    return [
        note(use.id, f"{len(cells)} voronoi cells (seed {seed}, {cut_mode}) on {use.target}")
    ]
