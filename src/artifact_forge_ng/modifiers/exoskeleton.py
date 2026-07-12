"""Biomorphic exoskeleton applicators (Bio-2, IR only).

``apply_biomorphic_exoskeleton`` grows the full load-aware rib network:
masks -> substrate -> Gabriel graph -> tapered ribs -> organic windows,
and attaches the frozen ExoskeletonIR to the form plus one organic
FieldFeature (which buys min_ligament_ok / field_cells_present /
serialization / the Bio-3 window cutting for free). Ribs are deliberately
NOT RibFeatures — tapered capsules are not boxes; Bio-3 materializes them
from the IR.

``add_bone_windows`` is the graph-less sibling: seeded voronoi windows on
a lightening zone, same organic FieldFeature contract.
"""

from __future__ import annotations

import zlib
from dataclasses import replace
from typing import Any

from ..core.findings import Finding, Level, Status
from ..form.exoskeleton.blend import node_blend_radii
from ..form.exoskeleton.ir import ExoskeletonIR
from ..form.exoskeleton.masks import (
    poly_clear,
    profile_surface_keepout_mask,
    semantic_keepout_mask,
)
from ..form.exoskeleton.ribs import load_path_guided_ribs
from ..form.exoskeleton.substrate import build_substrate
from ..form.exoskeleton.graph import surface_rib_graph
from ..form.exoskeleton.windows import organic_window_field
from ..form.part import FieldFeature, PartForm
from ..form.regions import Region2D
from ..form.voronoi import voronoi_cells, _centroid
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ModifierUse
from . import register_applicator
from .common import PlateWindow, fail, note, plate_window


def _warn(modifier_id: str, message: str) -> Finding:
    """A non-fatal applicator finding (Status.WARN) — the honest 'this is
    shallower/less than promised' signal, not a build-stopping FAIL."""
    return Finding(
        check=f"modifier:{modifier_id}",
        status=Status.WARN,
        level=Level.FORM,
        message=message,
    )


def _resolve_seed(params: dict[str, Any], form: PartForm) -> int:
    """Explicit positive seed wins; 0 (the default) derives a STABLE seed
    from the product name via CRC32 — never ``hash()``, which is salted
    per process and would turn every run into a dice roll."""
    raw = int(round(params.get("seed", 0)))
    if raw > 0:
        return raw
    return zlib.crc32(form.name.encode()) & 0xFFFF


def side_profile_window_gap(
    form: PartForm, use: ModifierUse, modifier_label: str
) -> Finding | None:
    """The honest guard for FIX-me-in-Bio-3 bodies: on a side-profile part
    (a clamp half) the region-AABB "top plane" fallback slices THROUGH the
    body interior — a bio surface planted there is garbage that would still
    validate. Without a builder-declared FaceWindow for the target region,
    refuse loudly instead of producing it."""
    if (
        form.windows.get(use.target) is None
        and form.print_orientation == "side_profile"
    ):
        return fail(
            use.id,
            f"region {use.target!r} has no declared face window; "
            f"side-profile bodies get {modifier_label} in Bio-3 "
            "(oriented windows) — the AABB fallback would slice through "
            "the body interior",
        )
    return None


def _masks(form: PartForm, pw: PlateWindow) -> tuple[Region2D, ...]:
    """The exoskeleton's semantic keepout mask. On a developable
    profile_surface, fastener columns and cord slots are projected into
    (s, x) as conservative supersets; for a horizontal panel the local
    (a, b) frame IS world (x, y), so the wider-role region sweep applies; an
    oriented FaceWindow's local frame does not match world projections, so
    only the builder-declared local keepouts (plus prior cuts already inside
    them) are trusted."""
    if pw.mapping == "profile_surface" and pw.surface is not None:
        return profile_surface_keepout_mask(
            form, pw.surface, pw.window, extra=pw.keepouts
        )
    if pw.origin is not None:
        return tuple(pw.keepouts)
    return semantic_keepout_mask(
        form,
        pw.window,
        z_range=(pw.z_top - pw.depth, pw.z_top),
        extra=pw.keepouts,
    )


@register_applicator("apply_biomorphic_exoskeleton")
def apply_biomorphic_exoskeleton(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    gap = side_profile_window_gap(form, use, "exoskeleton growth")
    if gap is not None:
        return [gap]
    if pw.mapping == "cylindrical":
        return [fail(use.id, "exoskeleton v1 grows on planar panels only — "
                             "cylindrical/curved mapping is Bio-5 scope")]
    if form.exoskeleton is not None:
        return [fail(use.id, f"form already carries an exoskeleton on region "
                             f"{form.exoskeleton.region!r} — one skeleton per part")]

    findings: list[Finding] = []
    region = form.region(use.target)
    if region is not None and region.role is RegionRole.AESTHETIC_LIGHTENING:
        findings.append(note(
            use.id,
            f"fallback target: {use.target!r} is aesthetic_lightening, not "
            "an exoskeleton_panel — growing on the lightening zone",
        ))

    seed = _resolve_seed(params, form)
    organicity = float(params.get("organicity", 0.5))
    rib_density = float(params.get("rib_density", 0.5))
    window_scale = float(params.get("window_scale", 0.8))
    rib_d_root = float(params.get("rib_d_root", 6.0))
    rib_d_tip = float(params.get("rib_d_tip", 3.0))
    node_blend = float(params.get("node_blend", 2.0))
    min_ligament = float(params.get("min_ligament", 2.0))
    on_surface = pw.mapping == "profile_surface" and pw.surface is not None
    # organicity drives the sample jitter: 0 = near-regular grid growth,
    # 1 = wild scatter; 0.5 keeps the historical 0.35 fraction.
    jitter = 0.15 + 0.4 * organicity
    if rib_d_tip > rib_d_root:
        findings.append(note(
            use.id,
            f"rib_d_tip {rib_d_tip:g} > rib_d_root {rib_d_root:g} — "
            f"clamped tip to {rib_d_root:g} (ribs cannot grow toward "
            "their tips)",
        ))
        rib_d_tip = rib_d_root

    masks = _masks(form, pw)
    w, h = pw.window.width, pw.window.height
    pitch = max(6.0, min(w, h) / (4.0 + 8.0 * rib_density))
    substrate = build_substrate(
        form, archetype, pw.window, masks,
        pitch=pitch, seed=seed, jitter=jitter,
        origin=pw.origin, tilt_deg=pw.tilt_deg,
        to_local=pw.surface.to_local if on_surface else None,
    )
    if not substrate.samples:
        return [*findings, fail(
            use.id,
            f"zero surface samples survived the masks on {use.target!r} "
            f"({w:.0f}x{h:.0f}mm window, pitch {pitch:g}) — no room to grow",
        )]
    if not substrate.anchors:
        return [*findings, fail(
            use.id,
            f"no anchor points on {use.target!r} — every rib root landing "
            "site is masked; the skeleton would float",
        )]

    graph = surface_rib_graph(substrate, masks, rib_density=rib_density, seed=seed)
    graph = load_path_guided_ribs(
        graph, rib_d_root=rib_d_root, rib_d_tip=rib_d_tip, node_blend=node_blend
    )
    min_rib_d = rib_d_tip
    if on_surface:
        # Hierarchical ribs (Bio-4M stage B): load-path edges get the fat
        # PRIMARY diameter, the rest the SECONDARY diameter — a flat
        # override of the taper baseline. vein_rib_d (a third tier of thin
        # veins along the window rims) is DECLARED but MVP-deferred until the
        # first visual pass — nothing is emitted for it yet.
        primary_rib_d = float(params.get("primary_rib_d", 7.0))
        secondary_rib_d = float(params.get("secondary_rib_d", 4.0))
        lp = set(graph.load_path_edges)
        primary_bias = bool(params.get("primary_bias_to_load_paths", True))
        new_radii = [
            (primary_rib_d if (primary_bias and e in lp) else secondary_rib_d)
            / 2.0
            for e in graph.edges
        ]
        blends = node_blend_radii(
            len(graph.nodes), graph.edges, tuple(new_radii), node_blend
        )
        graph = replace(
            graph, edge_radius=tuple(new_radii), node_blend_radius=blends
        )
        min_rib_d = min(primary_rib_d, secondary_rib_d)
    windows = organic_window_field(
        graph, substrate, masks,
        window_scale=window_scale, min_ligament=min_ligament,
    )

    form.exoskeleton = ExoskeletonIR(
        region=use.target,
        window=pw.window,
        origin=pw.origin,
        tilt_deg=pw.tilt_deg,
        depth=pw.depth,
        graph=graph,
        windows=windows,
        masks=masks,
        samples=substrate.samples,
        anchors=substrate.anchors,
        load_seeds=substrate.load_seeds,
        min_ligament=min_ligament,
        min_rib_d=min_rib_d,
        seed=seed,
        load_paths=substrate.load_paths,
        plane_z=pw.z_top,
        mapping=pw.mapping if on_surface else "planar",
        surface=pw.surface if on_surface else None,
    )
    form.fields.append(FieldFeature(
        plane_z=pw.z_top,
        centers=(),
        cell=0.0,
        depth=pw.depth,
        pattern="organic",
        window=pw.window,
        keepouts=masks,
        polygons=windows,
        min_ligament=min_ligament,
        origin=pw.origin,
        tilt_deg=pw.tilt_deg,
        mapping=pw.mapping if on_surface else "planar",
        surface=pw.surface if on_surface else None,
    ))
    findings.append(note(
        use.id,
        f"exoskeleton IR on {use.target}: {len(graph.nodes)} nodes, "
        f"{len(graph.edges)} edges ({len(graph.load_path_edges)} on load "
        f"paths), {len(graph.root_nodes)} roots, {len(windows)} organic "
        f"window(s), seed {seed}",
    ))
    if on_surface:
        # Honesty (review edit): the clamp body is solid — organic windows
        # are RECESSES, not through-cuts (a through-cut would breach the
        # saddle/channel). Publish the mode + reason so the report/Cockpit
        # never promises the reference's see-through windows.
        findings.append(note(
            use.id,
            "organic_windows: mode=recessed through_cuts=false reason="
            "protecting saddle/channel; safe_recess "
            f"{pw.depth:.2f}mm (lip_radius {float(params.get('lip_radius', 2.0)):g}mm)",
        ))
        shadow_min = float(params.get("inner_shadow_depth_min", 2.5))
        if pw.depth < shadow_min:
            findings.append(_warn(
                use.id,
                f"window recess {pw.depth:.2f}mm < inner_shadow_depth_min "
                f"{shadow_min:g}mm — organic windows read as shallow "
                "engraving, not deep shadow (quality.window_shadow_present)",
            ))
    return findings


@register_applicator("add_bone_windows")
def add_bone_windows(
    form: PartForm, use: ModifierUse, params: dict[str, Any], archetype: ArchetypeSpec
) -> list[Finding]:
    """Bone-like organic perforation without a rib graph: the existing
    seeded voronoi pipeline with heavy corner smoothing, scaled about each
    cell's centroid, against the exoskeleton-strict keepout mask."""
    pw = plate_window(form, use.target)
    if pw is None:
        return [fail(use.id, f"target region {use.target!r} has no usable window")]
    gap = side_profile_window_gap(form, use, "bone windows")
    if gap is not None:
        return [gap]
    if pw.mapping == "cylindrical":
        return [fail(use.id, "bone windows v1 cut planar panels only — "
                             "cylindrical mapping is Bio-5 scope")]
    seed = int(round(params.get("seed", 42)))
    min_ligament = float(params.get("min_ligament", 2.2))
    window_scale = float(params.get("window_scale", 0.85))
    masks = _masks(form, pw)
    cells = voronoi_cells(
        pw.window,
        list(masks),
        seed=seed,
        sites=int(round(params.get("sites", 14))),
        min_ligament=min_ligament,
        edge_margin=float(params.get("edge_margin", 2.0)),
        corner_smooth=int(round(params.get("corner_smooth", 3))),
        # bone windows are a SCATTER against a heavy keepout mask, not a
        # coverage field: a jittered grid dies in lockstep where the mask
        # is wide; the uniform scatter finds the free pockets (Bio-4M canon)
        init="random",
    )
    scale = max(0.0, min(window_scale, 1.0))
    polygons: list[tuple[tuple[float, float], ...]] = []
    for cell in cells:
        cx, cy = _centroid(cell)
        polygons.append(tuple(
            (cx + (x - cx) * scale, cy + (y - cy) * scale) for x, y in cell
        ))
    # Final gate with the CHECKER'S OWN rule: voronoi_cells clears the
    # ORIGINAL cell edges, but scaling toward the centroid can drag an edge
    # into a mask that intrudes the cell interior (caught on the clamp's
    # bolt-column masks). Generator and checker must share one truth —
    # poly_clear is exactly what form.windows_inside_safe_regions samples.
    cleared = [p for p in polygons if poly_clear(p, masks)]
    dropped = len(polygons) - len(cleared)
    polygons = cleared
    on_surface = pw.mapping == "profile_surface" and pw.surface is not None
    form.fields.append(FieldFeature(
        plane_z=pw.z_top,
        centers=(),
        cell=0.0,
        depth=pw.depth,
        pattern="organic",
        window=pw.window,
        keepouts=masks,
        polygons=tuple(polygons),
        min_ligament=min_ligament,
        origin=pw.origin,
        tilt_deg=pw.tilt_deg,
        mapping=pw.mapping if on_surface else "planar",
        surface=pw.surface if on_surface else None,
    ))
    out = [note(
        use.id,
        f"{len(polygons)} bone window(s) (seed {seed}, scale {scale:g}) "
        f"on {use.target}"
        + (f"; {dropped} cell(s) dropped by the keepout gate" if dropped else ""),
    )]
    if on_surface:
        out.append(note(
            use.id,
            "organic_windows: mode=recessed through_cuts=false reason="
            f"protecting saddle/channel; safe_recess {pw.depth:.2f}mm",
        ))
    return out
