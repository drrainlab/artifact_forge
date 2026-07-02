"""Phone-stand side profile — base slab, tilted back rest, device slot with
a front lip. All trigonometry lives here and in the frame: the horizontal
slot width is device_thickness / sin(tilt) + fit clearances, so the check
measuring the built profile against the declared device is exact.

Section coords: u = Y (0 at the front lip face, +u toward the back),
v = Z up; the stand sits on v = 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .molded import round_profile_corners
from .section import LineSeg, ProfileLoop, Pt, SectionProfile, Seg
from .style import SurfaceStyle


@dataclass(frozen=True)
class StandParams:
    device_thickness: float
    tilt_deg: float
    fit_clearance: float
    lip_t: float
    lip_h: float
    base_t: float
    base_depth: float
    rest_len: float
    rest_t: float

    @property
    def tilt_rad(self) -> float:
        return math.radians(self.tilt_deg)


def stand_frame(p: StandParams) -> dict[str, float]:
    t = p.tilt_rad
    sin_t, cos_t = math.sin(t), math.cos(t)
    slot_w = p.device_thickness / sin_t + 2.0 * p.fit_clearance
    rest_t_h = p.rest_t / sin_t
    u_rest = p.lip_t + slot_w
    rest_foot_end = u_rest + rest_t_h
    if rest_foot_end >= p.base_depth - 5.0:
        raise ValueError(
            f"rest foot at {rest_foot_end:.1f} leaves no base behind it "
            f"(base_depth {p.base_depth:g})"
        )
    top_f = Pt(u_rest + p.rest_len * cos_t, p.base_t + p.rest_len * sin_t)
    return {
        "slot_w": slot_w,
        "u_rest": u_rest,
        "rest_foot_end": rest_foot_end,
        "rest_top_u": top_f.u,
        "rest_top_v": top_f.v,
        "lip_t": p.lip_t,
        "lip_h": p.lip_h,
        "base_t": p.base_t,
        "base_depth": p.base_depth,
        "tilt_sin": sin_t,
        "tilt_cos": cos_t,
        "device_dir_u": cos_t,
        "device_dir_v": sin_t,
        "report_slot_w": slot_w,
        "report_base_depth": p.base_depth,
    }


def build_stand_profile(
    p: StandParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    f = stand_frame(p)
    t_h = p.rest_t / f["tilt_sin"]
    top_f = Pt(f["rest_top_u"], f["rest_top_v"])
    top_b = Pt(top_f.u + t_h, top_f.v)
    u_rest = f["u_rest"]
    bd, bt = p.base_depth, p.base_t
    lip_top = bt + p.lip_h

    def tags(*names: str) -> frozenset[str]:
        return frozenset(names)

    segments: list[Seg] = [
        # the stand sits flat — bottom corners stay sharp
        LineSeg(Pt(0, 0), Pt(bd, 0), tags("base_bottom", "intentional_corner")),
        LineSeg(Pt(bd, 0), Pt(bd, bt), tags("base_back", "external")),
        LineSeg(Pt(bd, bt), Pt(u_rest + t_h, bt), tags("base_top", "external")),
        # tilted back face of the rest
        LineSeg(Pt(u_rest + t_h, bt), top_b, tags("rest_back", "root")),
        LineSeg(top_b, top_f, tags("rest_top", "lip_tip")),
        # device support face down into the slot
        LineSeg(top_f, Pt(u_rest, bt), tags("device_rest", "contact")),
        # slot floor to the lip
        LineSeg(Pt(u_rest, bt), Pt(p.lip_t, bt),
                tags("slot_floor", "contact", "mouth_corner")),
        # lip inner face + top + front
        LineSeg(Pt(p.lip_t, bt), Pt(p.lip_t, lip_top),
                tags("lip", "lip_inner", "contact")),
        LineSeg(Pt(p.lip_t, lip_top), Pt(0, lip_top), tags("lip", "lip_tip")),
        # front face: its TOP corner must round (phone slides past it); the
        # bottom joint is covered by base_bottom's intentional tag
        LineSeg(Pt(0, lip_top), Pt(0, 0), tags("front", "external")),
    ]

    loop = round_profile_corners(ProfileLoop(segments), style)
    profile = SectionProfile(
        name="phone_stand_side", outer=loop, plane="YZ", width_axis="X"
    )
    return profile, f
