"""Zip-tie anchor section — an omega/bridge profile: two flat base flanges
and a raised bridge forming a tunnel the tie threads through (along the
extrusion axis). The tunnel bottom is the mounting surface itself.

Section coords: u across the anchor (mouth-agnostic), v up; v = 0 is the
adhesive/screw face.
"""

from __future__ import annotations

from dataclasses import dataclass

from .molded import round_profile_corners
from .section import LineSeg, ProfileLoop, Pt, SectionProfile, Seg
from .style import SurfaceStyle


@dataclass(frozen=True)
class OmegaParams:
    tie_w: float
    tie_t: float
    clearance: float
    wall: float
    flange_w: float
    base_t: float

    @property
    def tunnel_w(self) -> float:
        return self.tie_w + 2.0 * self.clearance

    @property
    def tunnel_h(self) -> float:
        # Tie thickness + clearance + head wiggle room.
        return self.tie_t + self.clearance + 0.4


def omega_frame(p: OmegaParams) -> dict[str, float]:
    half_span = p.tunnel_w / 2.0 + p.wall + p.flange_w
    return {
        "tunnel_w": p.tunnel_w,
        "tunnel_h": p.tunnel_h,
        "bridge_top_v": p.tunnel_h + p.wall,
        "half_span": half_span,
        "base_t": p.base_t,
        "report_tunnel_w": p.tunnel_w,
        "report_tunnel_h": p.tunnel_h,
    }


def build_omega_profile(
    p: OmegaParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    f = omega_frame(p)
    tw2 = f["tunnel_w"] / 2.0
    th = f["tunnel_h"]
    bt = f["bridge_top_v"]
    hs = f["half_span"]
    base_t = p.base_t

    def tags(*names: str) -> frozenset[str]:
        return frozenset(names)

    base = tags("base", "intentional_corner")
    segments: list[Seg] = [
        LineSeg(Pt(-hs, 0), Pt(-tw2, 0), base),
        LineSeg(Pt(-tw2, 0), Pt(-tw2, th), tags("tunnel", "tie_contact")),
        LineSeg(Pt(-tw2, th), Pt(tw2, th), tags("tunnel_roof", "tie_contact", "mouth_corner")),
        LineSeg(Pt(tw2, th), Pt(tw2, 0), tags("tunnel", "tie_contact")),
        LineSeg(Pt(tw2, 0), Pt(hs, 0), base),
        LineSeg(Pt(hs, 0), Pt(hs, base_t), tags("flange_tip", "intentional_corner")),
        LineSeg(Pt(hs, base_t), Pt(tw2 + p.wall, base_t), tags("flange_top", "external")),
        LineSeg(Pt(tw2 + p.wall, base_t), Pt(tw2 + p.wall, bt), tags("bridge_side", "root")),
        LineSeg(Pt(tw2 + p.wall, bt), Pt(-tw2 - p.wall, bt), tags("bridge_top", "external")),
        LineSeg(Pt(-tw2 - p.wall, bt), Pt(-tw2 - p.wall, base_t), tags("bridge_side", "root")),
        LineSeg(Pt(-tw2 - p.wall, base_t), Pt(-hs, base_t), tags("flange_top", "external")),
        LineSeg(Pt(-hs, base_t), Pt(-hs, 0), tags("flange_tip", "intentional_corner")),
    ]

    loop = round_profile_corners(ProfileLoop(segments), style)
    profile = SectionProfile(
        name="omega_tunnel", outer=loop, plane="YZ", width_axis="X"
    )
    return profile, f
