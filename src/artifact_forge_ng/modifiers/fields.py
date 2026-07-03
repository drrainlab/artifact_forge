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
from ..form.section import Pt
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
    from dataclasses import replace

    if pw.origin is not None:
        field = replace(field, origin=pw.origin, tilt_deg=pw.tilt_deg)
    if pw.mapping == "cylindrical":
        field = replace(field, mapping="cylindrical", cyl_center=pw.cyl_center,
                        cyl_r=pw.cyl_r, cyl_r_outer=pw.cyl_r_outer,
                        cyl_z0=pw.cyl_z0)
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
            from ..form.voronoi import chaikin

            polygons.append(tuple(chaikin(rect, 2)))
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
            origin=pw.origin,
            tilt_deg=pw.tilt_deg,
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
    if pw.mapping == "cylindrical" and ligament < 1.0:
        return [fail(use.id, f"cylindrical field ligament {ligament:g} < 1.0 — "
                             "through-wall webs this thin do not print")]
    cells = voronoi_cells(
        pw.window,
        list(pw.keepouts),
        seed=seed,
        sites=int(round(params.get("sites", 18))),
        min_ligament=ligament,
        edge_margin=params.get("edge_margin", 3.0),
        relax_iterations=int(round(params.get("relax_iterations", 2))),
        corner_smooth=int(round(params.get("corner_smooth", 2))),
    )
    if pw.mapping == "cylindrical" and cells:
        # cylindrical_z_mapping_v1 bound: a cell flattened onto its tangent
        # plane distorts by ~(s/2r)^2; keep cells small next to the radius.
        max_a = max(
            max(p[0] for p in c) - min(p[0] for p in c) for c in cells
        )
        if max_a > 0.6 * pw.cyl_r:
            return [fail(use.id,
                f"cell arc-width {max_a:.1f} > 0.6*r ({0.6 * pw.cyl_r:.1f}) — "
                "too distorted for the tangent-plane approximation; use more "
                "sites or a taller band")]
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
            origin=pw.origin,
            tilt_deg=pw.tilt_deg,
            mapping=pw.mapping,
            cyl_center=pw.cyl_center,
            cyl_r=pw.cyl_r,
            cyl_r_outer=pw.cyl_r_outer,
            cyl_z0=pw.cyl_z0,
        )
    )
    return [
        note(use.id, f"{len(cells)} voronoi cells (seed {seed}, {cut_mode}) on {use.target}")
    ]


@register_applicator("add_phyllotaxis_field")
def add_phyllotaxis_field(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    """Vogel sunflower spiral: hole k sits at r = c*sqrt(k), theta =
    k * 137.508 deg around the window center. Deterministic (no seed even
    needed — the spiral IS the pattern); every hole survives only if it
    clears the keepouts, and the c-spacing guarantees the declared ligament
    between NEIGHBOURS by construction (still measured, never trusted)."""
    import math as _math

    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    hole_d = params.get("hole_d", 3.0)
    ligament = params.get("min_ligament", 1.6)
    margin = params.get("edge_margin", 4.0)
    count = int(round(params.get("count", 120)))
    cut_mode = params.get("cut_mode", "through")
    inner = pw.window.shrunk(margin)
    if inner.width <= 0 or inner.height <= 0:
        form.fields.append(FieldFeature(
            plane_z=pw.z_top, centers=(), cell=hole_d, depth=pw.depth,
            pattern="round", window=pw.window, keepouts=pw.keepouts,
            min_ligament=ligament,
        ))
        return [note(use.id, "window smaller than margins — zero holes (honest)")]
    cx = (inner.u0 + inner.u1) / 2.0
    cy = (inner.v0 + inner.v1) / 2.0
    r_max = min(inner.width, inner.height) / 2.0
    # Vogel spacing: nearest-neighbour distance ~ c; pick c so that the
    # web between hole rims is at least the ligament.
    c = hole_d + ligament
    golden = _math.radians(137.50776405)
    kept: list[tuple[float, float]] = []
    r_hole = hole_d / 2.0
    k = 1
    while len(kept) < count:
        r = c * _math.sqrt(k)
        if r > r_max - r_hole:
            break
        theta = k * golden
        hx, hy = cx + r * _math.cos(theta), cy + r * _math.sin(theta)
        p = Pt(hx, hy)
        if inner.contains(p) and all(
            keep.shape.distance(p) > r_hole + keep.clearance for keep in pw.keepouts
        ):
            kept.append((hx, hy))
        k += 1
    field = FieldFeature(
        plane_z=pw.z_top,
        centers=tuple(kept),
        cell=hole_d,
        depth=_depth_for(cut_mode, pw.depth, params.get("recess_depth", 1.2)),
        pattern="round",
        window=pw.window,
        keepouts=pw.keepouts,
        min_ligament=ligament,
        origin=pw.origin,
        tilt_deg=pw.tilt_deg,
    )
    form.fields.append(field)
    return [
        note(use.id, f"{len(kept)} phyllotaxis holes ({cut_mode}) on {use.target}")
    ]


@register_applicator("add_vein_ribs")
def add_vein_ribs(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    """Standalone vein ribs — thin raised ridges flowing across the target
    face with a seeded rhythm (the biomorphic veins, available without the
    full style). Additive: they sit ON the face, keepouts only veto veins
    that would bury a screw head."""
    from ..form.part import RibFeature
    from ..form.regions import Box3

    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    if pw.origin is not None:
        return [fail(use.id, "vein ribs v1 support horizontal faces only")]
    import random

    rng = random.Random(int(round(params.get("seed", 7))))
    count = int(round(params.get("count", 5)))
    rib_h = params.get("rib_h", 1.4)
    rib_t = params.get("rib_t", 2.2)
    margin = params.get("edge_margin", 5.0)
    inner = pw.window.shrunk(margin)
    if inner.width <= 0 or inner.height <= 0:
        return [note(use.id, "window smaller than margins — zero veins (honest)")]
    along_u = inner.width >= inner.height
    lane = (inner.height if along_u else inner.width) / (count + 1)
    placed = 0
    for i in range(count):
        base = (inner.v0 if along_u else inner.u0) + lane * (i + 1)
        jitter = rng.uniform(-0.35, 0.35) * lane
        pos = base + jitter
        # seeded rhythm on the length too
        head = rng.uniform(0.0, 0.15)
        tail = rng.uniform(0.0, 0.15)
        if along_u:
            box = Box3(inner.u0 + head * inner.width, pos - rib_t / 2.0,
                       pw.z_top - 0.6,
                       inner.u1 - tail * inner.width, pos + rib_t / 2.0,
                       pw.z_top + rib_h)
        else:
            box = Box3(pos - rib_t / 2.0, inner.v0 + head * inner.height,
                       pw.z_top - 0.6,
                       pos + rib_t / 2.0, inner.v1 - tail * inner.height,
                       pw.z_top + rib_h)
        # veto veins that would bury a screw head
        from ..form.section import Pt as _Pt
        mid = _Pt((box.x0 + box.x1) / 2.0, (box.y0 + box.y1) / 2.0)
        if any(k.shape.distance(mid) <= k.clearance + rib_t for k in pw.keepouts):
            continue
        form.ribs.append(RibFeature(name=f"vein_{use.target}_{i}", box=box))
        placed += 1
    if placed == 0:
        return [fail(use.id, "every vein was vetoed by keepouts")]
    return [note(use.id, f"{placed} vein rib(s) (seed {int(params.get('seed', 7))}) on {use.target}")]
