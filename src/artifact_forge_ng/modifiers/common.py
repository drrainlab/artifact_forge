"""Shared applicator plumbing — resolving a semantic region into a working
window and deriving keepouts from the protected regions around it. This is
the "modifier checks target region -> computes keepouts" half of the
anti-hallucination chain; the compiler and validators are the other half.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.findings import Finding, Level, Status
from ..form.part import PartForm, PlateFeature
from ..form.regions import Circle2D, Rect2D, Region2D
from ..form.section import Pt
from ..product.archetype import RegionRole

PROTECTED_ROLES = frozenset(
    {RegionRole.FASTENER_KEEPOUT, RegionRole.HIGH_STRESS_REGION}
)


def fail(modifier_id: str, message: str) -> Finding:
    return Finding(
        check=f"modifier:{modifier_id}",
        status=Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=True,
    )


def note(modifier_id: str, message: str) -> Finding:
    return Finding(
        check=f"modifier:{modifier_id}",
        status=Status.PASS,
        level=Level.FORM,
        message=message,
    )


@dataclass(frozen=True)
class PlateWindow:
    """A modifier's working area on a horizontal face."""

    window: Rect2D  # in (x, y)
    z_top: float
    depth: float  # host material depth under the face
    keepouts: tuple[Region2D, ...]


def plate_window(
    form: PartForm, region_name: str, keepout_clearance: float = 0.0
) -> PlateWindow | None:
    """Resolve a region into a top-face window plus keepouts. Returns None
    when the region is missing or unusable (the applicator reports it)."""
    region = form.region(region_name)
    if region is None:
        return None
    b = region.box
    if not all(map(math.isfinite, (b.x0, b.y0, b.x1, b.y1, b.z1))):
        return None
    window = Rect2D(b.x0, b.y0, b.x1, b.y1)
    host: PlateFeature | None = None
    for plate in form.plates:
        if plate.z_bottom - 1e-6 <= b.z1 <= plate.z_top + 1e-6:
            host = plate
            break
    depth = host.thickness if host else max(0.0, b.z1 - (b.z0 if math.isfinite(b.z0) else b.z1))
    return PlateWindow(
        window=window,
        z_top=b.z1,
        depth=depth,
        keepouts=tuple(derive_keepouts(form, window, keepout_clearance)),
    )


def derive_keepouts(
    form: PartForm, window: Rect2D, clearance: float = 0.0
) -> list[Region2D]:
    """Every protected region overlapping the window (projected to XY),
    plus a circle per fastener hole — belt and suspenders."""
    keepouts: list[Region2D] = []
    for region in form.regions:
        if region.role not in PROTECTED_ROLES:
            continue
        b = region.box
        if not all(map(math.isfinite, (b.x0, b.y0, b.x1, b.y1))):
            continue
        rect = Rect2D(b.x0, b.y0, b.x1, b.y1)
        if (
            rect.u1 < window.u0 or rect.u0 > window.u1
            or rect.v1 < window.v0 or rect.v0 > window.v1
        ):
            continue
        keepouts.append(
            Region2D(region.name, region.role, rect, clearance=clearance)
        )
    head_r = form.frame.get("screw_head_r", 3.5)
    for i, hole in enumerate(form.holes):
        keepouts.append(
            Region2D(
                f"hole_{i}",
                RegionRole.FASTENER_KEEPOUT,
                Circle2D(Pt(hole.at[0], hole.at[1]), head_r + 2.0),
                clearance=clearance,
            )
        )
    return keepouts
