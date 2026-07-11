"""IR checks for bores and box cuts — keepout respect and wall sanity,
before any CAD. Self-registers in KNOWN_CHECKS on import.
"""

from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .part import BoreFeature, PartForm
from .regions import Box3, RegionRole

_PROTECTED_ROLES = frozenset(
    {RegionRole.FASTENER_KEEPOUT, RegionRole.HIGH_STRESS_REGION,
     RegionRole.BODY_CONTACT_SURFACE}
)


from .checks_common import make_finding
_finding = make_finding


def _bore_aabb(bore: BoreFeature) -> Box3:
    if bore.axis == "ANGLED":
        return bore.bbox()
    x, y, z = bore.center
    r = bore.d / 2.0
    lo, hi = bore.span
    if bore.axis == "X":
        return Box3(lo, y - r, z - r, hi, y + r, z + r)
    if bore.axis == "Y":
        return Box3(x - r, lo, z - r, x + r, hi, z + r)
    return Box3(x - r, y - r, lo, x + r, y + r, hi)


def _boxes_overlap(a: Box3, b: Box3) -> bool:
    return (
        a.x0 < b.x1 and b.x0 < a.x1
        and a.y0 < b.y1 and b.y0 < a.y1
        and a.z0 < b.z1 and b.z0 < a.z1
    )


def check_cuts_respect_keepouts(form: PartForm) -> Finding:
    """No bore or box cut may intersect a fastener-keepout or high-stress
    region. Builders never declare a keepout over an intended cut, so any
    overlap is a real conflict, not a false positive."""
    violations: list[str] = []
    protected = [r for r in form.regions if r.role in _PROTECTED_ROLES]
    cut_boxes: list[tuple[str, Box3]] = [
        (f"bore:{b.name}", _bore_aabb(b)) for b in form.bores
    ]
    cut_boxes.extend((f"cutbox:{c.name}", c.box) for c in form.cutboxes)
    for name, box in cut_boxes:
        for region in protected:
            if _boxes_overlap(box, region.box):
                violations.append(f"{name} intersects {region.name} ({region.role})")
    return _finding(
        "form.cuts_respect_keepouts",
        not violations,
        "all cuts clear of keepouts" if not violations else "; ".join(violations),
    )


register_probe("form.cuts_respect_keepouts")(
    lambda form, ctx: check_cuts_respect_keepouts(form)
)
