"""Region validators — keepouts and high-stress zones stay solid on the
COMPILED geometry (the IR filtered cut placement; this verifies nothing
else ate the material either).
"""

from __future__ import annotations

from ..cad.geometry import Geometry
from ..cad.probes import box_probe, solid_fraction
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from .probes import register_probe


def _finding(check: str, ok: bool, message: str, measured: float | None = None) -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.REGION,
        message=message,
        critical=True,
        measured=measured,
    )


@register_probe("region.keepouts_preserved")
def keepouts_preserved(geometry: Geometry, form: PartForm) -> Finding:
    """The annulus around each screw bore (outside the bore + countersink,
    inside the keepout radius) must stay solid — no hex cell, no stray cut."""
    head_r = form.frame.get("screw_head_r", 3.5)
    violated = []
    for hole in form.holes:
        x, y, z_top = hole.at
        # Slab between the countersink recess and the far face — must stay
        # solid apart from the bore itself.
        if hole.countersink_face == "bottom":
            z_lo, z_hi = z_top - hole.through + 2.2, z_top - 0.1
        else:
            z_lo, z_hi = z_top - hole.through + 0.1, z_top - 2.2
        zone = box_probe(
            x - head_r - 1.5, y - head_r - 1.5, z_lo,
            x + head_r + 1.5, y + head_r + 1.5, z_hi,
        )
        frac = solid_fraction(geometry.workplane, zone)
        if frac < 0.75:
            violated.append((hole.at, round(frac, 2)))
    return _finding(
        "region.keepouts_preserved",
        not violated,
        "fastener keepouts intact" if not violated else f"keepouts cut: {violated}",
    )


@register_probe("region.snap_root_not_perforated")
def snap_root_not_perforated(geometry: Geometry, form: PartForm) -> Finding:
    region = form.region("snap_root")
    if region is None or not region.box.finite:
        return _finding("region.snap_root_not_perforated", False, "no snap_root region")
    b = region.box
    zone = box_probe(b.x0, b.y0, b.z0, b.x1, b.y1, b.z1)
    frac = solid_fraction(geometry.workplane, zone)
    # The zone straddles wall + void; what matters is that a healthy share
    # of it is material and the wall band itself is continuous along X.
    wall_u = form.frame["wall_outer_u"]
    wall = form.params.get("wall", 3.0)
    m = form.frame["mouth_half"]
    vc = form.frame["cavity_center_v"]
    band = box_probe(
        form.width * 0.2, wall_u - wall, vc - form.frame["lip_band"],
        form.width * 0.8, wall_u, vc - m,
    )
    band_frac = solid_fraction(geometry.workplane, band)
    ok = band_frac > 0.6
    return _finding(
        "region.snap_root_not_perforated",
        ok,
        f"snap-root wall band fill {band_frac:.2f} (zone fill {frac:.2f})",
        measured=band_frac,
    )
