"""The growth substrate — where on the panel the rib graph MAY grow, where
it MUST land (anchors), and where the load wants it to go (load seeds).

v1 is planar only: the panel is a horizontal face or a tilted FaceWindow
whose local (a, b) frame the caller already resolved; cylindrical mapping
is refused upstream by the applicator (honest fail, Bio-5 scope).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

from ...product.archetype import RegionRole
from ..regions import Rect2D, Region2D
from .ir import LoadPathIR
from .masks import point_clear

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ...product.archetype import ArchetypeSpec
    from ..part import PartForm


@dataclass(frozen=True)
class SubstrateForm:
    """The sampled panel: everything the graph builder needs, frozen."""

    window: Rect2D
    pitch: float
    seed: int
    #: Jittered-grid sample points in local (a, b), mask-filtered.
    samples: tuple[tuple[float, float], ...]
    #: Rib-root landing points (RIB_ANCHOR regions or the fallbacks).
    anchors: tuple[tuple[float, float], ...]
    #: Load seed points the graph grows toward the anchors from.
    load_seeds: tuple[tuple[float, float], ...]
    #: Resolved DECLARED load paths (empty when the heuristic seeded).
    load_paths: tuple[LoadPathIR, ...] = ()


def _project(
    point: tuple[float, float, float],
    origin: tuple[float, float, float] | None,
    tilt_deg: float,
) -> tuple[float, float]:
    """World point -> local (a, b): the planar inverse of
    FieldFeature.local_to_world's in-plane part."""
    if origin is None:
        return (point[0], point[1])
    t = math.radians(tilt_deg)
    ox, oy, oz = origin
    return (
        point[0] - ox,
        (point[1] - oy) * math.cos(t) + (point[2] - oz) * math.sin(t),
    )


def _clamp(p: tuple[float, float], window: Rect2D) -> tuple[float, float]:
    return (
        min(max(p[0], window.u0), window.u1),
        min(max(p[1], window.v0), window.v1),
    )


def _edge_midpoints(rect: Rect2D) -> list[tuple[float, float]]:
    cu, cv = (rect.u0 + rect.u1) / 2.0, (rect.v0 + rect.v1) / 2.0
    return [(cu, rect.v0), (cu, rect.v1), (rect.u0, cv), (rect.u1, cv)]


def _inside(p: tuple[float, float], window: Rect2D) -> bool:
    return (
        window.u0 - 1e-9 <= p[0] <= window.u1 + 1e-9
        and window.v0 - 1e-9 <= p[1] <= window.v1 + 1e-9
    )


def _dedupe(points: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    return list(dict.fromkeys(points))


#: Default sample jitter as a fraction of the pitch — the applicator maps
#: ``organicity`` onto this (0.15 + 0.4*organicity; 0.35 at the 0.5 default).
DEFAULT_JITTER = 0.35


def jittered_grid_samples(
    window: Rect2D,
    masks: Sequence[Region2D],
    *,
    pitch: float,
    seed: int,
    jitter: float = DEFAULT_JITTER,
) -> tuple[tuple[float, float], ...]:
    """Deterministic jittered grid: pitch-spaced points, each jittered by
    ±jitter*pitch via ``random.Random(seed)``; jitter is drawn for EVERY
    grid point before filtering so the surviving set is stable under mask
    changes. Points outside the window or inside a mask are dropped."""
    rng = random.Random(seed)
    out: list[tuple[float, float]] = []
    v = window.v0 + pitch / 2.0
    while v <= window.v1 - pitch / 2.0 + 1e-9:
        u = window.u0 + pitch / 2.0
        while u <= window.u1 - pitch / 2.0 + 1e-9:
            ju = u + rng.uniform(-jitter, jitter) * pitch
            jv = v + rng.uniform(-jitter, jitter) * pitch
            p = (ju, jv)
            if _inside(p, window) and point_clear(p, masks):
                out.append(p)
            u += pitch
        v += pitch
    return tuple(out)


Project = Callable[[tuple[float, float, float]], tuple[float, float]]


def _resolve_anchors(
    form: "PartForm",
    window: Rect2D,
    masks: Sequence[Region2D],
    project: Project,
) -> tuple[tuple[float, float], ...]:
    """RIB_ANCHOR region centers -> fallback MOUNTING/HIGH_STRESS box edge
    points inside the window -> final fallback window edge midpoints. Each
    tier is mask-filtered; an empty result is the applicator's honest
    failure, not this function's problem."""
    anchors: list[tuple[float, float]] = []
    for region in form.regions:
        if region.role is not RegionRole.RIB_ANCHOR:
            continue
        b = region.box
        if not all(map(math.isfinite, (b.x0, b.y0, b.x1, b.y1))):
            continue
        center = ((b.x0 + b.x1) / 2.0, (b.y0 + b.y1) / 2.0,
                  b.z1 if math.isfinite(b.z1) else 0.0)
        anchors.append(_clamp(project(center), window))
    anchors = [p for p in _dedupe(anchors) if point_clear(p, masks)]
    if anchors:
        return tuple(anchors)
    for region in form.regions:
        if region.role not in (
            RegionRole.MOUNTING_SURFACE, RegionRole.HIGH_STRESS_REGION
        ):
            continue
        b = region.box
        if not all(map(math.isfinite, (b.x0, b.y0, b.x1, b.y1))):
            continue
        z = b.z1 if math.isfinite(b.z1) else 0.0
        lo = project((b.x0, b.y0, z))
        hi = project((b.x1, b.y1, z))
        rect = Rect2D(min(lo[0], hi[0]), min(lo[1], hi[1]),
                      max(lo[0], hi[0]), max(lo[1], hi[1]))
        for p in _edge_midpoints(rect):
            if _inside(p, window):
                anchors.append(p)
    anchors = [p for p in _dedupe(anchors) if point_clear(p, masks)]
    if anchors:
        return tuple(anchors)
    anchors = [
        p for p in _edge_midpoints(window) if point_clear(p, masks)
    ]
    return tuple(_dedupe(anchors))


def _snap_clear(
    p: tuple[float, float],
    samples: Sequence[tuple[float, float]],
    masks: Sequence[Region2D],
) -> tuple[float, float]:
    """A seed point buried in a mask snaps to the nearest mask-clear
    sample; a clear point stays put. No clear sample -> the point stays
    where it is and the load-path checks fail honestly."""
    if point_clear(p, masks):
        return p
    best: tuple[float, float] | None = None
    best_d = math.inf
    for s in samples:
        d = math.hypot(s[0] - p[0], s[1] - p[1])
        if d < best_d:
            best, best_d = s, d
    return best if best is not None else p


def _resolve_load_seeds(
    form: "PartForm",
    archetype: "ArchetypeSpec | None",
    window: Rect2D,
    masks: Sequence[Region2D],
    samples: Sequence[tuple[float, float]],
    project: Project,
) -> tuple[tuple[tuple[float, float], ...], tuple[LoadPathIR, ...]]:
    """(a) Declared archetype load paths: each source region's center
    projected into the window (region boxes resolved from form.regions by
    name). (b) Without declarations: the heuristic — HIGH_STRESS region
    centers plus datum projections that land inside the window."""
    declared: list[LoadPathIR] = []
    if archetype is not None:
        for lp in archetype.load_paths:
            region = form.region(lp.from_)
            if region is None:
                continue  # form.regions_present already reports this lie
            b = region.box
            if not all(map(math.isfinite, (b.x0, b.y0, b.x1, b.y1))):
                continue
            center = ((b.x0 + b.x1) / 2.0, (b.y0 + b.y1) / 2.0,
                      b.z1 if math.isfinite(b.z1) else 0.0)
            p = _clamp(project(center), window)
            p = _snap_clear(p, samples, masks)
            declared.append(
                LoadPathIR(
                    from_region=lp.from_, to_region=lp.to,
                    priority=lp.priority, seed=p,
                )
            )
    if declared:
        return tuple(_dedupe(d.seed for d in declared)), tuple(declared)
    seeds: list[tuple[float, float]] = []
    for region in form.regions:
        if region.role is not RegionRole.HIGH_STRESS_REGION:
            continue
        b = region.box
        if not all(map(math.isfinite, (b.x0, b.y0, b.x1, b.y1))):
            continue
        center = ((b.x0 + b.x1) / 2.0, (b.y0 + b.y1) / 2.0,
                  b.z1 if math.isfinite(b.z1) else 0.0)
        p = project(center)
        if _inside(p, window):
            seeds.append(p)
    for datum in form.datums.values():
        at = datum.get("at")
        if not (isinstance(at, (list, tuple)) and len(at) == 3):
            continue
        p = project((float(at[0]), float(at[1]), float(at[2])))
        if _inside(p, window):
            seeds.append(p)
    seeds = [p for p in _dedupe(seeds) if point_clear(p, masks)]
    return tuple(seeds), ()


def build_substrate(
    form: "PartForm",
    archetype: "ArchetypeSpec | None",
    window: Rect2D,
    masks: Sequence[Region2D],
    *,
    pitch: float,
    seed: int,
    jitter: float = DEFAULT_JITTER,
    origin: tuple[float, float, float] | None = None,
    tilt_deg: float = 0.0,
    to_local: Project | None = None,
) -> SubstrateForm:
    """Sample the panel and resolve anchors + load seeds. Purely
    deterministic in (form, archetype, window, masks, pitch, seed,
    jitter).

    ``to_local`` projects a world point to local ``(a, b)``. It defaults to
    None, which reproduces the planar ``origin``/``tilt_deg`` inverse
    BYTE-IDENTICALLY (KEY LAW 6); a developable ``profile_surface`` passes
    its own ``surface.to_local`` inverse instead."""
    if to_local is None:
        def _proj(pt: tuple[float, float, float]) -> tuple[float, float]:
            return _project(pt, origin, tilt_deg)
        project: Project = _proj
    else:
        project = to_local
    samples = jittered_grid_samples(
        window, masks, pitch=pitch, seed=seed, jitter=jitter
    )
    anchors = _resolve_anchors(form, window, masks, project)
    load_seeds, load_paths = _resolve_load_seeds(
        form, archetype, window, masks, samples, project
    )
    return SubstrateForm(
        window=window,
        pitch=pitch,
        seed=seed,
        samples=samples,
        anchors=anchors,
        load_seeds=load_seeds,
        load_paths=load_paths,
    )
