"""Manufacturing validators — FAILs here cap the grade but do not trip the
critical product-identity gate (that's contract/topology/region territory).
"""

from __future__ import annotations

from ..cad.geometry import Geometry
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from .probes import register_probe

BED = (220.0, 220.0, 250.0)


def _finding(check: str, status: Status, message: str, *, measured: float | None = None,
             limit: float | None = None, suggestion: str = "") -> Finding:
    return Finding(
        check=check, status=status, level=Level.MANUFACTURING, message=message,
        measured=measured, limit=limit, suggestion=suggestion,
        unit="mm" if measured is not None else "",
    )


@register_probe("manufacturing.bed_fit")
def bed_fit(geometry: Geometry, form: PartForm) -> Finding:
    bb = geometry.bounding_box()
    size = sorted(bb.size, reverse=True)
    bed = sorted(BED, reverse=True)
    ok = all(s <= b + 1e-6 for s, b in zip(size, bed))
    return _finding(
        "manufacturing.bed_fit",
        Status.PASS if ok else Status.FAIL,
        f"part {size[0]:.0f}x{size[1]:.0f}x{size[2]:.0f} vs bed {bed[0]:.0f}x{bed[1]:.0f}x{bed[2]:.0f}",
        measured=size[0],
        limit=bed[0],
    )


@register_probe("manufacturing.min_wall")
def min_wall(geometry: Geometry, form: PartForm) -> Finding:
    """Thinnest designed feature vs the printer's wall floor. Analytic (the
    IR knows its own thinnest member — the tapered lower lip tip); a mesh
    raycast can replace this later without changing the check name."""
    wall = form.params.get("wall")
    floor = form.params.get("printer_min_wall", 1.2)
    if wall is None:
        return _finding("manufacturing.min_wall", Status.WARN, "wall unknown")
    thinnest = min(wall, wall * 0.7)  # lower lip tip taper
    ok = thinnest >= floor - 1e-6
    return _finding(
        "manufacturing.min_wall",
        Status.PASS if ok else Status.FAIL,
        f"thinnest designed wall {thinnest:.2f} vs printer floor {floor:.2f}",
        measured=thinnest,
        limit=floor,
        suggestion="" if ok else "increase wall or use a larger nozzle",
    )


@register_probe("manufacturing.overhang")
def overhang(geometry: Geometry, form: PartForm) -> Finding:
    """Printed flange-down, the cavity ceiling is a bridged circular span.
    Heuristic thresholds (documented, replaceable by mesh analysis):
    span <= 25 mm bridges fine; 25-35 warns; beyond that needs support."""
    span = 2.0 * form.frame.get("r_cavity", 0.0)
    if span <= 25.0:
        return _finding(
            "manufacturing.overhang", Status.PASS,
            f"cavity bridge span {span:.1f} mm — printable without support",
            measured=span, limit=25.0,
        )
    if span <= 35.0:
        return _finding(
            "manufacturing.overhang", Status.WARN,
            f"cavity bridge span {span:.1f} mm — expect some sag",
            measured=span, limit=25.0,
            suggestion="reduce bundle_d or allow supports",
        )
    return _finding(
        "manufacturing.overhang", Status.FAIL,
        f"cavity bridge span {span:.1f} mm needs support",
        measured=span, limit=35.0,
        suggestion="allow supports (support_policy: allow) or split the archetype",
    )
