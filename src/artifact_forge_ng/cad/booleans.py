"""Boolean discipline — the v1 lip-overlap lesson as enforced API.

``weld`` is the ONLY sanctioned union: it asserts the result is still one
solid, so a body that merely touches (and would silently drop off) becomes
a loud error. ``keep_largest`` is the ported v1 ``_keep_one`` fragment
guard.
"""

from __future__ import annotations

import cadquery as cq

#: Minimum protrusion of any welded joint into its target solid.
WELD_OVERLAP = 0.6


class WeldError(RuntimeError):
    """A union produced a disconnected result — the joint never touched."""


def keep_largest(wp: cq.Workplane) -> cq.Workplane:
    solids = wp.solids().vals()
    if len(solids) <= 1:
        return wp
    return cq.Workplane("XY").newObject([max(solids, key=lambda s: s.Volume())])


def weld(base: cq.Workplane, addition: cq.Workplane, what: str = "part") -> cq.Workplane:
    fused = base.union(addition)
    solids = fused.solids().vals()
    if len(solids) != 1:
        raise WeldError(
            f"welding {what} produced {len(solids)} solids — the joint does "
            f"not overlap (needs >= {WELD_OVERLAP} mm of interpenetration)"
        )
    return fused


def cut_keep_solid(
    base: cq.Workplane, cutter: cq.Workplane
) -> tuple[cq.Workplane, bool]:
    """Cut, keeping the result only if it stays one valid solid; returns
    (result, applied). A cut that fragments or invalidates the body is
    reverted, never shipped."""
    try:
        result = base.cut(cutter)
        solids = result.solids().vals()
        if len(solids) == 1 and solids[0].isValid():
            return result, True
    except Exception:
        pass
    return base, False
