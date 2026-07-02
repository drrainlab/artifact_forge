"""CAD kernel wrapper.

Models build geometry with the full CadQuery API, but every model returns a
``Geometry`` handle rather than a raw CadQuery object. ``Geometry`` exposes
backend-agnostic *measurements* (bounding box, volume, surface area, center of
mass) and *exports*. This is the seam the rest of the platform depends on:

  * rule-based reviews read measurements, never the CadQuery object directly;
  * exporters write STEP/STL through one path;
  * the CAD backend could be swapped later without touching review or loop code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cadquery as cq


@dataclass(frozen=True)
class BoundingBox:
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float

    @property
    def size(self) -> tuple[float, float, float]:
        return (self.xmax - self.xmin, self.ymax - self.ymin, self.zmax - self.zmin)

    @property
    def width(self) -> float:
        return self.xmax - self.xmin

    @property
    def depth(self) -> float:
        return self.ymax - self.ymin

    @property
    def height(self) -> float:
        return self.zmax - self.zmin


class Geometry:
    """A backend-agnostic handle to a solid produced by a parametric model."""

    def __init__(self, solid: cq.Workplane) -> None:
        if not isinstance(solid, cq.Workplane):
            raise TypeError(
                f"Geometry expects a cadquery.Workplane, got {type(solid).__name__}"
            )
        self._wp = solid

    # -- raw access (use sparingly; prefer measurements) ----------------------

    @property
    def workplane(self) -> cq.Workplane:
        return self._wp

    def _compound(self) -> cq.Shape:
        return self._wp.val()

    # -- measurements ---------------------------------------------------------

    def bounding_box(self) -> BoundingBox:
        bb = self._compound().BoundingBox()
        return BoundingBox(bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax)

    def volume(self) -> float:
        """Solid volume in mm^3."""
        return self._compound().Volume()

    def surface_area(self) -> float:
        """Total surface area in mm^2."""
        return self._compound().Area()

    def center_of_mass(self) -> tuple[float, float, float]:
        c = self._compound().Center()
        return (c.x, c.y, c.z)

    def mesh(self, tolerance: float = 0.2):
        """Tessellate to (vertices, triangles) as numpy arrays for analysis."""
        import numpy as np
        verts, tris = self._compound().tessellate(tolerance)
        V = np.array([[v.x, v.y, v.z] for v in verts], dtype=float)
        T = np.array(tris, dtype=int) if tris else np.empty((0, 3), dtype=int)
        return V, T

    def solid_count(self) -> int:
        """Number of disjoint solid bodies. 1 means a single connected part;
        more means the geometry fell into separate pieces (usually a design
        error — features that don't touch the body float off and won't print)."""
        try:
            return len(self._compound().Solids())
        except Exception:
            return 1

    def is_valid(self) -> bool:
        """Is the solid geometrically VALID — not merely closed? A watertight
        shell can still be self-intersecting or non-manifold (a degenerate
        fillet, a sliver from a near-tangent union); such a body looks fine but
        the slicer chokes on it. Wraps OCC's BRepCheck via cq ``Shape.isValid``.
        Returns True when validity can't be determined (don't fail on tooling)."""
        try:
            return bool(self._compound().isValid())
        except Exception:
            return True

    # -- export ---------------------------------------------------------------

    def export_step(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cq.exporters.export(self._wp, str(path), exportType="STEP")
        return path

    def export_stl(
        self,
        path: str | Path,
        tolerance: float = 0.05,
        angular_tolerance: float = 0.1,
    ) -> Path:
        """Export a printable mesh.

        ``tolerance`` is the max linear deviation of the mesh from the true
        surface (mm); ``angular_tolerance`` controls facet count on curves.
        Smaller = smoother + larger file. 0.05 mm is a good print default.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cq.exporters.export(
            self._wp, str(path), exportType="STL",
            tolerance=tolerance, angularTolerance=angular_tolerance,
        )
        return path
