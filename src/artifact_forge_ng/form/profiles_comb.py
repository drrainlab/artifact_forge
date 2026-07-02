"""Cable-comb section — a bar whose top edge carries N open slots: each a
circular resting cavity reached through a throat narrower than the cable
(snap retention). Ported construction from v1 ``_add_cable_comb``; the
throat width is set EXACTLY by the cavity arc's endpoint angles, the same
trick as the flagship mouth.

Section coords: u along the bar, v up; cables run along the extrusion
width. The bar sits on v = 0 (adhesive mount).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .molded import round_profile_corners
from .section import ArcSeg, LineSeg, ProfileLoop, Pt, SectionProfile, Seg
from .style import SurfaceStyle


@dataclass(frozen=True)
class CombParams:
    cable_d: float
    slot_count: int
    clearance: float
    wall: float
    throat_w: float
    pitch: float
    base_h: float
    end_margin: float

    @property
    def cavity_r(self) -> float:
        return self.cable_d / 2.0 + self.clearance

    @property
    def lid_t(self) -> float:
        """Material retained above the cavity top — the retention overhang."""
        return 0.6 * self.wall


def comb_frame(p: CombParams) -> dict[str, float]:
    r = p.cavity_r
    if p.throat_w >= 2.0 * r - 1e-6:
        raise ValueError(
            f"throat_w {p.throat_w:g} must be narrower than the cavity {2 * r:g}"
        )
    cavity_cv = p.base_h + r
    total_h = cavity_cv + r + p.lid_t
    first_cx = p.end_margin + p.wall + r
    bar_l = 2.0 * (p.end_margin + p.wall + r) + p.pitch * (p.slot_count - 1)
    frame: dict[str, float] = {
        "cavity_r": r,
        "cavity_cv": cavity_cv,
        "total_h": total_h,
        "bar_l": bar_l,
        "base_h": p.base_h,
        "throat_w": p.throat_w,
        "slot_count": float(p.slot_count),
        "report_throat_w": p.throat_w,
        "report_bar_l": bar_l,
        "throat_top_v": total_h,
    }
    for i in range(p.slot_count):
        frame[f"slot_cx_{i}"] = first_cx + i * p.pitch
    return frame


def build_cable_comb_profile(
    p: CombParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    f = comb_frame(p)
    r, cv, top, bar_l = f["cavity_r"], f["cavity_cv"], f["total_h"], f["bar_l"]
    half_t = p.throat_w / 2.0
    v_int = cv + math.sqrt(r * r - half_t * half_t)  # throat meets the circle

    def tags(*names: str) -> frozenset[str]:
        return frozenset(names)

    segments: list[Seg] = [
        # The base edge sits flat on the desk — its corners stay sharp.
        LineSeg(Pt(0, 0), Pt(bar_l, 0), tags("base", "intentional_corner")),
        LineSeg(Pt(bar_l, 0), Pt(bar_l, top), tags("external")),
    ]
    # Top edge walked right-to-left; each slot dives down its throat, sweeps
    # the cavity the long way around, and climbs back out.
    cursor = Pt(bar_l, top)
    for i in reversed(range(p.slot_count)):
        cx = f[f"slot_cx_{i}"]
        entry_r = Pt(cx + half_t, top)
        entry_l = Pt(cx - half_t, top)
        p_r = Pt(cx + half_t, v_int)
        p_l = Pt(cx - half_t, v_int)
        slot = f"slot_{i}"
        segments.extend(
            [
                LineSeg(cursor, entry_r, tags("bar_top", "external")),
                LineSeg(entry_r, p_r, tags("throat", "slot_entry", "mouth_corner", slot)),
                ArcSeg(
                    p_r, p_l, Pt(cx, cv), ccw=False,
                    tags=tags("cavity_inner", "cable_contact", "mouth_corner", slot),
                ),
                LineSeg(p_l, entry_l, tags("throat", "slot_entry", "mouth_corner", slot)),
            ]
        )
        cursor = entry_l
    segments.extend(
        [
            LineSeg(cursor, Pt(0, top), tags("bar_top", "external")),
            LineSeg(Pt(0, top), Pt(0, 0), tags("external")),
        ]
    )

    loop = round_profile_corners(ProfileLoop(segments), style)
    profile = SectionProfile(
        name="cable_comb_bar", outer=loop, plane="XZ", width_axis="Y"
    )
    return profile, f
