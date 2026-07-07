"""Voxel grid evaluation + marching cubes + mesh checks (numpy, lazy skimage).

The grid is padded by 2 voxels of guaranteed-outside space on every side,
so the marching-cubes surface is CLOSED by construction. Values evaluate
in float64 chunks and store as float32 — a pure function of (recipe,
grid plan), which is what makes the exported STL byte-deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

#: Hard budget on grid size (review #2): one unlucky parameter must not
#: make a build unbuildable — exceeding it auto-coarsens with a WARN note.
MAX_VOXELS = 16_000_000

#: Guaranteed-outside padding voxels per side (closed MC surface).
PAD_VOXELS = 2

#: Points per evaluation chunk (~memory bound, not a correctness knob).
CHUNK_POINTS = 2_000_000

Vec3 = tuple[float, float, float]


@dataclass
class GridPlan:
    origin: Vec3
    shape: tuple[int, int, int]
    resolution: float
    notes: list[str] = field(default_factory=list)

    @property
    def voxel_count(self) -> int:
        nx, ny, nz = self.shape
        return nx * ny * nz

    def axes(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        ox, oy, oz = self.origin
        nx, ny, nz = self.shape
        r = self.resolution
        return (
            ox + np.arange(nx, dtype=np.float64) * r,
            oy + np.arange(ny, dtype=np.float64) * r,
            oz + np.arange(nz, dtype=np.float64) * r,
        )


def _shape_for(bounds: tuple[Vec3, Vec3], res: float) -> tuple[Vec3, tuple[int, int, int]]:
    lo, hi = bounds
    origin = tuple(lo[i] - PAD_VOXELS * res for i in range(3))
    shape = tuple(
        int(math.ceil((hi[i] - lo[i]) / res)) + 2 * PAD_VOXELS + 1 for i in range(3)
    )
    return origin, shape  # type: ignore[return-value]


def plan_grid(
    bounds: tuple[Vec3, Vec3],
    resolution: float,
    feature_limit: float | None = None,
    max_voxels: int = MAX_VOXELS,
) -> GridPlan:
    """Resolution guards, in order: (1) auto-REFINE when the requested
    voxel is too coarse for the thinnest declared feature
    (res <= min(min_rib_d/2, min_ligament)/3); (2) auto-COARSEN when the
    grid would blow the voxel budget. Both leave an honest note."""
    notes: list[str] = []
    res = float(resolution)
    if feature_limit is not None and feature_limit > 0 and res > feature_limit + 1e-9:
        notes.append(
            f"skin_resolution {res:g}mm too coarse for the thinnest feature — "
            f"auto-refined to {feature_limit:g}mm"
        )
        res = feature_limit
    origin, shape = _shape_for(bounds, res)
    count = shape[0] * shape[1] * shape[2]
    while count > max_voxels:
        res *= (count / max_voxels) ** (1.0 / 3.0) * 1.02
        origin, shape = _shape_for(bounds, res)
        new_count = shape[0] * shape[1] * shape[2]
        notes.append(
            f"WARN: voxel budget {max_voxels} exceeded ({count}) — "
            f"auto-coarsened resolution to {res:.3f}mm ({new_count} voxels); "
            "thin features may lose fidelity"
        )
        count = new_count
    return GridPlan(origin=origin, shape=shape, resolution=res, notes=notes)


def eval_grid(fn: Callable[[np.ndarray], np.ndarray], plan: GridPlan) -> np.ndarray:
    """Evaluate ``fn`` (an (N,3)->(N,) SDF) over the grid in float64
    chunks, returning a float32 (nx, ny, nz) array."""
    nx, ny, nz = plan.shape
    xs, ys, zs = plan.axes()
    values = np.empty((nx, ny, nz), dtype=np.float32)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    per_slice = nx * ny
    slab = max(1, CHUNK_POINTS // max(per_slice, 1))
    for k0 in range(0, nz, slab):
        zb = zs[k0 : k0 + slab]
        k = len(zb)
        P = np.empty((per_slice * k, 3), dtype=np.float64)
        P[:, 0] = np.broadcast_to(X[:, :, None], (nx, ny, k)).reshape(-1)
        P[:, 1] = np.broadcast_to(Y[:, :, None], (nx, ny, k)).reshape(-1)
        P[:, 2] = np.broadcast_to(zb[None, None, :], (nx, ny, k)).reshape(-1)
        values[:, :, k0 : k0 + k] = fn(P).reshape(nx, ny, k).astype(np.float32)
    return values


def marching_cubes_mesh(
    values: np.ndarray, plan: GridPlan
) -> tuple[np.ndarray, np.ndarray]:
    """Extract the zero level set (Lewiner marching cubes) as
    (verts (V,3) float64 world coords, faces (F,3) int). Exact grid zeros
    are nudged outside by 1e-6 so no degenerate zero-area configuration
    survives; duplicate vertices are merged and degenerate faces dropped —
    all deterministically."""
    from skimage import measure  # lazy: cad-extra dependency

    vals = values.copy()
    vals[vals == 0.0] = np.float32(1e-6)
    r = plan.resolution
    verts, faces, _normals, _vals = measure.marching_cubes(
        vals,
        level=0.0,
        spacing=(r, r, r),
        gradient_direction="ascent",  # SDF: exterior > interior
        allow_degenerate=False,
        method="lewiner",
    )
    verts = verts.astype(np.float64) + np.asarray(plan.origin, dtype=np.float64)
    # Lewiner with allow_degenerate=False is 2-manifold IN INDEX SPACE
    # already (vertices shared per grid edge). A positional np.unique merge
    # can fuse near-coincident but topologically DISTINCT vertices, and
    # dropping the resulting sliver faces opens boundary edges — that was
    # the source of hundreds of non-manifold edges on the clamp halves.
    # Ship the mesh exactly as extracted.
    return verts, faces.astype(np.int64)


def mesh_watertight(verts: np.ndarray, faces: np.ndarray) -> tuple[bool, dict]:
    """Edge-manifold watertightness on our own arrays: every undirected
    edge borders exactly two triangles, and every directed edge appears
    exactly once (consistent orientation)."""
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]], axis=0)
    und = np.sort(e, axis=1)
    _, und_counts = np.unique(und, axis=0, return_counts=True)
    _, dir_counts = np.unique(e, axis=0, return_counts=True)
    bad_und = int(np.count_nonzero(und_counts != 2))
    bad_dir = int(np.count_nonzero(dir_counts != 1))
    stats = {
        "vertices": int(len(verts)),
        "triangles": int(len(faces)),
        "undirected_edges": int(len(und_counts)),
        "edges_not_2_manifold": bad_und,
        "directed_edge_conflicts": bad_dir,
    }
    return bad_und == 0 and bad_dir == 0, stats


def mesh_feature_stats(verts: np.ndarray, faces: np.ndarray) -> dict:
    """Informational facet statistics (manufacturing.mesh_min_feature)."""
    tri = verts[faces]
    e0 = np.linalg.norm(tri[:, 1] - tri[:, 0], axis=1)
    e1 = np.linalg.norm(tri[:, 2] - tri[:, 1], axis=1)
    e2 = np.linalg.norm(tri[:, 0] - tri[:, 2], axis=1)
    edges = np.concatenate([e0, e1, e2])
    areas = 0.5 * np.linalg.norm(
        np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1
    )
    return {
        "min_edge_mm": float(edges.min()) if len(edges) else 0.0,
        "median_edge_mm": float(np.median(edges)) if len(edges) else 0.0,
        "min_triangle_area_mm2": float(areas.min()) if len(areas) else 0.0,
        "total_area_mm2": float(areas.sum()),
    }


def orient_vertices_for_print(verts: np.ndarray, form) -> np.ndarray:
    """Mirrors ``compiler.pipeline.orient_for_print`` EXACTLY for the
    rotation (side_profile: rotate -90 degrees about +Y), then drops to the
    bed by the MESH zmin. Documented difference from the BRep path: the
    skinned mesh stands proud of the BRep body, so its zmin (and therefore
    the drop) can differ by the proud amount."""
    if getattr(form, "print_orientation", "as_modeled") != "side_profile":
        return verts
    out = np.empty_like(verts)
    # R_y(-90 deg): (x, y, z) -> (-z, y, x)
    out[:, 0] = -verts[:, 2]
    out[:, 1] = verts[:, 1]
    out[:, 2] = verts[:, 0]
    zmin = float(out[:, 2].min())
    if abs(zmin) > 1e-9:
        out[:, 2] -= zmin
    return out
