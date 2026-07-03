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
    #: "round" (classic circular cavity) or "teardrop" — the bottom of the
    #: cavity becomes two 45-degree tangent chamfers meeting at a peak, so
    #: the cavity roof is SELF-SUPPORTING when the clip prints flange-down.
    cavity_roof: str = "round"

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
    teardrop = p.cavity_roof == "teardrop"
    # Teardrop: 45-degree tangent chamfers meet at a peak sqrt(2)*r below
    # the center — the hook grows deeper by ~0.41*r_o, the honest price of
    # a self-supporting cavity roof.
    hook_bot_v = vc - (r_o * math.sqrt(2.0) if teardrop else r_o)
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
        "hook_bot_v": hook_bot_v,
        "neck_u0": n0,
        "neck_u1": n1,
        "weld_top_v": WELD_OVERLAP,
        "cavity_teardrop": 1.0 if teardrop else 0.0,
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


def _side_hook_body(p: SideHookParams, f: dict[str, float]) -> tuple[list[Seg], Pt, Pt]:
    """The hook itself — from the neck's mouth-side junction ``j1`` around
    both lips, the cavity and the outer bottom, back to the rear junction
    ``j0``. Shared VERBATIM by the v2 (welded flange plate) and v3
    (in-profile tongue) builders, so the two variants hold a cable with the
    exact same geometry. Returns (segments, j0, j1)."""
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
    j0 = Pt(n0, _outer_v(f, n0))
    j1 = Pt(n1, _outer_v(f, n1))

    def tags(*names: str) -> frozenset[str]:
        return frozenset(names)

    def at_angle(radius: float, deg: float) -> Pt:
        return Pt(
            center.u + radius * math.cos(math.radians(deg)),
            center.v + radius * math.sin(math.radians(deg)),
        )

    inner_tags = tags("cavity_inner", "cable_contact", "mouth_corner")
    if p.cavity_roof == "teardrop":
        # Self-supporting cavity: the bottom quarter of the circle becomes
        # two 45-degree TANGENT chamfers meeting at a peak sqrt(2)*r below
        # the center (tangency at the 225/315-degree points is exact, so
        # only the peak needs the molded pass). The outer wall follows the
        # same teardrop at r_o — the wall stays constant by construction.
        peak_i = Pt(center.u, vc - r_i * math.sqrt(2.0))
        cavity_chain: list[Seg] = [
            ArcSeg(a_i, at_angle(r_i, 225.0), center, ccw=True, tags=inner_tags),
            LineSeg(at_angle(r_i, 225.0), peak_i, inner_tags),
            LineSeg(peak_i, at_angle(r_i, 315.0), inner_tags),
            ArcSeg(at_angle(r_i, 315.0), b_i, center, ccw=True, tags=inner_tags),
        ]
        peak_o = Pt(center.u, vc - r_o * math.sqrt(2.0))
        outer_tags = tags("hook_outer", "root", "external")
        outer_bottom: list[Seg] = [
            ArcSeg(b_o, at_angle(r_o, 315.0), center, ccw=False, tags=outer_tags),
            LineSeg(at_angle(r_o, 315.0), peak_o, outer_tags),
            LineSeg(peak_o, at_angle(r_o, 225.0), outer_tags),
            ArcSeg(at_angle(r_o, 225.0), j0, center, ccw=False, tags=outer_tags),
        ]
    else:
        cavity_chain = [ArcSeg(a_i, b_i, center, ccw=True, tags=inner_tags)]
        outer_bottom = [
            ArcSeg(b_o, j0, center, ccw=False,
                   tags=tags("hook_outer", "root", "external")),
        ]

    segments: list[Seg] = [
        # outer wall, upper mouth side (short way down to the lip band)
        ArcSeg(j1, a_o, center, ccw=False, tags=tags("hook_outer", "root", "external")),
        # upper lip: top edge out, tip down, inner (mouth-top) edge back
        LineSeg(a_o, t_u_o, tags("upper_lip", "upper_lip_outer", "root")),
        LineSeg(t_u_o, t_u_i, tags("upper_lip", "lip_tip")),
        LineSeg(t_u_i, a_i, tags("upper_lip", "mouth_upper", "mouth_corner")),
        # the cavity, the LONG way over top, back and bottom — endpoint
        # angles define the mouth gap exactly; teardrop replaces the bottom
        *cavity_chain,
        # lower lip: inner (mouth-bottom) edge out, tip down, tapered
        # outer edge back to the wall
        LineSeg(b_i, t_l_i, tags("lower_lip", "mouth_lower", "mouth_corner")),
        LineSeg(t_l_i, t_l_o, tags("lower_lip", "lip_tip")),
        LineSeg(t_l_o, b_o, tags("lower_lip", "lower_lip_outer", "root")),
        # outer wall the long way around bottom, ending at the rear junction
        *outer_bottom,
    ]
    return segments, j0, j1


def _tags(*names: str) -> frozenset[str]:
    return frozenset(names)


def build_molded_side_hook_profile(
    p: SideHookParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    """The flagship (v2) section: the shared hook body closed by a short
    neck whose flat top welds into a separate flange PLATE — then the
    molded rounding pass. Returns the profile and its frame."""
    f = side_hook_frame(p)
    body, j0, j1 = _side_hook_body(p, f)
    n0, n1 = f["neck_u0"], f["neck_u1"]
    v_top = f["weld_top_v"]
    n_tl, n_tr = Pt(n0, v_top), Pt(n1, v_top)

    segments: list[Seg] = [
        # down the neck's mouth-side edge onto the hook's outer circle
        LineSeg(n_tr, j1, _tags("neck", "root")),
        *body,
        LineSeg(j0, n_tl, _tags("neck", "root")),
        # neck top: welds into the flange plate — an intentional corner pair
        LineSeg(n_tl, n_tr, _tags("neck_top", "weld_joint")),
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


@dataclass(frozen=True)
class SnapClipParams:
    """Symmetric snap C-clip for pipes/rods/broom handles — the retention
    is the ARC (coverage past 180 degrees), not asymmetric lips. NOT a
    substitute for the under-desk side-hook: different physics, different
    family checks."""

    pipe_d: float
    clearance: float
    wall: float
    #: Cavity coverage in degrees; the mouth chord follows from it.
    arc_deg: float
    neck_drop: float

    @property
    def r_cavity(self) -> float:
        return self.pipe_d / 2.0 + self.clearance

    @property
    def r_outer(self) -> float:
        return self.r_cavity + self.wall


def snap_c_frame(p: SnapClipParams) -> dict[str, float]:
    if not 190.0 <= p.arc_deg <= 268.0:
        raise ValueError(f"arc_deg {p.arc_deg:g} outside the snap range 190..268")
    r_i, r_o = p.r_cavity, p.r_outer
    vc = -(p.neck_drop + r_o)
    half_gap = math.radians((360.0 - p.arc_deg) / 2.0)
    mouth_gap = 2.0 * r_i * math.sin(half_gap)
    neck_w = max(3.0 * p.wall, r_i * 0.9)
    n = min(neck_w / 2.0, r_o * 0.6)
    return {
        "r_cavity": r_i,
        "r_outer": r_o,
        "cavity_center_u": 0.0,
        "cavity_center_v": vc,
        "snap_arc_deg": p.arc_deg,
        "mouth_gap": mouth_gap,
        "hook_top_v": vc + r_o,
        "hook_bot_v": vc - r_o,
        "neck_u0": -n,
        "neck_u1": n,
    }


def build_snap_c_tongue_profile(
    p: SnapClipParams, beam_half: float, tongue_t: float, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    """Snap C-clip with the mounting beam IN the profile (both wings carry
    a screw), mouth opening straight down (-v) away from the mount face.
    A constant-section extrusion — prints profile-on-bed, zero overhangs."""
    f = snap_c_frame(p)
    r_i, r_o = f["r_cavity"], f["r_outer"]
    vc = f["cavity_center_v"]
    center = Pt(0.0, vc)
    n0, n1 = f["neck_u0"], f["neck_u1"]
    if beam_half <= r_o + 2.0:
        raise ValueError("beam must extend past the hook on both sides")

    def at_angle(radius: float, deg: float) -> Pt:
        return Pt(
            radius * math.cos(math.radians(deg)),
            vc + radius * math.sin(math.radians(deg)),
        )

    half_gap_deg = (360.0 - p.arc_deg) / 2.0
    ang_r = 270.0 + half_gap_deg  # right mouth edge
    ang_l = 270.0 - half_gap_deg  # left mouth edge
    b_i, b_o = at_angle(r_i, ang_r), at_angle(r_o, ang_r)
    a_i, a_o = at_angle(r_i, ang_l), at_angle(r_o, ang_l)
    j0 = Pt(n0, vc + math.sqrt(r_o * r_o - n0 * n0))
    j1 = Pt(n1, vc + math.sqrt(r_o * r_o - n1 * n1))
    tr, br = Pt(beam_half, tongue_t), Pt(beam_half, 0.0)
    tl, bl = Pt(-beam_half, tongue_t), Pt(-beam_half, 0.0)
    inner_tags = _tags("cavity_inner", "cable_contact")
    outer_tags = _tags("hook_outer", "root", "external")

    segments: list[Seg] = [
        # the mount face: one flat edge across both wings
        LineSeg(tl, tr, _tags("mount_face", "intentional_corner")),
        LineSeg(tr, br, _tags("tongue_back", "external")),
        LineSeg(br, Pt(n1, 0.0), _tags("tongue_bottom", "root", "external")),
        LineSeg(Pt(n1, 0.0), j1, _tags("neck", "root")),
        # outer wall down the right side to the mouth
        ArcSeg(j1, b_o, center, ccw=False, tags=outer_tags),
        # right mouth face (rounded at both ends by the molded pass)
        LineSeg(b_o, b_i, _tags("mouth_face", "contact")),
        # the retention arc — the long way over the top
        ArcSeg(b_i, a_i, center, ccw=True, tags=inner_tags),
        LineSeg(a_i, a_o, _tags("mouth_face", "contact")),
        ArcSeg(a_o, j0, center, ccw=False, tags=outer_tags),
        LineSeg(j0, Pt(n0, 0.0), _tags("neck", "root")),
        LineSeg(Pt(n0, 0.0), bl, _tags("tongue_bottom", "root", "external")),
        LineSeg(bl, tl, _tags("tongue_back", "external")),
    ]

    loop = round_profile_corners(ProfileLoop(segments), style)
    f = dict(f)
    f.update(
        tongue_u0=-beam_half,
        beam_u1=beam_half,
        tongue_t=tongue_t,
        hook_y0=-r_o,
        hook_y1=r_o,
    )
    profile = SectionProfile(
        name="snap_c_tongue",
        outer=loop,
        plane="YZ",
        width_axis="X",
        features={
            "cavity": SideOpenObroundCavity(
                center=center,
                bundle_d=p.pipe_d,
                clearance=p.clearance,
                mouth_gap=f["mouth_gap"],
                mouth_dir=(0.0, -1.0),
            )
        },
    )
    return profile, f


def build_tongue_side_hook_profile(
    p: SideHookParams, tongue_u0: float, tongue_t: float, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    """The v3 SIDEPRINT section: the same hook body, but the mounting
    flange is an in-profile TONGUE running behind the hook (u < 0) — screws
    land along the tongue where a driver clears the hook. Because every
    feature lives in this one section, the part is a true constant-section
    extrusion: printed profile-on-bed (extrusion axis vertical) it has NO
    overhangs by construction — every layer is the same shape."""
    f = side_hook_frame(p)
    if tongue_u0 >= f["neck_u0"] - 1.0:
        raise ValueError(
            f"tongue_u0 {tongue_u0:g} must reach behind the neck "
            f"(< {f['neck_u0'] - 1.0:g})"
        )
    body, j0, j1 = _side_hook_body(p, f)
    n0, n1 = f["neck_u0"], f["neck_u1"]
    beam_tr = Pt(n1, tongue_t)  # mount face meets the mouth-side drop edge
    heel = Pt(n0, 0.0)  # tongue underside meets the neck's rear edge
    back_b, back_t = Pt(tongue_u0, 0.0), Pt(tongue_u0, tongue_t)

    segments: list[Seg] = [
        # one straight edge: beam right side continuing down the neck
        LineSeg(beam_tr, j1, _tags("neck", "root")),
        *body,
        LineSeg(j0, heel, _tags("neck", "root")),
        # tongue underside — the screw heads seat here (countersinks)
        LineSeg(heel, back_b, _tags("tongue_bottom", "root", "external")),
        LineSeg(back_b, back_t, _tags("tongue_back", "external")),
        # the desk-contact face: stays dead flat, corners intentional
        LineSeg(back_t, beam_tr, _tags("mount_face", "intentional_corner")),
    ]

    loop = round_profile_corners(ProfileLoop(segments), style)
    f = dict(f)
    f.update(
        tongue_u0=tongue_u0,
        tongue_t=tongue_t,
        beam_u1=n1,
        # The driver-blocking footprint is the HOOK only, not the tongue —
        # screw access measures against these instead of the profile bbox.
        hook_y0=-f["r_outer"],
        hook_y1=f["lower_lip_tip_u"],
    )
    profile = SectionProfile(
        name="tongue_side_hook",
        outer=loop,
        plane="YZ",
        width_axis="X",
        features={"cavity": build_side_open_obround_cavity(p)},
    )
    return profile, f
