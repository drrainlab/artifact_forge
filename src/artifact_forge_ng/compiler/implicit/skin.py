"""export_implicit_skin — the Bio-4M orchestrator.

PartForm -> recipe -> voxel grid -> marching cubes -> print orientation ->
binary STL, plus every finding the skin stage owns (the probe DECLARATIONS
live in validators/probes.py with impl=None — these findings are the
implementations, emitted from here and appended to the report BEFORE the
honesty/score finalization).

Failure policy: anything that prevents an implicit export raises
:class:`ImplicitSkinError` — the pipeline converts it into a loud
PipelineFailure. Handing back a BRep STL under a skin request would be a
hallucination, and this module refuses to be one.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from ...core.findings import Finding, Level, Status
from ...form.part import PartForm
from .from_form import (
    INNER_SHADOW_DEPTH_MIN,
    ImplicitSkinError,
    ProbePoint,
    UnsupportedFormForImplicit,
    recipe_from_form,
)
from .mesh import (
    eval_grid,
    marching_cubes_mesh,
    mesh_feature_stats,
    mesh_watertight,
    orient_vertices_for_print,
    plan_grid,
)
from .stl import write_binary_stl

__all__ = [
    "ImplicitSkinError",
    "UnsupportedFormForImplicit",
    "export_implicit_skin",
]

#: rectangularity gate: at most this triangle-area fraction of the SKIN
#: CANVAS may face within AXIS_TOL_DEG of an axis direction.
RECTANGULARITY_MAX = 0.55
AXIS_TOL_DEG = 5.0

#: analytic probe sign margin (mm) — a probe point must clear the surface
#: by at least this much in its expected direction.
PROBE_MARGIN = 0.05


def export_implicit_skin(
    form: PartForm, stl_path: str | Path
) -> tuple[Path, list[Finding], dict]:
    """Returns (written STL path, findings, exports meta)."""
    try:
        import skimage  # noqa: F401  — lazy cad-extra dependency
    except ImportError as exc:
        raise ImplicitSkinError(
            "scikit-image (marching cubes) is not installed — "
            "install the [cad] extra"
        ) from exc

    recipe, probes, meta = recipe_from_form(form)

    # resolution guards (see mesh.plan_grid): feature refine + voxel budget
    min_rib_d = float(meta.get("min_rib_d", 0.0))
    min_ligament = float(meta.get("min_ligament", 0.0))
    limits = [v for v in (min_rib_d / 2.0, min_ligament) if v > 1e-9]
    feature_limit = (min(limits) / 3.0) if limits else None
    plan = plan_grid(recipe.bounds(), float(form.style.skin_resolution), feature_limit)

    values = eval_grid(recipe.evaluate, plan)
    verts, faces = marching_cubes_mesh(values, plan)

    findings: list[Finding] = []
    wt_ok, wt_stats = mesh_watertight(verts, faces)
    findings.append(Finding(
        check="manufacturing.mesh_watertight",
        status=Status.PASS if wt_ok else Status.FAIL,
        level=Level.MANUFACTURING,
        critical=not wt_ok,
        message=(
            f"{wt_stats['triangles']} triangles, "
            f"{wt_stats['undirected_edges']} edges — every edge 2-manifold, "
            "orientation consistent"
            if wt_ok
            else f"mesh NOT watertight: {wt_stats['edges_not_2_manifold']} "
            f"non-2-manifold edges, {wt_stats['directed_edge_conflicts']} "
            "orientation conflicts"
        ),
        measured=float(
            wt_stats["edges_not_2_manifold"] + wt_stats["directed_edge_conflicts"]
        ),
        limit=0.0,
    ))

    feat = mesh_feature_stats(verts, faces)
    findings.append(Finding(
        check="manufacturing.mesh_min_feature",
        status=Status.PASS,
        level=Level.MANUFACTURING,
        message=(
            "informational facet stats: min edge "
            f"{feat['min_edge_mm']:.4f}mm, median edge "
            f"{feat['median_edge_mm']:.3f}mm, min facet area "
            f"{feat['min_triangle_area_mm2']:.6f}mm2"
        ),
        measured=feat["min_edge_mm"],
        unit="mm",
    ))

    findings.append(_probe_finding(
        "manufacturing.implicit_skin_fidelity", recipe, probes.fidelity,
        "analytic SDF honors the IR (ribs solid, windows void, bolts exact)",
    ))
    findings.append(_probe_finding(
        "manufacturing.boss_growth_preserves_fastener_access", recipe, probes.boss,
        "grown bosses keep head seats, driver access and open bores",
    ))
    findings.append(_probe_finding(
        "manufacturing.skin_assembly_clearance", recipe, probes.clearance,
        "skin stays clear of the mating/mounting plane and the part outline",
    ))

    findings.append(_rectangularity_finding(recipe, verts, faces, meta))
    findings.append(_window_shadow_finding(meta))
    for note_msg in meta.get("shell_notes", []):
        # honest scope note (worded so the honesty pass collects it as an
        # engine gap: WARN + "no implementation").
        findings.append(Finding(
            check="skin.organic_base_shell",
            status=Status.WARN,
            level=Level.QUALITY,
            message=note_msg,
        ))

    oriented = orient_vertices_for_print(verts, form)
    path = write_binary_stl(stl_path, oriented, faces)

    meta.update({
        "resolution": plan.resolution,
        "grid": list(plan.shape),
        "voxels": plan.voxel_count,
        "vertices": int(len(verts)),
        "triangles": int(len(faces)),
        "stl_bytes": path.stat().st_size,
        "notes": list(plan.notes),
    })
    if form.print_orientation == "side_profile":
        meta["notes"].append(
            "drop-to-bed uses the MESH zmin — differs from the BRep zmin "
            "by the proud skin height (documented)"
        )
    return path, findings, meta


# ---------------------------------------------------------------------------
# finding builders
# ---------------------------------------------------------------------------


def _probe_finding(
    check: str, recipe, points: tuple[ProbePoint, ...], ok_summary: str
) -> Finding:
    if not points:
        return Finding(
            check=check, status=Status.PASS, level=Level.MANUFACTURING,
            message="no applicable probe points on this form (vacuous pass)",
        )
    P = np.asarray([p.xyz for p in points], dtype=np.float64)
    d = recipe.evaluate(P)
    bad: list[str] = []
    for point, dist in zip(points, d):
        if point.expect == "solid" and dist > -PROBE_MARGIN:
            bad.append(f"{point.label} (expected solid, sdf={dist:.3f})")
        elif point.expect == "void" and dist < PROBE_MARGIN:
            bad.append(f"{point.label} (expected void, sdf={dist:.3f})")
    if bad:
        shown = "; ".join(bad[:4]) + ("; ..." if len(bad) > 4 else "")
        return Finding(
            check=check, status=Status.FAIL, level=Level.MANUFACTURING,
            critical=True,
            message=f"{len(bad)}/{len(points)} analytic samples violated: {shown}",
            measured=float(len(bad)), limit=0.0,
        )
    return Finding(
        check=check, status=Status.PASS, level=Level.MANUFACTURING,
        message=f"{len(points)} analytic SDF samples pass: {ok_summary}",
        measured=0.0, limit=0.0,
    )


def _rectangularity_finding(
    recipe, verts: np.ndarray, faces: np.ndarray, meta: dict
) -> Finding:
    """Triangle-area-weighted fraction of SKIN-CANVAS surface whose normal
    lies within AXIS_TOL_DEG of +-X/+-Y/+-Z. Computed ONLY over triangles
    whose centroids sit inside the canvas (window minus masks, above the
    panel top) — mate faces, seats and rims are functionally flat and are
    not the skin's to cure (review #2). Planar canvases only: the metric
    is a GATE on the pre-flight demo plate and WARN-only elsewhere."""
    canvas = recipe.canvas
    if canvas is None:
        why = (
            "rectangularity over a curved profile_surface canvas: "
            "no implementation yet (Bio-5 scope)"
            if meta.get("mapping") == "profile_surface"
            else "no skin canvas on this recipe — metric not applicable"
        )
        return Finding(
            check="quality.rectangularity_reduced", status=Status.WARN,
            level=Level.QUALITY, message=why,
        )
    tri = verts[faces]
    centroids = tri.mean(axis=1)
    in_canvas = canvas.contains_world(centroids)
    if not bool(in_canvas.any()):
        return Finding(
            check="quality.rectangularity_reduced", status=Status.WARN,
            level=Level.QUALITY,
            message="no mesh triangles landed in the skin canvas",
        )
    tri = tri[in_canvas]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area2 = np.linalg.norm(n, axis=1)
    ok = area2 > 1e-12
    n_unit = n[ok] / area2[ok][:, None]
    w = area2[ok]
    cos_tol = math.cos(math.radians(AXIS_TOL_DEG))
    axis_aligned = np.max(np.abs(n_unit), axis=1) >= cos_tol
    fraction = float(w[axis_aligned].sum() / w.sum()) if w.sum() > 0 else 0.0
    passed = fraction < RECTANGULARITY_MAX
    return Finding(
        check="quality.rectangularity_reduced",
        status=Status.PASS if passed else Status.FAIL,
        level=Level.QUALITY,
        message=(
            f"{fraction:.3f} of skin-canvas area faces within "
            f"{AXIS_TOL_DEG:g} deg of an axis "
            f"({'below' if passed else 'NOT below'} the "
            f"{RECTANGULARITY_MAX:g} threshold; "
            f"{int(in_canvas.sum())} canvas triangles)"
        ),
        measured=fraction,
        limit=RECTANGULARITY_MAX,
    )


def _window_shadow_finding(meta: dict) -> Finding:
    depth = float(meta.get("window_depth_min", 0.0))
    n_windows = int(meta.get("window_prisms", 0))
    if n_windows == 0:
        return Finding(
            check="quality.window_shadow_present", status=Status.WARN,
            level=Level.QUALITY,
            message="no organic windows on this form — nothing to shadow",
        )
    deep = depth >= INNER_SHADOW_DEPTH_MIN
    mode = meta.get("organic_windows", {}).get("mode", "unknown")
    return Finding(
        check="quality.window_shadow_present",
        status=Status.PASS if deep else Status.WARN,
        level=Level.QUALITY,
        message=(
            f"window depth {depth:g}mm (mode: {mode}) "
            + (
                f">= {INNER_SHADOW_DEPTH_MIN:g}mm — reads as shadow"
                if deep
                else f"< {INNER_SHADOW_DEPTH_MIN:g}mm — shallow engraving, "
                "not a window shadow (honest warn)"
            )
        ),
        measured=depth,
        limit=INNER_SHADOW_DEPTH_MIN,
        unit="mm",
    )
