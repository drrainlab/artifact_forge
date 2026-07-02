"""Revolved-cup half-section — a lamp-socket holder: base disc with a
central cable exit, cylindrical wall, rounded rim. The half-section lives
in (u = radial, v = axial Z) and revolves about the Z axis; the cable exit
is profile-native (the loop starts at exit_r), so no bore is needed and the
axis-clearance check is exact.
"""

from __future__ import annotations

from dataclasses import dataclass

from .molded import round_profile_corners
from .section import LineSeg, ProfileLoop, Pt, SectionProfile, Seg
from .style import SurfaceStyle


@dataclass(frozen=True)
class CupParams:
    inner_d: float  # actual socket bore (preset already applied)
    depth: float  # actual cavity depth
    wall: float
    base_t: float
    exit_d: float

    @property
    def inner_r(self) -> float:
        return self.inner_d / 2.0

    @property
    def outer_r(self) -> float:
        return self.inner_r + self.wall

    @property
    def exit_r(self) -> float:
        return self.exit_d / 2.0

    @property
    def height(self) -> float:
        return self.depth + self.base_t


def cup_frame(p: CupParams) -> dict[str, float]:
    if p.exit_r <= 0.5:
        raise ValueError("exit_d must leave a real cable hole (> 1 mm)")
    if p.exit_r >= p.inner_r - 2.0:
        raise ValueError(
            f"exit_d {p.exit_d:g} leaves no base floor inside inner_d {p.inner_d:g}"
        )
    return {
        "axis_clear_r": p.exit_r,
        "inner_r": p.inner_r,
        "outer_r": p.outer_r,
        "exit_r": p.exit_r,
        "height": p.height,
        "base_t": p.base_t,
        # min-web outline: holes live on the base floor between the exit
        # hole and the wall root (circle outline with an inner bore).
        "outline_outer_r": p.inner_r,
        "outline_inner_r": p.exit_r,
        "report_inner_d": p.inner_d,
        "report_depth": p.depth,
        "report_exit_d": p.exit_d,
    }


def build_cup_profile(
    p: CupParams, style: SurfaceStyle
) -> tuple[SectionProfile, dict[str, float]]:
    f = cup_frame(p)

    def tags(*names: str) -> frozenset[str]:
        return frozenset(names)

    segments: list[Seg] = [
        # base underside: exit hole edge out to the outer radius
        LineSeg(Pt(p.exit_r, 0), Pt(p.outer_r, 0), tags("base_bottom", "mount_face")),
        # outer wall up
        LineSeg(Pt(p.outer_r, 0), Pt(p.outer_r, p.height), tags("outer_wall", "external")),
        # rim across
        LineSeg(Pt(p.outer_r, p.height), Pt(p.inner_r, p.height), tags("rim", "external")),
        # inner wall down to the base floor — the socket seats here, so the
        # bottom corner stays sharp (intentional)
        LineSeg(Pt(p.inner_r, p.height), Pt(p.inner_r, p.base_t),
                tags("inner_wall", "socket_contact", "intentional_corner")),
        # base floor in to the exit hole
        LineSeg(Pt(p.inner_r, p.base_t), Pt(p.exit_r, p.base_t),
                tags("base_top", "intentional_corner")),
        # exit hole edge
        LineSeg(Pt(p.exit_r, p.base_t), Pt(p.exit_r, 0),
                tags("exit_edge", "intentional_corner")),
    ]

    loop = round_profile_corners(ProfileLoop(segments), style)
    profile = SectionProfile(
        name="revolved_cup", outer=loop, plane="XZ", width_axis="Y"
    )
    return profile, f
