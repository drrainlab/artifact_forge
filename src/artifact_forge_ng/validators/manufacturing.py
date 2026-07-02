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


#: Lip ledges shorter than this print acceptably without support even as
#: horizontal cantilevers (a few sagging perimeter loops, cosmetic only).
LIP_CANTILEVER_OK = 8.0


@register_probe("manufacturing.overhang")
def overhang(geometry: Geometry, form: PartForm) -> Finding:
    """Overhang honesty, per PRINT ORIENTATION.

    side_profile: a constant-section extrusion printed profile-on-bed has
    zero overhangs BY CONSTRUCTION — every layer is the same shape. The
    claim is only made when the section really is constant (no plates,
    ribs, cuts or fields; small transverse holes bridge natively).

    flange-down (the side-hook family default): two distinct problems —
    the cavity roof (round = bridged circular span, teardrop = self-
    supporting 45deg) AND the lips, which print as horizontal cantilever
    ledges hanging over the mouth. A slicer will ask for supports under a
    long lower lip no matter what the cavity roof does; the honest fix is
    the sideprint variant, not more chamfers. Lesson from a real slicer
    session: the first version of this check modeled only the cavity."""
    if form.print_orientation == "side_profile":
        breakers = [
            label
            for label, items in (
                ("plates", form.plates), ("ribs", form.ribs),
                ("cutboxes", form.cutboxes), ("bores", form.bores),
                ("fields", form.fields),
            )
            if items
        ]
        if form.kind != "section_extrude" or breakers:
            return _finding(
                "manufacturing.overhang", Status.WARN,
                "side-print orientation, but the part is not a pure "
                f"extrusion ({', '.join(breakers) or form.kind}) — "
                "overhangs unverified",
                suggestion="keep sideprint parts constant-section",
            )
        return _finding(
            "manufacturing.overhang", Status.PASS,
            "profile-on-bed: constant section along the vertical axis — no "
            "overhangs by construction; screw holes print as short "
            "horizontal bores. Note: lip flexure crosses layers in this "
            "orientation — use 3+ perimeters",
            measured=0.0, limit=45.0,
        )

    problems: list[str] = []
    worst = Status.PASS
    suggestion = ""

    span = 2.0 * form.frame.get("r_cavity", 0.0)
    if span > 0.0:
        if form.frame.get("cavity_teardrop", 0.0) >= 0.5:
            problems.append("teardrop cavity roof self-supporting at 45deg")
        elif span <= 12.0:
            problems.append(f"round cavity span {span:.1f} mm — trivial bridge")
        elif span <= 35.0:
            problems.append(
                f"round cavity roof spans {span:.1f} mm — relies on bridging "
                "(near-90deg local overhang at the roof sides)"
            )
            worst = Status.WARN
            suggestion = "cavity_roof: teardrop, or the sideprint variant"
        else:
            problems.append(f"round cavity span {span:.1f} mm needs support")
            worst = Status.FAIL
            suggestion = "the sideprint variant, or support_policy: allow"

    lip = form.frame.get("lower_lip_tip_u", 0.0) - form.frame.get(
        "wall_outer_u", 0.0
    )
    if form.frame.get("lower_lip_tip_u") is not None and lip > LIP_CANTILEVER_OK:
        problems.append(
            f"the {lip:.0f} mm lower lip prints as a horizontal cantilever "
            "flange-down — slicers will ask for supports under the lips"
        )
        if worst is Status.PASS:
            worst = Status.WARN
        if not suggestion:
            suggestion = (
                "the sideprint variant prints this hook support-free "
                "(intent make_support_free)"
            )

    if not problems:
        return _finding(
            "manufacturing.overhang", Status.PASS, "no overhang-prone features"
        )
    return _finding(
        "manufacturing.overhang", worst,
        "; ".join(problems),
        measured=span if span > 0 else None,
        suggestion=suggestion,
    )
