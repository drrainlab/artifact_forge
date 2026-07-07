"""Analytic section builder for the wearable forearm cuff (wave P2,
docs/ROADMAP.md — параллельная линия P).

The whole artifact is ONE constant section in the ``(u, v)`` = (Y, Z)
plane, extruded along X (X = the forearm axis), printed ``side_profile``:
zero overhangs by construction, and every wearable guarantee — skin
clearance, donning window, pad recesses, payload retention — is exact 2D
geometry measurable before any CAD.

Chain, walked CCW around the outside (cavity arcs are cw, like the clamp
halves):

* **arm saddle** — mouth opens DOWN; the limb is not a branch: the ring
  must spring over flesh, retention belongs to the STRAPS, so the capture
  arc (210..262 deg, default 240) only LIGHTLY clips the limb: the mouth
  chord must land inside the donning window measured against the flesh
  diameter by ``form.arm_mouth_dons_ok`` (clearance widens the mouth — a
  too-generous clearance honestly fails that check, it is not clamped
  away). Three recessed TPU pad lands ride the top arc (reuse of the
  clamp's ``_saddle_chain``).
* **chord mouth + strap tabs** — the ring terminates on a horizontal
  CHORD at the mouth-tip level (a round ring cannot host flat tabs at a
  down-facing radial mouth without self-intersection; the chord loses a
  sliver of material and gains a clean area weld). The tabs continue that
  chord outward — flat plates the ``add_strap_slots`` modifier pierces;
  they carry the closure function.
* **neck + payload snap-C** on top — mouth opens UP, pipe-clip arc
  retention (190..268 deg family), the first client of BUILDERS.md's
  ``cylindrical_cradle`` (mirrored snap_c).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace as dc_replace

from .molded import round_profile_corners
from .profiles_clamp import _saddle_chain
from .section import ArcSeg, LineSeg, ProfileLoop, Pt, SectionProfile, Seg
from .style import MOLDED_UTILITY_PART

_BODY = frozenset({"body_contact"})
_TAB_TOP = frozenset({"strap_land", "external"})
_EXTERNAL = frozenset({"external"})
_P_MOUTH = frozenset({"payload_mouth_face", "intentional_corner"})
_P_CAVITY = frozenset({"payload_contact", "cavity_inner"})


@dataclass(frozen=True)
class CuffParams:
    """2D parameters of the forearm cuff (mm / degrees)."""

    arm_circumference: float
    arm_clearance: float = 6.0
    wall: float = 4.0
    arm_capture_deg: float = 240.0
    land_angle: float = 45.0
    land_w: float = 14.0
    pad_recess: float = 1.5
    comfort_edge_r: float = 2.0
    tab_t: float = 4.0
    tab_len: float = 26.0
    payload_d: float = 25.0
    payload_clearance: float = 0.3
    payload_arc_deg: float = 240.0
    clip_wall: float = 3.0
    neck_drop: float = 4.0

    @property
    def limb_r(self) -> float:
        return self.arm_circumference / (2.0 * math.pi)

    @property
    def arm_r_inner(self) -> float:
        return self.limb_r + self.arm_clearance

    @property
    def arm_r_outer(self) -> float:
        return self.arm_r_inner + self.wall

    @property
    def payload_r_inner(self) -> float:
        return self.payload_d / 2.0 + self.payload_clearance

    @property
    def payload_r_outer(self) -> float:
        return self.payload_r_inner + self.clip_wall


def forearm_cuff_frame(p: CuffParams) -> dict[str, float]:
    """Single source of truth — builder and validators consume the SAME
    dict (the side-hook frame discipline)."""
    r_ai, r_ao = p.arm_r_inner, p.arm_r_outer
    r_pi, r_po = p.payload_r_inner, p.payload_r_outer
    if r_ai < 15.0:
        raise ValueError(f"arm cavity radius {r_ai:.1f} < 15 — not a forearm")
    if not 205.0 <= p.arm_capture_deg <= 262.0:
        raise ValueError(
            f"arm_capture_deg {p.arm_capture_deg:g} outside 205..262 — below, "
            "the C degenerates into a U (no location on the arm); above, the "
            "cuff cannot don over flesh"
        )
    if not 190.0 <= p.payload_arc_deg <= 268.0:
        raise ValueError(
            f"payload_arc_deg {p.payload_arc_deg:g} outside the snap range 190..268"
        )
    if p.wall < 2.0 or p.clip_wall < 2.0:
        raise ValueError("wall/clip_wall below 2 mm — not printable as a cuff")
    if p.payload_d >= 2.0 * p.limb_r:
        raise ValueError(
            f"payload_d {p.payload_d:g} is not smaller than the limb itself"
        )

    h = (360.0 - p.arm_capture_deg) / 2.0  # mouth half-angle from -90 deg
    tip_v = -r_ai * math.cos(math.radians(h))
    tip_u = r_ai * math.sin(math.radians(h))
    mouth_gap = 2.0 * tip_u
    tab_v_bot = tip_v - p.tab_t
    #: The chord-mouth junction: where the mouth chord meets the OUTER circle.
    tab_u_x = math.sqrt(r_ao * r_ao - tip_v * tip_v)
    tab_u_out = tip_u + p.tab_len
    if tab_u_out < tab_u_x + 12.0:
        raise ValueError(
            f"tab_len {p.tab_len:g} leaves under 12 mm of usable tab beyond "
            f"the ring wall at |u|={tab_u_x:.1f} — no room for a strap pair"
        )

    # payload clip (snap_c_frame math: neck from the pipe-clip family)
    p_cv = r_ao + p.neck_drop + r_po
    neck_w = max(3.0 * p.clip_wall, r_pi * 0.9)
    n = min(neck_w / 2.0, r_po * 0.6)
    p_h = (360.0 - p.payload_arc_deg) / 2.0  # payload mouth half-angle (from +90)
    payload_mouth_gap = 2.0 * r_pi * math.sin(math.radians(p_h))
    if n >= r_ao - 1.0:
        raise ValueError("payload neck wider than the arm ring")
    if payload_mouth_gap >= p.payload_d - 0.8:
        raise ValueError(
            f"payload mouth {payload_mouth_gap:.1f} leaves no retention on a "
            f"{p.payload_d:g} payload — increase payload_arc_deg"
        )

    return {
        "arm_r_inner": r_ai,
        "arm_r_outer": r_ao,
        "arm_capture_deg": p.arm_capture_deg,
        "arm_mouth_gap": mouth_gap,
        "arm_mouth_tip_u": tip_u,
        "arm_mouth_tip_v": tip_v,
        "cuff_wall": p.wall,
        "pad_recess": p.pad_recess,
        "land_w": p.land_w,
        "land_count": 3.0,
        "tab_t": p.tab_t,
        "tab_v_top": tip_v,
        "tab_v_bot": tab_v_bot,
        "tab_u_in": tip_u,
        "tab_u_x": tab_u_x,
        "tab_u_out": tab_u_out,
        "neck_half_w": n,
        "payload_cv": p_cv,
        "payload_r_inner": r_pi,
        "payload_r_outer": r_po,
        "payload_arc_deg": p.payload_arc_deg,
        "payload_mouth_gap": payload_mouth_gap,
        "comfort_edge_r": p.comfort_edge_r,
        # generic cavity vocabulary (topology.cavity_open reuse — the ARM void):
        "cavity_center_u": 0.0,
        "cavity_center_v": 0.0,
        "r_cavity": r_ai,
        "mouth_gap": mouth_gap,  # the generic probe sizes itself from this
    }


def _on_circle(center: Pt, r: float, deg: float) -> Pt:
    a = math.radians(deg)
    return Pt(center.u + r * math.cos(a), center.v + r * math.sin(a))


def build_forearm_cuff_profile(
    p: CuffParams,
) -> tuple[SectionProfile, dict[str, float]]:
    """One closed loop: left tab -> arm saddle (over the top) -> right tab
    -> around the outside -> neck -> payload snap-C -> back. Returns
    (profile, frame)."""
    f = forearm_cuff_frame(p)
    arm_c = Pt(0.0, 0.0)
    r_ai, r_ao = f["arm_r_inner"], f["arm_r_outer"]
    r_pi, r_po = f["payload_r_inner"], f["payload_r_outer"]
    p_cv, n = f["payload_cv"], f["neck_half_w"]
    pay_c = Pt(0.0, p_cv)

    h = (360.0 - p.arm_capture_deg) / 2.0
    # Saddle: descending from the left tip over the top (90) to the right tip.
    start_deg, end_deg = 270.0 - h, h - 90.0
    lands = [90.0 - p.land_angle, 90.0, 90.0 + p.land_angle]
    saddle = [
        dc_replace(s, tags=s.tags | _BODY)
        for s in _saddle_chain(arm_c, r_ai, start_deg, end_deg, lands,
                               p.land_w, p.pad_recess)
    ]
    left_tip, right_tip = saddle[0].a, saddle[-1].b

    tip_v, tab_v_bot = f["arm_mouth_tip_v"], f["tab_v_bot"]
    tab_u_out, tab_u_x, tab_u_in = f["tab_u_out"], f["tab_u_x"], f["tab_u_in"]
    # shoulder angles on the two circles
    arm_shoulder = math.degrees(math.acos(n / r_ao))
    pay_shoulder = math.degrees(math.acos(n / r_po))
    p_h = (360.0 - p.payload_arc_deg) / 2.0

    segs: list[Seg] = []
    # left tab inner edge up to the left mouth tip, then the saddle over
    # the top, then down the right tab inner edge (the chord-mouth walk:
    # the tabs' undersides face the strap void, their tops continue the
    # mouth chord outward from the ring wall junction at |u| = tab_u_x)
    segs.append(LineSeg(Pt(-tab_u_in, tab_v_bot), left_tip, tags=_EXTERNAL))
    segs.extend(saddle)
    segs.append(LineSeg(right_tip, Pt(tab_u_in, tab_v_bot), tags=_EXTERNAL))
    # right tab underside out + outer edge up + top back to the ring wall
    segs.append(LineSeg(Pt(tab_u_in, tab_v_bot), Pt(tab_u_out, tab_v_bot),
                        tags=_EXTERNAL))
    segs.append(LineSeg(Pt(tab_u_out, tab_v_bot), Pt(tab_u_out, tip_v),
                        tags=_EXTERNAL))
    segs.append(LineSeg(Pt(tab_u_out, tip_v), Pt(tab_u_x, tip_v),
                        tags=_TAB_TOP))
    # up the right flank of the ring to the neck shoulder
    segs.append(ArcSeg(Pt(tab_u_x, tip_v),
                       _on_circle(arm_c, r_ao, arm_shoulder),
                       arm_c, ccw=True, tags=_EXTERNAL))
    # neck right flank up to the payload circle
    segs.append(LineSeg(_on_circle(arm_c, r_ao, arm_shoulder),
                        _on_circle(pay_c, r_po, -pay_shoulder),
                        tags=_EXTERNAL))
    # payload outer right, up to the right mouth tip (90 - p_h)
    segs.append(ArcSeg(_on_circle(pay_c, r_po, -pay_shoulder),
                       _on_circle(pay_c, r_po, 90.0 - p_h),
                       pay_c, ccw=True, tags=_EXTERNAL))
    # right mouth face in to the cavity
    segs.append(LineSeg(_on_circle(pay_c, r_po, 90.0 - p_h),
                        _on_circle(pay_c, r_pi, 90.0 - p_h), tags=_P_MOUTH))
    # payload cavity: the long way UNDER the center (cw / descending)
    segs.append(ArcSeg(_on_circle(pay_c, r_pi, 90.0 - p_h),
                       _on_circle(pay_c, r_pi, p_h - 270.0),
                       pay_c, ccw=False, tags=_P_CAVITY))
    # left mouth face back out
    segs.append(LineSeg(_on_circle(pay_c, r_pi, 90.0 + p_h),
                        _on_circle(pay_c, r_po, 90.0 + p_h), tags=_P_MOUTH))
    # payload outer left, down to the left neck shoulder
    segs.append(ArcSeg(_on_circle(pay_c, r_po, 90.0 + p_h),
                       _on_circle(pay_c, r_po, 180.0 + pay_shoulder),
                       pay_c, ccw=True, tags=_EXTERNAL))
    # neck left flank down to the ring
    segs.append(LineSeg(_on_circle(pay_c, r_po, 180.0 + pay_shoulder),
                        _on_circle(arm_c, r_ao, 180.0 - arm_shoulder),
                        tags=_EXTERNAL))
    # down the left flank of the ring to the left chord-mouth junction
    segs.append(ArcSeg(_on_circle(arm_c, r_ao, 180.0 - arm_shoulder),
                       Pt(-tab_u_x, tip_v),
                       arm_c, ccw=True, tags=_EXTERNAL))
    # left tab: top outward, outer edge down, underside back to the mouth
    segs.append(LineSeg(Pt(-tab_u_x, tip_v), Pt(-tab_u_out, tip_v),
                        tags=_TAB_TOP))
    segs.append(LineSeg(Pt(-tab_u_out, tip_v), Pt(-tab_u_out, tab_v_bot),
                        tags=_EXTERNAL))
    segs.append(LineSeg(Pt(-tab_u_out, tab_v_bot), Pt(-tab_u_in, tab_v_bot),
                        tags=_EXTERNAL))

    style = dc_replace(
        MOLDED_UTILITY_PART,
        name="forearm_cuff",
        external_edge_r=p.comfort_edge_r,
        contact_r=p.comfort_edge_r,
    )
    loop = round_profile_corners(ProfileLoop(segs), style)
    profile = SectionProfile(
        name="recipe_forearm_cuff", outer=loop, plane="YZ", width_axis="X",
    )
    for i, phi in enumerate(lands):
        mid = _on_circle(arm_c, r_ai + p.pad_recess, phi)
        f[f"land_{i}_u"] = mid.u
        f[f"land_{i}_v"] = mid.v
        f[f"land_{i}_w"] = p.land_w
    return profile, f
