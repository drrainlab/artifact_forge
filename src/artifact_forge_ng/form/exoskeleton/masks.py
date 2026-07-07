"""Semantic keepout masks for the exoskeleton — STRICTER than the global
modifier keepouts.

``EXO_PROTECTED_ROLES`` deliberately MIRRORS ``modifiers.common
.PROTECTED_ROLES`` instead of importing it (layering: form/ never imports
modifiers/) and widens it with the contact/seal/flexure roles — an
exoskeleton growing over a saddle pad or a seal lip would destroy function
even though ordinary lightening fields are allowed near them. A sync test
asserts PROTECTED_ROLES ⊆ EXO_PROTECTED_ROLES so the mirror cannot rot.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Iterable, Sequence

from ...product.archetype import RegionRole
from ..regions import Circle2D, Rect2D, Region2D
from ..section import Pt

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps import cycle away
    from ..part import PartForm
    from .ir import ProfileSurfaceMap

#: Mirror of modifiers.common.PROTECTED_ROLES plus the exoskeleton-only
#: additions. Do NOT import modifiers.common here (layering); the superset
#: relation is guarded by a test.
EXO_PROTECTED_ROLES = frozenset(
    {
        RegionRole.FASTENER_KEEPOUT,
        RegionRole.HIGH_STRESS_REGION,
        RegionRole.INTERFACE_KEEPOUT,
        RegionRole.SOFT_CONTACT_SURFACE,
        RegionRole.SEAL_SURFACE,
        RegionRole.RETAINING_FLEXURE,
        RegionRole.BODY_CONTACT_SURFACE,
        RegionRole.TRANSIENT_WATER_PATH,
        RegionRole.SUBSTRATE_SUPPORT_MESH,
    }
)


def _z_disjoint(z_range: tuple[float, float] | None, z0: float, z1: float) -> bool:
    """Mirror of modifiers.common._z_disjoint: geometry entirely outside
    the panel's z-slab is no keepout."""
    if z_range is None:
        return False
    lo, hi = z_range
    return z1 <= lo + 1e-6 or z0 >= hi - 1e-6


def semantic_keepout_mask(
    form: "PartForm",
    window: Rect2D,
    *,
    margin: float = 0.0,
    z_range: tuple[float, float] | None = None,
    extra: Sequence[Region2D] = (),
) -> tuple[Region2D, ...]:
    """Every EXO-protected region overlapping the window, a circle per
    fastener hole, every earlier cut/bore — mirroring
    ``modifiers.common.derive_keepouts`` over the wider role set — merged
    with ``extra`` (the PlateWindow's own keepouts: builder-declared holes
    and prior modifier cuts come along for free)."""
    keepouts: list[Region2D] = list(extra)
    for region in form.regions:
        if region.role not in EXO_PROTECTED_ROLES:
            continue
        b = region.box
        if not all(map(math.isfinite, (b.x0, b.y0, b.x1, b.y1))):
            continue
        if (
            math.isfinite(b.z0) and math.isfinite(b.z1)
            and _z_disjoint(z_range, b.z0, b.z1)
        ):
            continue
        rect = Rect2D(b.x0, b.y0, b.x1, b.y1)
        if (
            rect.u1 < window.u0 or rect.u0 > window.u1
            or rect.v1 < window.v0 or rect.v0 > window.v1
        ):
            continue
        keepouts.append(
            Region2D(region.name, region.role, rect, clearance=margin)
        )
    head_r = form.frame.get("screw_head_r", 3.5)
    for i, hole in enumerate(form.holes):
        keepouts.append(
            Region2D(
                f"hole_{i}",
                RegionRole.FASTENER_KEEPOUT,
                Circle2D(Pt(hole.at[0], hole.at[1]), head_r + 2.0),
                clearance=margin,
            )
        )
    for cut in form.cutboxes:
        b = cut.box
        if _z_disjoint(z_range, b.z0, b.z1):
            continue
        keepouts.append(
            Region2D(
                f"prior_cut_{cut.name}",
                RegionRole.FASTENER_KEEPOUT,
                Rect2D(b.x0, b.y0, b.x1, b.y1),
                clearance=margin,
            )
        )
    for bore in form.bores:
        if bore.axis != "Z":
            continue
        if _z_disjoint(z_range, bore.span[0], bore.span[1]):
            continue
        keepouts.append(
            Region2D(
                f"prior_bore_{bore.name}",
                RegionRole.FASTENER_KEEPOUT,
                Circle2D(Pt(bore.center[0], bore.center[1]), bore.d / 2.0),
                clearance=margin,
            )
        )
    return tuple(keepouts)


def _u_span(
    surface: "ProfileSurfaceMap", cy: float, tol: float
) -> tuple[float, float] | None:
    """Bounding arc-length interval of every contour knot whose section
    ``u`` (world Y) sits within ``tol`` of ``cy`` — the s-projection of a
    Z-axis fastener column. Per-axis bounding, so the returned interval is a
    conservative SUPERSET of the true footprint. Padded by ``tol`` to cover
    sub-segment crossings between knots."""
    lo = math.inf
    hi = -math.inf
    for s, (u, _v) in zip(surface.s_breaks, surface.points):
        if abs(u - cy) <= tol:
            lo = min(lo, s)
            hi = max(hi, s)
    if lo > hi:
        return None
    return (max(0.0, lo - tol), min(surface.total_s, hi + tol))


def _uv_box_span(
    surface: "ProfileSurfaceMap",
    y0: float, z0: float, y1: float, z1: float,
    tol: float,
) -> tuple[float, float] | None:
    """Bounding arc-length interval of knots whose ``(u, v) == (Y, Z)`` land
    inside the world box ``[y0,y1]x[z0,z1]`` (expanded by ``tol``) — the
    s-projection of a cord/tie slot's mouth on the surface."""
    lo = math.inf
    hi = -math.inf
    for s, (u, v) in zip(surface.s_breaks, surface.points):
        if y0 - tol <= u <= y1 + tol and z0 - tol <= v <= z1 + tol:
            lo = min(lo, s)
            hi = max(hi, s)
    if lo > hi:
        return None
    return (max(0.0, lo - tol), min(surface.total_s, hi + tol))


def profile_surface_keepout_mask(
    form: "PartForm",
    surface: "ProfileSurfaceMap",
    window: Rect2D,
    *,
    margin: float = 0.0,
    extra: Sequence[Region2D] = (),
) -> tuple[Region2D, ...]:
    """The exoskeleton keepout mask on a developable ``profile_surface``, in
    local ``(s, x)``. Every Z-axis fastener column (heatset bore / clearance
    hole) and every cord/tie slot becomes a conservative axis-aligned
    rectangle — a SUPERSET of the real footprint, per KEY LAW 2: no bolt or
    slot can hide from the mask. The axial cable channel runs ALONG X inside
    the body and never breaks the surface, so it contributes no mask (it only
    caps recess depth via the op's ``safe_recess``). ``extra`` carries the
    builder-declared local keepouts (the dovetail rail interval)."""
    keepouts: list[Region2D] = list(extra)
    head_r = form.frame.get("screw_head_r", 3.5)

    def _push(name: str, s_span: tuple[float, float] | None,
              x_lo: float, x_hi: float) -> None:
        if s_span is None:
            return
        s_lo, s_hi = s_span
        # clip x to the surface's extrusion span; skip an empty rect
        x_lo = max(x_lo, 0.0)
        x_hi = min(x_hi, surface.width)
        if s_hi - s_lo < 1e-6 or x_hi - x_lo < 1e-6:
            return
        keepouts.append(
            Region2D(name, RegionRole.FASTENER_KEEPOUT,
                     Rect2D(s_lo, x_lo, s_hi, x_hi), clearance=margin)
        )

    for i, hole in enumerate(form.holes):
        r = head_r + 2.0
        _push(f"hole_{i}", _u_span(surface, hole.at[1], r),
              hole.at[0] - r, hole.at[0] + r)
    for bore in form.bores:
        if bore.axis != "Z":
            continue
        r = bore.d / 2.0 + 2.0
        _push(f"bore_{bore.name}", _u_span(surface, bore.center[1], r),
              bore.center[0] - r, bore.center[0] + r)
    for cut in form.cutboxes:
        b = cut.box
        if not all(map(math.isfinite, (b.x0, b.y0, b.z0, b.x1, b.y1, b.z1))):
            continue
        _push(f"cut_{cut.name}",
              _uv_box_span(surface, b.y0, b.z0, b.y1, b.z1, 2.0),
              b.x0 - 2.0, b.x1 + 2.0)
    return tuple(keepouts)


def point_clear(
    p: tuple[float, float], keepouts: Iterable[Region2D]
) -> bool:
    """The SAME keepout-distance rule form/voronoi._poly_clear_of_keepout
    applies to its edge samples: outside the shape AND beyond its
    clearance band."""
    pt = Pt(p[0], p[1])
    return all(
        k.shape.distance(pt) > k.clearance - 1e-9 and not k.shape.contains(pt)
        for k in keepouts
    )


def poly_clear(
    poly: Sequence[tuple[float, float]], keepouts: Iterable[Region2D]
) -> bool:
    """Edge-sampled polygon clearance — samples at t = 0 and 0.5 of every
    edge, exactly like form/voronoi's cell filter."""
    samples: list[tuple[float, float]] = []
    for p, q in zip(poly, list(poly[1:]) + [poly[0]]):
        for t in (0.0, 0.5):
            samples.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    keeps = list(keepouts)
    return all(point_clear(s, keeps) for s in samples)
