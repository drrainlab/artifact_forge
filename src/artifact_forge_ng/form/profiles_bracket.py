"""Lamp-bracket arm side profile — a cantilever beam welded under the
mounting plate, with an optional root gusset. The wiring channel is NOT in
the profile: it is two intersecting BoreFeatures (vertical entry near the
root, horizontal run to the tip) the builder declares and the
channel_continuous probe verifies along the full L-path.

Section coords: u = Y along the arm (+Y = away from the plate center),
v = Z; plate underside v = 0; the arm hangs below, tip at u = arm_len.
"""

from __future__ import annotations

from dataclasses import dataclass

from .molded import round_profile_corners
from .profiles import WELD_OVERLAP
from .section import LineSeg, ProfileLoop, Pt, SectionProfile, Seg
from .style import SurfaceStyle


@dataclass(frozen=True)
class BracketArmParams:
    arm_len: float
    arm_h: float
    plate_w: float
    gusset: bool
    gusset_len: float
    gusset_drop: float

    @property
    def root_u(self) -> float:
        return -self.plate_w / 2.0 + 4.0

    @property
    def weld_pad_end(self) -> float:
        return self.plate_w / 2.0 - 2.0


def bracket_arm_frame(p: BracketArmParams) -> dict[str, float]:
    top_v = WELD_OVERLAP
    bot_v = top_v - p.arm_h
    drop = p.gusset_drop if p.gusset else 0.0
    return {
        "root_u": p.root_u,
        "tip_u": p.arm_len,
        "top_v": top_v,
        "bot_v": bot_v,
        "gusset_drop": drop,
        "gusset_len": p.gusset_len if p.gusset else 0.0,
        "weld_pad_end": p.weld_pad_end,
        "arm_center_v": top_v - p.arm_h / 2.0,
        "hook_top_v": top_v,  # generic flange_above_cradle probe contract
        "report_arm_len": p.arm_len,
        "report_arm_h": p.arm_h,
    }


def build_bracket_arm_profile(
    p: BracketArmParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    f = bracket_arm_frame(p)
    top, bot = f["top_v"], f["bot_v"]
    root_u, tip_u = f["root_u"], f["tip_u"]
    pad_end = f["weld_pad_end"]

    def tags(*names: str) -> frozenset[str]:
        return frozenset(names)

    segments: list[Seg] = [
        # weld pad under the plate (pokes WELD_OVERLAP into it), then a tiny
        # step down to v=0 for the exposed run of the arm top
        LineSeg(Pt(root_u, top), Pt(pad_end, top), tags("weld_pad", "weld_joint")),
        LineSeg(Pt(pad_end, top), Pt(pad_end, 0.0), tags("weld_step", "weld_joint")),
        LineSeg(Pt(pad_end, 0.0), Pt(tip_u, 0.0), tags("arm_top", "external")),
        # tip face down
        LineSeg(Pt(tip_u, 0.0), Pt(tip_u, bot), tags("arm_tip_face", "external")),
    ]
    if p.gusset and f["gusset_drop"] > 0.1:
        segments.extend(
            [
                LineSeg(Pt(tip_u, bot), Pt(f["gusset_len"], bot),
                        tags("arm_bottom", "external")),
                LineSeg(Pt(f["gusset_len"], bot), Pt(root_u, bot - f["gusset_drop"]),
                        tags("gusset", "root")),
                LineSeg(Pt(root_u, bot - f["gusset_drop"]), Pt(root_u, top),
                        tags("arm_root", "root")),
            ]
        )
    else:
        segments.extend(
            [
                LineSeg(Pt(tip_u, bot), Pt(root_u, bot), tags("arm_bottom", "external")),
                LineSeg(Pt(root_u, bot), Pt(root_u, top), tags("arm_root", "root")),
            ]
        )

    loop = round_profile_corners(ProfileLoop(segments), style)
    profile = SectionProfile(
        name="bracket_arm_side", outer=loop, plane="YZ", width_axis="X"
    )
    return profile, f
