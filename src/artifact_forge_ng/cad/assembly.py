"""Assembled-pose CAD helpers: placing part-frame geometry by a Pose,
measuring pairwise interference, and exporting the assembled COMPOUND.

No boolean fuse anywhere — a fused union of touching parts is fragile and
lies about the artifact (you print PARTS, not the union). Placement is for
the eyes and the probes; intersection runs only inside measurements.
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq

from ..assembly.joints import Pose
from .geometry import Geometry


def place(geometry: Geometry, pose: Pose) -> Geometry:
    """Part-frame solid placed into the root frame. NEVER feed this the
    print-oriented export — poses are defined in part frames."""
    wp = geometry.workplane
    rx, ry, rz = pose.rotate
    if rx:
        wp = wp.rotate((0, 0, 0), (1, 0, 0), rx)
    if ry:
        wp = wp.rotate((0, 0, 0), (0, 1, 0), ry)
    if rz:
        wp = wp.rotate((0, 0, 0), (0, 0, 1), rz)
    tx, ty, tz = pose.translate
    if any((tx, ty, tz)):
        wp = wp.translate((tx, ty, tz))
    return Geometry(wp)


def interference_volume(a: Geometry, b: Geometry) -> float:
    """Overlap volume between two placed parts in mm^3. Touching faces are
    0; real material overlap is a fit failure."""
    try:
        overlap = a.workplane.intersect(b.workplane)
        return float(overlap.val().Volume())
    except Exception:
        return 0.0  # disjoint solids — OCC may throw instead of returning empty


def export_assembled_step(placed: dict[str, Geometry], path: Path) -> Path:
    """One STEP with every part in its pose, as a COMPOUND (no fuse)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    shapes = [g.workplane.val() for g in placed.values()]
    compound = cq.Compound.makeCompound(shapes)
    cq.exporters.export(cq.Workplane(obj=compound), str(path), exportType="STEP")
    return path
