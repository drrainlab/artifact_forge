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
    """Printed flange-down, a ROUND cavity ceiling is a bridged circular
    span whose lowest quadrant approaches 90-degree overhang — small spans
    bridge, larger ones sag. A TEARDROP cavity is self-supporting at 45
    degrees by construction. Heuristics documented, replaceable by mesh
    analysis."""
    if form.frame.get("cavity_teardrop", 0.0) >= 0.5:
        return _finding(
            "manufacturing.overhang", Status.PASS,
            "self-supporting 45deg teardrop cavity roof — no supports",
            measured=45.0, limit=45.0,
        )
    span = 2.0 * form.frame.get("r_cavity", 0.0)
    if span <= 0.0:
        return _finding(
            "manufacturing.overhang", Status.PASS, "no cavity to bridge"
        )
    if span <= 12.0:
        return _finding(
            "manufacturing.overhang", Status.PASS,
            f"round cavity span {span:.1f} mm — trivial bridge",
            measured=span, limit=12.0,
        )
    if span <= 35.0:
        return _finding(
            "manufacturing.overhang", Status.WARN,
            f"round cavity roof spans {span:.1f} mm — relies on bridging "
            "(near-90deg local overhang at the roof sides)",
            measured=span, limit=12.0,
            suggestion="cavity_roof: teardrop (the make_support_free edit)",
        )
    return _finding(
        "manufacturing.overhang", Status.FAIL,
        f"round cavity span {span:.1f} mm needs support",
        measured=span, limit=35.0,
        suggestion="cavity_roof: teardrop, or support_policy: allow",
    )
