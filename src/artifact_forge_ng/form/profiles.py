"""Analytic section-profile builders.

Per the MVP simplification rule, :func:`build_molded_side_hook_profile` is a
DEDICATED builder with explicit arcs and lines — no general offset engine in
the critical path. The outer wall is the concentric circle ``r_cavity +
wall``; the mouth gap is set exactly by the cavity arc's endpoint angles;
the lips are loop extensions whose lengths are the parameters themselves.
A symmetric C-ring is unrepresentable by accident: equal lip lengths are
clamped apart at resolve, and the mouth is part of the loop topology.

The section lives in ``(u, v)`` = (Y, Z): mouth opens toward +u, flange
underside at ``v = 0``, hook hangs below.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .molded import round_profile_corners
from .section import (
    ArcSeg,
    LineSeg,
    ProfileLoop,
    Pt,
    SectionProfile,
    Seg,
    SideOpenObroundCavity,
)
from .style import SurfaceStyle

#: Minimum protrusion of any welded joint into its target solid — the v1
#: lip-overlap lesson generalized: a union that merely touches is a silently
#: dropped body, so every weld overlaps by construction.
WELD_OVERLAP = 0.6


@dataclass(frozen=True)
class SideHookParams:
    bundle_d: float
    clearance: float
    wall: float
    mouth_gap: float
    upper_lip_len: float
    lower_lip_len: float
    neck_drop: float
    #: Lower lip tip keeps this fraction of the wall thickness (taper).
    lower_lip_taper: float = 0.7

    @property
    def r_cavity(self) -> float:
        return self.bundle_d / 2.0 + self.clearance

    @property
    def r_outer(self) -> float:
        return self.r_cavity + self.wall

    @property
    def lip_t(self) -> float:
        return self.wall


def side_hook_frame(p: SideHookParams) -> dict[str, float]:
    """Single source of truth for every derived position — the builder
    consumes these values and the validators measure against the SAME dict,
    so declared and built geometry cannot drift (v1 frame discipline)."""
    r_i, r_o = p.r_cavity, p.r_outer
    m = p.mouth_gap / 2.0
    if m >= r_i:
        raise ValueError(
            f"mouth_gap {p.mouth_gap:g} does not fit cavity radius {r_i:g}"
        )
    vc = -(p.neck_drop + p.wall + r_i)
    band = m + p.lip_t
    if band >= r_o:
        raise ValueError("lip band exceeds outer radius — wall too thin for lips")
    wall_outer_u = math.sqrt(r_o * r_o - m * m)
    neck_w = max(3.0 * p.wall, r_i * 0.9)
    neck_c = -0.3 * r_i
    n0 = max(neck_c - neck_w / 2.0, -r_o * 0.85)
    n1 = min(neck_c + neck_w / 2.0, r_o * 0.5)
    return {
        "r_cavity": r_i,
        "r_outer": r_o,
        "cavity_center_u": 0.0,
        "cavity_center_v": vc,
        "mouth_gap": p.mouth_gap,
        "mouth_half": m,
        "lip_band": band,
        "wall_outer_u": wall_outer_u,
        "upper_lip_tip_u": wall_outer_u + p.upper_lip_len,
        "lower_lip_tip_u": wall_outer_u + p.lower_lip_len,
        "mouth_v_top": vc + m,
        "mouth_v_bot": vc - m,
        "upper_lip_v_top": vc + band,
        "lower_lip_v_bot": vc - band,
        "hook_top_v": vc + r_o,  # == -neck_drop
        "hook_bot_v": vc - r_o,
        "neck_u0": n0,
        "neck_u1": n1,
        "weld_top_v": WELD_OVERLAP,
    }


def _outer_v(frame: dict[str, float], u: float) -> float:
    """v of the outer circle's UPPER half at ``u``."""
    r_o = frame["r_outer"]
    return frame["cavity_center_v"] + math.sqrt(r_o * r_o - u * u)


def build_side_open_obround_cavity(p: SideHookParams) -> SideOpenObroundCavity:
    return SideOpenObroundCavity(
        center=Pt(0.0, side_hook_frame(p)["cavity_center_v"]),
        bundle_d=p.bundle_d,
        clearance=p.clearance,
        mouth_gap=p.mouth_gap,
        mouth_dir=(1.0, 0.0),
    )


def build_molded_side_hook_profile(
    p: SideHookParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    """The flagship section: one closed loop containing the side-open
    cavity, both lips, the wall and the neck — then the molded rounding
    pass. Returns the profile and its frame."""
    f = side_hook_frame(p)
    r_i, r_o = f["r_cavity"], f["r_outer"]
    center = Pt(f["cavity_center_u"], f["cavity_center_v"])
    m, band = f["mouth_half"], f["lip_band"]
    vc = f["cavity_center_v"]

    a_i = Pt(math.sqrt(r_i * r_i - m * m), vc + m)
    b_i = Pt(a_i.u, vc - m)
    a_o = Pt(math.sqrt(r_o * r_o - band * band), vc + band)
    b_o = Pt(a_o.u, vc - band)
    t_u_o = Pt(f["upper_lip_tip_u"], vc + band)
    t_u_i = Pt(f["upper_lip_tip_u"], vc + m)
    t_l_i = Pt(f["lower_lip_tip_u"], vc - m)
    t_l_o = Pt(
        f["lower_lip_tip_u"], vc - m - p.lip_t * p.lower_lip_taper
    )
    n0, n1 = f["neck_u0"], f["neck_u1"]
    v_top = f["weld_top_v"]
    j0 = Pt(n0, _outer_v(f, n0))
    j1 = Pt(n1, _outer_v(f, n1))
    n_tl, n_tr = Pt(n0, v_top), Pt(n1, v_top)

    def tags(*names: str) -> frozenset[str]:
        return frozenset(names)

    segments: list[Seg] = [
        # down the neck's mouth-side edge onto the hook's outer circle
        LineSeg(n_tr, j1, tags("neck", "root")),
        # outer wall, upper mouth side (short way down to the lip band)
        ArcSeg(j1, a_o, center, ccw=False, tags=tags("hook_outer", "root", "external")),
        # upper lip: top edge out, tip down, inner (mouth-top) edge back
        LineSeg(a_o, t_u_o, tags("upper_lip", "upper_lip_outer", "root")),
        LineSeg(t_u_o, t_u_i, tags("upper_lip", "lip_tip")),
        LineSeg(t_u_i, a_i, tags("upper_lip", "mouth_upper", "mouth_corner")),
        # the cavity: one arc the LONG way over top, back and bottom — its
        # endpoint angles define the mouth gap exactly
        ArcSeg(a_i, b_i, center, ccw=True,
               tags=tags("cavity_inner", "cable_contact", "mouth_corner")),
        # lower lip: inner (mouth-bottom) edge out, tip down, tapered
        # outer edge back to the wall
        LineSeg(b_i, t_l_i, tags("lower_lip", "mouth_lower", "mouth_corner")),
        LineSeg(t_l_i, t_l_o, tags("lower_lip", "lip_tip")),
        LineSeg(t_l_o, b_o, tags("lower_lip", "lower_lip_outer", "root")),
        # outer wall the long way around bottom and back up to the neck
        ArcSeg(b_o, j0, center, ccw=False, tags=tags("hook_outer", "root", "external")),
        LineSeg(j0, n_tl, tags("neck", "root")),
        # neck top: welds into the flange plate — an intentional corner pair
        LineSeg(n_tl, n_tr, tags("neck_top", "weld_joint")),
    ]

    loop = round_profile_corners(ProfileLoop(segments), style)
    profile = SectionProfile(
        name="molded_side_hook",
        outer=loop,
        plane="YZ",
        width_axis="X",
        features={"cavity": build_side_open_obround_cavity(p)},
    )
    return profile, f
