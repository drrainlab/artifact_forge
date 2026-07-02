"""The flagship profile across its parameter range, plus the negative
proof that a symmetric annular C-clip profile is rejected by the family
check — the validator is not a rubber stamp."""

import math

import pytest

from artifact_forge_ng.form.molded import INTENTIONAL_TAGS, joint_is_tangent
from artifact_forge_ng.form.profiles import (
    SideHookParams,
    build_molded_side_hook_profile,
    side_hook_frame,
)
from artifact_forge_ng.form.section import (
    ArcSeg,
    LineSeg,
    ProfileLoop,
    Pt,
    SectionProfile,
    SideOpenObroundCavity,
)
from artifact_forge_ng.form import silhouette
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART


def params(bundle_d: float, **overrides) -> SideHookParams:
    upper = overrides.pop("upper_lip_len", 6.0)
    lower = overrides.pop("lower_lip_len", max(15.0, upper * 1.6))
    return SideHookParams(
        bundle_d=bundle_d,
        clearance=0.8,
        wall=3.2,
        mouth_gap=overrides.pop("mouth_gap", min(10.0, bundle_d * 0.55)),
        upper_lip_len=upper,
        lower_lip_len=lower,
        neck_drop=8.0,
        **overrides,
    )


@pytest.mark.parametrize("bundle_d", [8.0, 20.0, 40.0])
class TestAcrossRange:
    def test_mouth_gap_exact(self, bundle_d):
        p = params(bundle_d)
        profile, frame = build_molded_side_hook_profile(p, MOLDED_UTILITY_PART)
        measured = silhouette.measure_mouth_gap(profile.outer)
        assert measured == pytest.approx(p.mouth_gap, abs=1e-6)

    def test_lip_ratio_and_family(self, bundle_d):
        p = params(bundle_d)
        profile, frame = build_molded_side_hook_profile(p, MOLDED_UTILITY_PART)
        report = silhouette.measure(profile, frame)
        assert report.family_ok, report.family_problems
        assert report.lip_ratio is not None and report.lip_ratio > 1.5
        assert report.mouth_direction is not None
        assert report.mouth_direction[0] > 0.9

    def test_lip_lengths_measured(self, bundle_d):
        p = params(bundle_d)
        profile, frame = build_molded_side_hook_profile(p, MOLDED_UTILITY_PART)
        upper = silhouette.measure_lip_length(
            profile.outer, "upper_lip", frame["wall_outer_u"]
        )
        lower = silhouette.measure_lip_length(
            profile.outer, "lower_lip", frame["wall_outer_u"]
        )
        assert upper == pytest.approx(p.upper_lip_len, abs=1e-6)
        assert lower == pytest.approx(p.lower_lip_len, abs=1e-6)

    def test_all_joints_smooth(self, bundle_d):
        p = params(bundle_d)
        profile, _ = build_molded_side_hook_profile(p, MOLDED_UTILITY_PART)
        sharp = [
            (sorted(a.tags), sorted(b.tags))
            for a, b in profile.outer.joints()
            if not joint_is_tangent(a, b) and not ((a.tags | b.tags) & INTENTIONAL_TAGS)
        ]
        assert sharp == []

    def test_positive_area_and_sane_bbox(self, bundle_d):
        p = params(bundle_d)
        profile, frame = build_molded_side_hook_profile(p, MOLDED_UTILITY_PART)
        assert profile.outer.area() > 0
        lo, hi = profile.outer.bbox()
        assert lo.v == pytest.approx(frame["hook_bot_v"], abs=0.5)
        assert hi.u == pytest.approx(frame["lower_lip_tip_u"], abs=0.5)


def test_mouth_gap_too_wide_rejected():
    with pytest.raises(ValueError, match="mouth_gap"):
        side_hook_frame(params(8.0, mouth_gap=30.0))


def symmetric_c_ring_profile() -> tuple[SectionProfile, dict[str, float]]:
    """A hand-built SYMMETRIC annular C-clip — the historical failure mode.
    Equal lips, mouth still sideways; the family check must reject it."""
    r_i, wall, m = 10.0, 3.0, 5.0
    r_o = r_i + wall
    vc = -20.0
    center = Pt(0.0, vc)
    lip = 6.0  # equal upper and lower lips
    band = m + wall
    a_i = Pt(math.sqrt(r_i**2 - m**2), vc + m)
    b_i = Pt(a_i.u, vc - m)
    a_o = Pt(math.sqrt(r_o**2 - band**2), vc + band)
    b_o = Pt(a_o.u, vc - band)
    wall_u = math.sqrt(r_o**2 - m**2)
    t_u_o, t_u_i = Pt(wall_u + lip, vc + band), Pt(wall_u + lip, vc + m)
    t_l_i, t_l_o = Pt(wall_u + lip, vc - m), Pt(wall_u + lip, vc - band)
    segs = [
        LineSeg(a_o, t_u_o, frozenset({"upper_lip"})),
        LineSeg(t_u_o, t_u_i, frozenset({"upper_lip", "lip_tip"})),
        LineSeg(t_u_i, a_i, frozenset({"upper_lip", "mouth_upper"})),
        ArcSeg(a_i, b_i, center, ccw=True, tags=frozenset({"cavity_inner"})),
        LineSeg(b_i, t_l_i, frozenset({"lower_lip", "mouth_lower"})),
        LineSeg(t_l_i, t_l_o, frozenset({"lower_lip", "lip_tip"})),
        LineSeg(t_l_o, b_o, frozenset({"lower_lip"})),
        ArcSeg(b_o, a_o, center, ccw=True, tags=frozenset({"hook_outer"})),
    ]
    profile = SectionProfile(
        name="symmetric_cring",
        outer=ProfileLoop(segs),
        features={
            "cavity": SideOpenObroundCavity(
                center=center, bundle_d=2 * (r_i - 0.8), clearance=0.8, mouth_gap=2 * m
            )
        },
    )
    return profile, {"wall_outer_u": wall_u}


def test_symmetric_c_ring_fails_family_check():
    profile, frame = symmetric_c_ring_profile()
    report = silhouette.measure(profile, frame)
    assert not report.family_ok
    assert any("lip ratio" in p for p in report.family_problems)


def test_no_lips_fails_family_check():
    """A plain annulus with a slot but no lip tags at all."""
    profile, frame = symmetric_c_ring_profile()
    stripped = ProfileLoop(
        [
            type(s)(s.a, s.b, s.center, s.ccw, frozenset())
            if isinstance(s, ArcSeg)
            else LineSeg(s.a, s.b, frozenset())
            for s in profile.outer.segments
        ]
    )
    bare = SectionProfile(name="bare", outer=stripped, features=profile.features)
    report = silhouette.measure(bare, frame)
    assert not report.family_ok
