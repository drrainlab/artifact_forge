"""IR-side silhouette measurement — the section profile IS the side view.

Everything here reads tagged segments and the frame dict; measurements are
exact (arc/line parameters), which is what lets the golden test assert
``mouth_gap == 10mm`` with no mesh tolerance fuzz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .part import PartForm
from .section import ArcSeg, LineSeg, ProfileLoop, Pt, SectionProfile, SideOpenObroundCavity


@dataclass(frozen=True)
class SilhouetteReport:
    mouth_gap: float | None
    mouth_direction: tuple[float, float] | None
    upper_lip_len: float | None
    lower_lip_len: float | None
    lip_ratio: float | None
    family_ok: bool
    family_problems: tuple[str, ...]


def _tagged_lines(loop: ProfileLoop, tag: str) -> list[LineSeg]:
    return [s for s in loop.tagged(tag) if isinstance(s, LineSeg)]


def measure_mouth_gap(loop: ProfileLoop) -> float | None:
    uppers = _tagged_lines(loop, "mouth_upper")
    lowers = _tagged_lines(loop, "mouth_lower")
    if not uppers or not lowers:
        return None
    v_up = min(s.point_at(0.5).v for s in uppers)
    v_low = max(s.point_at(0.5).v for s in lowers)
    return v_up - v_low


def measure_lip_length(loop: ProfileLoop, tag: str, wall_outer_u: float) -> float | None:
    segs = loop.tagged(tag)
    if not segs:
        return None
    tip_u = max(max(s.a.u, s.b.u) for s in segs)
    return tip_u - wall_outer_u


def measure_mouth_direction(profile: SectionProfile) -> tuple[float, float] | None:
    cavity = profile.features.get("cavity")
    if not isinstance(cavity, SideOpenObroundCavity):
        return None
    uppers = _tagged_lines(profile.outer, "mouth_upper")
    lowers = _tagged_lines(profile.outer, "mouth_lower")
    if not uppers or not lowers:
        return None
    pts = [s.point_at(0.5) for s in uppers + lowers]
    mid = Pt(sum(p.u for p in pts) / len(pts), sum(p.v for p in pts) / len(pts))
    d = mid - cavity.center
    n = d.norm()
    if n < 1e-9:
        return None
    return (d.u / n, d.v / n)


def cavity_back_closed(loop: ProfileLoop) -> bool:
    """The cavity arc must wrap well past a half-circle — an open back or a
    shallow scoop is not a hook."""
    arcs = [s for s in loop.tagged("cavity_inner") if isinstance(s, ArcSeg)]
    total_sweep = sum(abs(s.sweep) for s in arcs)
    return total_sweep >= math.radians(200)


def measure(profile: SectionProfile, frame: dict[str, float]) -> SilhouetteReport:
    loop = profile.outer
    wall_u = frame.get("wall_outer_u", 0.0)
    gap = measure_mouth_gap(loop)
    upper = measure_lip_length(loop, "upper_lip", wall_u)
    lower = measure_lip_length(loop, "lower_lip", wall_u)
    direction = measure_mouth_direction(profile)
    ratio = (lower / upper) if (upper and upper > 1e-9 and lower is not None) else None

    problems: list[str] = []
    if gap is None:
        problems.append("no mouth found (mouth_upper/mouth_lower tags missing)")
    if direction is None:
        problems.append("mouth direction unmeasurable")
    elif direction[0] < 0.9:
        problems.append(
            f"mouth does not open sideways (+u): direction=({direction[0]:.2f}, {direction[1]:.2f})"
        )
    if ratio is None:
        problems.append("lip lengths unmeasurable")
    elif ratio <= 1.5:
        problems.append(f"lip ratio {ratio:.2f} <= 1.5 — symmetric-ish lips")
    if not cavity_back_closed(loop):
        problems.append("cavity back is not closed (sweep < 200 degrees)")

    return SilhouetteReport(
        mouth_gap=gap,
        mouth_direction=direction,
        upper_lip_len=upper,
        lower_lip_len=lower,
        lip_ratio=ratio,
        family_ok=not problems,
        family_problems=tuple(problems),
    )


def matches_family(profile: SectionProfile, frame: dict[str, float]) -> bool:
    return measure(profile, frame).family_ok


def flange_above_cradle(form: PartForm) -> bool:
    """Every plate must sit fully above the hook body (weld overlap aside)."""
    if not form.plates:
        return False
    _, hi = form.section.outer.bbox()
    hook_top = hi.v
    return all(p.z_bottom >= hook_top - 1.0 for p in form.plates)
