"""Analytic section builders for the split branch clamp family
(docs/BIOMORPHIC.md, Bio-1).

Each clamp half is a CONSTANT SECTION in the ``(u, v)`` = (Y, Z) plane,
extruded along X (X = the branch axis), printed ``side_profile`` — so the
saddle, the TPU pad lands and the dovetail rail are all exact 2D geometry:
support-free by construction and measurable without CAD.

The compression-gap trick: each half's saddle arc center sits ``gap/2``
BEYOND its own mating plane, so the posed pair forms ONE nominal circle of
``branch_d`` while the mating faces stay ``gap`` apart — the clamp always
squeezes the branch, never bottoms out metal-to-metal.

* lower half: mating plane at ``v = mate_z`` (notch cut into the TOP edge,
  arc center at ``mate_z + gap/2``), two pad lands at ±``land_angle`` from
  the saddle bottom;
* upper half: modeled MATING-FACE-DOWN with the mating plane at ``v = 0``
  (notch in the bottom edge, arc center at ``-gap/2``), one pad land at the
  apex, and a REAL male dovetail ridge on top (in-profile trapezoid,
  ``root = rail_w - 2*rail_h*tan(rail_angle)``, ``top = rail_w``).

Pad lands are chord flats pushed radially OUTWARD by ``pad_recess`` with
short RADIAL side walls (never tangent) — three-point TPU contact by
construction across the assembled pair.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace as dc_replace

from .molded import round_profile_corners
from .section import ArcSeg, LineSeg, ProfileLoop, Pt, SectionProfile, Seg
from .style import MOLDED_UTILITY_PART

#: A pad land / mouth tip must keep at least this much arc (degrees) to its
#: neighbour — below it the saddle chain degenerates.
MIN_ARC_MARGIN_DEG = 2.0

_MATE = frozenset({"mate_face", "intentional_corner"})
_SADDLE = frozenset({"saddle_contact", "cavity_inner", "contact"})
_PAD_WALL = frozenset({"pad_wall", "intentional_corner"})
_PAD_LAND = frozenset({"pad_land", "contact", "intentional_corner"})
_RAIL_FLANK = frozenset({"rail_flank", "intentional_corner"})
_RAIL_TOP = frozenset({"rail_top", "intentional_corner"})
#: Plain external walls: their joints against mate faces / pad walls / rail
#: flanks inherit intentionality from the OTHER segment; external-external
#: corners get the molded fillet (radius = corner_r).
_EXTERNAL = frozenset({"external"})


@dataclass(frozen=True)
class ClampHalfParams:
    """Shared 2D parameters of one clamp half (all mm / degrees)."""

    branch_d: float
    gap: float = 3.0
    flange_t: float = 10.0
    bolt_y: float = 40.0
    edge_m: float = 10.0
    wall: float = 4.0
    corner_r: float = 2.5
    land_angle: float = 50.0
    land_w: float = 14.0
    pad_recess: float = 1.2
    # lower only
    base_t: float = 8.0
    # upper only
    top_t: float = 20.0
    rail_w: float = 20.0
    rail_h: float = 6.0
    rail_angle: float = 10.0

    @property
    def saddle_r(self) -> float:
        return self.branch_d / 2.0


def _common_frame(p: ClampHalfParams) -> dict[str, float]:
    r = p.saddle_r
    if p.branch_d < 10.0:
        raise ValueError(f"branch_d {p.branch_d:g} too small for a split clamp")
    if not 1.0 <= p.gap <= 0.5 * r:
        raise ValueError(
            f"compression gap {p.gap:g} outside the sane range "
            f"1.0..{0.5 * r:g} for a {p.branch_d:g} branch"
        )
    if p.pad_recess < 0.4 or p.pad_recess > 0.35 * r:
        raise ValueError(f"pad_recess {p.pad_recess:g} outside 0.4..{0.35 * r:g}")
    mouth_half = math.sqrt(r * r - (p.gap / 2.0) ** 2)
    body_half = mouth_half + p.wall
    wing_u_out = p.bolt_y + p.edge_m
    if wing_u_out < mouth_half + 1.0:
        raise ValueError(
            f"wing edge at |u|={wing_u_out:g} sits inside the saddle mouth "
            f"(half-gap {mouth_half:.1f}) — increase bolt_y or edge_m"
        )
    return {
        "saddle_r": r,
        "saddle_mouth_half": mouth_half,
        "mouth_gap": 2.0 * mouth_half,
        "body_half": body_half,
        "wing_u_out": wing_u_out,
        "flange_t": p.flange_t,
        "clamp_gap": p.gap,
        "pad_recess": p.pad_recess,
        "land_w": p.land_w,
        # generic cavity vocabulary (topology.cavity_open reuse):
        "cavity_center_u": 0.0,
        "r_cavity": r,
    }


def clamp_lower_frame(p: ClampHalfParams) -> dict[str, float]:
    """Single source of truth for the lower half — builder and validators
    consume the SAME dict (the side-hook frame discipline)."""
    f = _common_frame(p)
    r = p.saddle_r
    if p.base_t < 3.0:
        raise ValueError(f"base_t {p.base_t:g} < 3 — no floor under the saddle")
    mate_z = p.base_t + r - p.gap / 2.0
    if mate_z - p.flange_t < 1.0:
        raise ValueError(
            f"flange_t {p.flange_t:g} leaves no body below the wings "
            f"(mating plane at {mate_z:.1f})"
        )
    f.update(
        mate_z=mate_z,
        saddle_cz=mate_z + p.gap / 2.0,
        saddle_apex_v=p.base_t,  # deepest notch penetration
        cavity_center_v=mate_z + p.gap / 2.0,
        wing_v0=mate_z - p.flange_t,
    )
    return f


def clamp_upper_frame(p: ClampHalfParams) -> dict[str, float]:
    """Single source of truth for the upper half (mating plane at v=0)."""
    f = _common_frame(p)
    r = p.saddle_r
    apex_v = r - p.gap / 2.0
    if p.top_t < 6.0:
        raise ValueError(f"top_t {p.top_t:g} < 6 — no body above the saddle")
    if not 0.0 <= p.rail_angle <= 25.0:
        raise ValueError(f"rail_angle {p.rail_angle:g} outside 0..25 degrees")
    rail_root_w = p.rail_w - 2.0 * p.rail_h * math.tan(math.radians(p.rail_angle))
    if rail_root_w < 4.0:
        raise ValueError(
            f"dovetail root {rail_root_w:.1f} < 4 — reduce rail_h/rail_angle "
            "or widen rail_w"
        )
    if p.rail_w / 2.0 + 1.0 > f["body_half"]:
        raise ValueError(
            f"rail_w {p.rail_w:g} wider than the clamp body "
            f"({2.0 * f['body_half']:.1f})"
        )
    body_top = apex_v + p.top_t
    f.update(
        mate_z=0.0,
        saddle_cz=-p.gap / 2.0,
        saddle_apex_v=apex_v,
        cavity_center_v=-p.gap / 2.0,
        wing_v0=p.flange_t,  # wing band top (mating band v in [0, flange_t])
        body_top_v=body_top,
        rail_root_w=rail_root_w,
        rail_top_w=p.rail_w,
        rail_v0=body_top,
        rail_v1=body_top + p.rail_h,
    )
    return f


def _saddle_chain(
    center: Pt,
    r: float,
    start_deg: float,
    end_deg: float,
    land_centers_deg: list[float],
    land_w: float,
    pad_recess: float,
) -> list[Seg]:
    """The saddle arc from ``start_deg`` DOWN to ``end_deg`` (descending
    angles, cw arcs) with a recessed flat pad land at every angle in
    ``land_centers_deg``: [arc] wall-in, flat, wall-out [arc] ...

    The land flat is the chord at distance ``r + pad_recess`` from the
    center; its side walls are exactly radial. Overlaps raise ValueError —
    honest refusal, not silent mangling.
    """
    if start_deg <= end_deg:
        raise ValueError("saddle chain needs descending angles")
    q = math.hypot(r + pad_recess, land_w / 2.0)
    half = math.degrees(math.atan2(land_w / 2.0, r + pad_recess))

    def rho(deg: float) -> Pt:
        return Pt(math.cos(math.radians(deg)), math.sin(math.radians(deg)))

    def on_arc(deg: float) -> Pt:
        return center + rho(deg).scaled(r)

    def on_flat(deg: float) -> Pt:
        return center + rho(deg).scaled(q)

    events: list[tuple[float, float]] = []  # (enter_deg, exit_deg), descending
    for phi in sorted(land_centers_deg, reverse=True):
        events.append((phi + half, phi - half))
    guard = start_deg - MIN_ARC_MARGIN_DEG
    for enter, exit_ in events:
        if enter > guard:
            raise ValueError(
                f"pad land at {enter - half:.1f} deg overlaps the mouth tip "
                "or its neighbour — reduce land_w/land_angle"
            )
        guard = exit_ - MIN_ARC_MARGIN_DEG
    if events and events[-1][1] - MIN_ARC_MARGIN_DEG < end_deg:
        raise ValueError("pad land overlaps the far mouth tip")

    segs: list[Seg] = []
    cursor = start_deg
    for enter, exit_ in events:
        segs.append(ArcSeg(on_arc(cursor), on_arc(enter), center, ccw=False,
                           tags=_SADDLE))
        segs.append(LineSeg(on_arc(enter), on_flat(enter), tags=_PAD_WALL))
        segs.append(LineSeg(on_flat(enter), on_flat(exit_), tags=_PAD_LAND))
        segs.append(LineSeg(on_flat(exit_), on_arc(exit_), tags=_PAD_WALL))
        cursor = exit_
    segs.append(ArcSeg(on_arc(cursor), on_arc(end_deg), center, ccw=False,
                       tags=_SADDLE))
    return segs


def _molded(segments: list[Seg], p: ClampHalfParams, name: str) -> ProfileLoop:
    style = dc_replace(MOLDED_UTILITY_PART, name=name, external_edge_r=p.corner_r)
    return round_profile_corners(ProfileLoop(segments), style)


def build_clamp_lower_profile(
    p: ClampHalfParams,
) -> tuple[SectionProfile, dict[str, float]]:
    """Lower half: base slab + saddle notch in the top edge + wing flanges
    at the mating plane. Returns (profile, frame)."""
    f = clamp_lower_frame(p)
    r, mate_z = f["saddle_r"], f["mate_z"]
    center = Pt(0.0, f["saddle_cz"])
    bh, u_out = f["body_half"], f["wing_u_out"]
    wing_v0 = f["wing_v0"]

    tip_deg = math.degrees(math.asin((p.gap / 2.0) / r))
    start_deg = -tip_deg  # right mouth tip, just below the u-axis
    end_deg = -180.0 + tip_deg  # left mouth tip
    lands = [-90.0 + p.land_angle, -90.0 - p.land_angle]
    saddle = _saddle_chain(center, r, start_deg, end_deg, lands,
                           p.land_w, p.pad_recess)
    right_tip = saddle[0].a  # lands exactly on v = mate_z by construction
    left_tip = saddle[-1].b

    stepped = u_out > bh + 0.75
    side = bh if stepped else u_out
    segs: list[Seg] = []
    # mate face left -> saddle -> mate face right (top edge, walked -u to +u
    # on the left, then the notch, then +u):
    segs.append(LineSeg(Pt(-u_out, mate_z), left_tip, tags=_MATE))
    segs.extend(s.reversed() for s in reversed(saddle))
    segs.append(LineSeg(right_tip, Pt(u_out, mate_z), tags=_MATE))
    # right wing outer wall down to the wing underside
    if stepped:
        segs.append(LineSeg(Pt(u_out, mate_z), Pt(u_out, wing_v0),
                            tags=_EXTERNAL))
        segs.append(LineSeg(Pt(u_out, wing_v0), Pt(side, wing_v0),
                            tags=_EXTERNAL))
        segs.append(LineSeg(Pt(side, wing_v0), Pt(side, 0.0),
                            tags=_EXTERNAL))
    else:
        segs.append(LineSeg(Pt(u_out, mate_z), Pt(side, 0.0),
                            tags=_EXTERNAL))
    # bottom
    segs.append(LineSeg(Pt(side, 0.0), Pt(-side, 0.0), tags=_EXTERNAL))
    # left side back up to the mate face
    if stepped:
        segs.append(LineSeg(Pt(-side, 0.0), Pt(-side, wing_v0),
                            tags=_EXTERNAL))
        segs.append(LineSeg(Pt(-side, wing_v0), Pt(-u_out, wing_v0),
                            tags=_EXTERNAL))
        segs.append(LineSeg(Pt(-u_out, wing_v0), Pt(-u_out, mate_z),
                            tags=_EXTERNAL))
    else:
        segs.append(LineSeg(Pt(-side, 0.0), Pt(-u_out, mate_z),
                            tags=_EXTERNAL))

    loop = _molded(segs, p, "clamp_lower")
    profile = SectionProfile(
        name="recipe_clamp_lower", outer=loop, plane="YZ", width_axis="X",
    )
    f["land_count"] = 2.0
    _land_frame_keys(f, center, lands, p)
    return profile, f


def build_clamp_upper_profile(
    p: ClampHalfParams,
) -> tuple[SectionProfile, dict[str, float]]:
    """Upper half, modeled mating-face-down: saddle notch in the bottom
    edge, wings at v in [0, flange_t], body rising to apex + top_t, male
    dovetail ridge on top. Returns (profile, frame)."""
    f = clamp_upper_frame(p)
    r = f["saddle_r"]
    center = Pt(0.0, f["saddle_cz"])
    bh, u_out = f["body_half"], f["wing_u_out"]
    band_t, body_top = f["flange_t"], f["body_top_v"]
    rr2, rw2 = f["rail_root_w"] / 2.0, f["rail_top_w"] / 2.0
    rail_v1 = f["rail_v1"]

    tip_deg = math.degrees(math.asin((p.gap / 2.0) / r))
    start_deg = 180.0 - tip_deg  # left mouth tip
    end_deg = tip_deg  # right mouth tip
    saddle = _saddle_chain(center, r, start_deg, end_deg, [90.0],
                           p.land_w, p.pad_recess)
    left_tip = saddle[0].a  # lands exactly on v = 0 by construction
    right_tip = saddle[-1].b

    stepped = u_out > bh + 0.75
    side = bh if stepped else u_out
    segs: list[Seg] = []
    # bottom (mating) edge with the saddle notch, walked -u to +u:
    segs.append(LineSeg(Pt(-u_out, 0.0), left_tip, tags=_MATE))
    segs.extend(saddle)
    segs.append(LineSeg(right_tip, Pt(u_out, 0.0), tags=_MATE))
    # right wing + body + rail
    if stepped:
        segs.append(LineSeg(Pt(u_out, 0.0), Pt(u_out, band_t),
                            tags=_EXTERNAL))
        segs.append(LineSeg(Pt(u_out, band_t), Pt(side, band_t),
                            tags=_EXTERNAL))
        segs.append(LineSeg(Pt(side, band_t), Pt(side, body_top),
                            tags=_EXTERNAL))
    else:
        segs.append(LineSeg(Pt(u_out, 0.0), Pt(side, body_top),
                            tags=_EXTERNAL))
    segs.append(LineSeg(Pt(side, body_top), Pt(rr2, body_top), tags=_EXTERNAL))
    segs.append(LineSeg(Pt(rr2, body_top), Pt(rw2, rail_v1), tags=_RAIL_FLANK))
    segs.append(LineSeg(Pt(rw2, rail_v1), Pt(-rw2, rail_v1), tags=_RAIL_TOP))
    segs.append(LineSeg(Pt(-rw2, rail_v1), Pt(-rr2, body_top), tags=_RAIL_FLANK))
    segs.append(LineSeg(Pt(-rr2, body_top), Pt(-side, body_top), tags=_EXTERNAL))
    if stepped:
        segs.append(LineSeg(Pt(-side, body_top), Pt(-side, band_t),
                            tags=_EXTERNAL))
        segs.append(LineSeg(Pt(-side, band_t), Pt(-u_out, band_t),
                            tags=_EXTERNAL))
        segs.append(LineSeg(Pt(-u_out, band_t), Pt(-u_out, 0.0),
                            tags=_EXTERNAL))
    else:
        segs.append(LineSeg(Pt(-side, body_top), Pt(-u_out, 0.0),
                            tags=_EXTERNAL))

    loop = _molded(segs, p, "clamp_upper")
    profile = SectionProfile(
        name="recipe_clamp_upper", outer=loop, plane="YZ", width_axis="X",
    )
    f["land_count"] = 1.0
    _land_frame_keys(f, center, [90.0], p)
    return profile, f


def _land_frame_keys(
    f: dict[str, float], center: Pt, lands_deg: list[float], p: ClampHalfParams
) -> None:
    """Publish each land's flat midpoint and width — checks match tagged
    segments against these."""
    for i, phi in enumerate(lands_deg):
        mid = center + Pt(
            math.cos(math.radians(phi)), math.sin(math.radians(phi))
        ).scaled(f["saddle_r"] + p.pad_recess)
        f[f"land_{i}_u"] = mid.u
        f[f"land_{i}_v"] = mid.v
        f[f"land_{i}_w"] = p.land_w
