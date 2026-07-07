"""Analytic section builder for the wall tool ring mount family.

The section is the TOP-VIEW silhouette of a wall-mounted tool holder in
``(u, v)`` = (Y, Z): a flange strip against the wall (``v ∈ [0, flange_t]``)
fused with a C-ring saddle around the tool axis at ``(0, standoff)``, mouth
opening toward +v (away from the wall). Extruded along X (the tool axis =
vertical along the wall), the loop IS the load path: flange → fusion neck →
ring — so every retention/clearance check is an exact 2D measurement.

Model-frame convention for the whole family: Z = wall normal (wall face at
z = 0), X = vertical along the wall = tool axis = extrusion axis, Y =
horizontal along the wall.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .molded import round_profile_corners
from .section import ArcSeg, LineSeg, ProfileLoop, Pt, SectionProfile, Seg, SideOpenObroundCavity
from .style import SurfaceStyle

#: Minimum snap interference (tool_d - mouth_gap) — below this the mouth
#: does not measurably retain the tool.
MIN_RETENTION_MM = 0.8
#: Insertion floor: a mouth narrower than this fraction of the effective
#: bore cannot flex wide enough to admit the tool.
MIN_MOUTH_FRACTION = 0.7


@dataclass(frozen=True)
class WallRingParams:
    tool_d: float
    clearance: float
    ring_wall: float
    #: Saddle coverage in degrees; the mouth chord follows from it.
    capture_deg: float
    #: Tool axis distance from the wall face (v of the ring center).
    standoff: float
    flange_w: float
    flange_t: float
    flange_corner_r: float = 6.0

    @property
    def r_saddle(self) -> float:
        return self.tool_d / 2.0 + self.clearance

    @property
    def r_outer(self) -> float:
        return self.r_saddle + self.ring_wall

    @property
    def d_eff(self) -> float:
        return self.tool_d + 2.0 * self.clearance


def wall_ring_frame(p: WallRingParams) -> dict[str, float]:
    """Single source of truth for every derived position — the builder
    consumes these values and the validators measure against the SAME dict
    (the side-hook frame discipline)."""
    if not 195.0 <= p.capture_deg <= 262.0:
        raise ValueError(
            f"capture_deg {p.capture_deg:g} outside the retention range 195..262"
        )
    r_i, r_o = p.r_saddle, p.r_outer
    s, t = p.standoff, p.flange_t
    if s < t + r_i + 1.5:
        raise ValueError(
            f"standoff {s:g} too small — the saddle cavity would cut into the "
            f"flange (need >= {t + r_i + 1.5:g})"
        )
    drop = s - t  # ring center height above the flange front face
    fusion_sq = r_o * r_o - drop * drop
    fusion_half_w = math.sqrt(fusion_sq) if fusion_sq > 0.0 else 0.0
    if fusion_half_w < 2.0 * p.ring_wall:
        raise ValueError(
            f"ring barely reaches the flange (fusion half-width "
            f"{fusion_half_w:.1f} < {2.0 * p.ring_wall:g}) — reduce standoff "
            "or thicken ring_wall"
        )
    half_gap = math.radians((360.0 - p.capture_deg) / 2.0)
    mouth_gap = 2.0 * r_i * math.sin(half_gap)
    if p.tool_d - mouth_gap < MIN_RETENTION_MM:
        raise ValueError(
            f"mouth_gap {mouth_gap:.1f} does not retain the tool "
            f"(needs <= tool_d - {MIN_RETENTION_MM:g} = "
            f"{p.tool_d - MIN_RETENTION_MM:.1f}) — increase capture_deg or "
            "reduce clearance"
        )
    if mouth_gap < MIN_MOUTH_FRACTION * p.d_eff:
        raise ValueError(
            f"mouth_gap {mouth_gap:.1f} too narrow to insert a "
            f"{p.tool_d:g} tool — reduce capture_deg"
        )
    strip_lo = fusion_half_w + 1.5
    strip_hi = p.flange_w / 2.0 - p.flange_corner_r
    if strip_lo > strip_hi:
        raise ValueError(
            f"flange_w {p.flange_w:g} too narrow for the ring fusion "
            f"(needs >= {2.0 * (strip_lo + p.flange_corner_r):.0f})"
        )
    strip_half = min(strip_hi, max(strip_lo, r_o))
    return {
        "saddle_r": r_i,
        "d_eff": p.d_eff,
        "r_outer": r_o,
        "ring_wall": p.ring_wall,
        "saddle_cu": 0.0,
        "saddle_cz": s,
        "capture_deg": p.capture_deg,
        "mouth_gap": mouth_gap,
        "mouth_tip_u": r_i * math.sin(half_gap),
        "mouth_tip_v": s + r_i * math.cos(half_gap),
        "fusion_half_w": fusion_half_w,
        "strip_half_w": strip_half,
        "flange_t": t,
        # physically-named probe sizes: "does the tool body pass" and
        # "is the mouth window open" — consumed by topology.tool_void_open.
        "tool_probe_d": 0.85 * p.d_eff,
        "mouth_probe_d": 0.8 * mouth_gap,
        # generic cavity vocabulary (silhouette coverage, probes):
        "cavity_center_u": 0.0,
        "cavity_center_v": s,
        "r_cavity": r_i,
        # driver-blocking floor-plan footprint for form.screw_access_clear:
        "hook_y0": -r_o,
        "hook_y1": r_o,
    }


def _tags(*names: str) -> frozenset[str]:
    return frozenset(names)


def build_wall_ring_section(
    p: WallRingParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    """Flange strip + fused C-ring saddle as ONE exact closed loop, then the
    molded rounding pass. Returns the profile and its frame."""
    f = wall_ring_frame(p)
    r_i, r_o = f["saddle_r"], f["r_outer"]
    s, t = f["saddle_cz"], f["flange_t"]
    sh, u_f = f["strip_half_w"], f["fusion_half_w"]
    center = Pt(0.0, s)

    def at_angle(radius: float, deg: float) -> Pt:
        return Pt(
            radius * math.cos(math.radians(deg)),
            s + radius * math.sin(math.radians(deg)),
        )

    half_gap_deg = (360.0 - p.capture_deg) / 2.0
    ang_r = 90.0 - half_gap_deg  # right mouth edge
    ang_l = 90.0 + half_gap_deg  # left mouth edge
    b_o, b_i = at_angle(r_o, ang_r), at_angle(r_i, ang_r)
    a_i, a_o = at_angle(r_i, ang_l), at_angle(r_o, ang_l)
    bl, br = Pt(-sh, 0.0), Pt(sh, 0.0)
    tr, tl = Pt(sh, t), Pt(-sh, t)
    f_r, f_l = Pt(u_f, t), Pt(-u_f, t)

    outer_tags = _tags("hook_outer", "root", "external")
    segments: list[Seg] = [
        # the wall-contact face: stays dead flat, corners intentional
        LineSeg(bl, br, _tags("mount_face", "intentional_corner")),
        LineSeg(br, tr, _tags("flange_side", "external", "intentional_corner")),
        # flange front face, right of the fusion — the ring welds in at f_r
        LineSeg(tr, f_r, _tags("flange_front", "external")),
        # outer wall up the right side to the mouth
        ArcSeg(f_r, b_o, center, ccw=True, tags=outer_tags),
        # right mouth face (rounded at both ends by the molded pass)
        LineSeg(b_o, b_i, _tags("mouth_face", "lip_tip", "contact")),
        # the saddle — the LONG way under the tool, toward the wall and back
        ArcSeg(b_i, a_i, center, ccw=False,
               tags=_tags("saddle_contact", "cavity_inner", "contact")),
        LineSeg(a_i, a_o, _tags("mouth_face", "lip_tip", "contact")),
        ArcSeg(a_o, f_l, center, ccw=True, tags=outer_tags),
        LineSeg(f_l, tl, _tags("flange_front", "external")),
        LineSeg(tl, bl, _tags("flange_side", "external", "intentional_corner")),
    ]

    loop = round_profile_corners(ProfileLoop(segments), style)
    profile = SectionProfile(
        name="recipe_wall_ring",
        outer=loop,
        plane="YZ",
        width_axis="X",
        features={
            "cavity": SideOpenObroundCavity(
                center=center,
                bundle_d=p.tool_d,
                clearance=p.clearance,
                mouth_gap=f["mouth_gap"],
                mouth_dir=(0.0, 1.0),
            )
        },
    )
    return profile, f
