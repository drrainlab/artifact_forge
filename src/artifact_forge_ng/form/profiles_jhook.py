"""J-hook section — a plate-hung open hook: spine down from the plate,
half-round bay floor, tall tip lip, bay open toward the plate. Almost every
joint is tangent BY CONSTRUCTION (vertical lines meet the concentric arcs
exactly where their tangents are vertical), so the molded pass only rounds
the lip tip.

Section coords (flagship convention): u = Y, v = Z; plate underside v = 0,
hook below. Shared by wall_hook_v1 and headphone_hook_v1.
"""

from __future__ import annotations

from dataclasses import dataclass

from .molded import round_profile_corners
from .profiles import WELD_OVERLAP
from .section import ArcSeg, LineSeg, ProfileLoop, Pt, SectionProfile, Seg
from .style import SurfaceStyle


@dataclass(frozen=True)
class JHookParams:
    bay_w: float
    bay_depth: float
    wall: float
    lip_h: float

    @property
    def r_in(self) -> float:
        return self.bay_w / 2.0

    @property
    def r_out(self) -> float:
        return self.r_in + self.wall


def j_hook_frame(p: JHookParams) -> dict[str, float]:
    if p.bay_depth < p.r_in + p.lip_h + 4.0:
        raise ValueError(
            f"bay_depth {p.bay_depth:g} too shallow for lip {p.lip_h:g} — entry closes"
        )
    c_u = p.wall + p.r_in
    c_v = -p.bay_depth + p.r_in
    lip_tip_v = c_v + p.lip_h
    return {
        "bay_w": p.bay_w,
        "bay_depth": p.bay_depth,
        "bay_center_u": c_u,
        "bay_center_v": c_v,
        "r_in": p.r_in,
        "r_out": p.r_out,
        "lip_tip_v": lip_tip_v,
        "lip_outer_u": p.bay_w + 2.0 * p.wall,
        "lip_inner_u": p.bay_w + p.wall,
        "entry_gap": -lip_tip_v,
        "hook_top_v": WELD_OVERLAP,
        "report_bay_w": p.bay_w,
        "report_bay_depth": p.bay_depth,
        "report_lip_h": p.lip_h,
        "report_entry_gap": -lip_tip_v,
    }


def build_j_hook_profile(
    p: JHookParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    f = j_hook_frame(p)
    c = Pt(f["bay_center_u"], f["bay_center_v"])
    top = f["hook_top_v"]
    tip_v = f["lip_tip_v"]
    lo_u, li_u = f["lip_outer_u"], f["lip_inner_u"]

    def tags(*names: str) -> frozenset[str]:
        return frozenset(names)

    segments: list[Seg] = [
        # spine outer: straight down the u=0 face into the outer arc's
        # vertical-tangent point (angle 180 deg) — tangent by construction
        LineSeg(Pt(0, top), Pt(0, c.v), tags("spine", "external")),
        # outer bay floor, 180 degrees under the bay
        ArcSeg(Pt(0, c.v), Pt(lo_u, c.v), c, ccw=True,
               tags=tags("hook_outer", "external")),
        # lip outer face up to the tip
        LineSeg(Pt(lo_u, c.v), Pt(lo_u, tip_v), tags("lip", "lip_outer")),
        # tip edge (rounded by the molded pass)
        LineSeg(Pt(lo_u, tip_v), Pt(li_u, tip_v), tags("lip", "lip_tip")),
        # lip inner face back down into the bay
        LineSeg(Pt(li_u, tip_v), Pt(li_u, c.v), tags("lip", "bay_contact", "contact")),
        # inner bay floor back to the spine
        ArcSeg(Pt(li_u, c.v), Pt(p.wall, c.v), c, ccw=False,
               tags=tags("bay_floor", "bay_contact", "contact")),
        # spine inner up to the weld
        LineSeg(Pt(p.wall, c.v), Pt(p.wall, top), tags("spine", "root")),
        # weld edge into the plate
        LineSeg(Pt(p.wall, top), Pt(0, top), tags("neck_top", "weld_joint")),
    ]

    loop = round_profile_corners(ProfileLoop(segments), style)
    profile = SectionProfile(name="j_hook", outer=loop, plane="YZ", width_axis="X")
    return profile, f
