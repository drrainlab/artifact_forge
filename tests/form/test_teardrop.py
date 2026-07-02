"""Teardrop cavity: self-supporting geometry, function bit-for-bit intact."""

import math

import pytest

from artifact_forge_ng.form.molded import INTENTIONAL_TAGS, joint_is_tangent
from artifact_forge_ng.form.profiles import SideHookParams, build_molded_side_hook_profile
from artifact_forge_ng.form import silhouette
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART


def params(bundle_d: float, roof: str) -> SideHookParams:
    return SideHookParams(
        bundle_d=bundle_d, clearance=0.8, wall=3.2,
        mouth_gap=min(10.0, bundle_d * 0.55),
        upper_lip_len=6.0, lower_lip_len=15.0, neck_drop=8.0,
        cavity_roof=roof,
    )


@pytest.mark.parametrize("bundle_d", [8.0, 20.0, 40.0])
class TestTeardropAcrossRange:
    def test_function_identical_to_round(self, bundle_d):
        round_p, round_f = build_molded_side_hook_profile(
            params(bundle_d, "round"), MOLDED_UTILITY_PART
        )
        tear_p, tear_f = build_molded_side_hook_profile(
            params(bundle_d, "teardrop"), MOLDED_UTILITY_PART
        )
        r_rep = silhouette.measure(round_p, round_f)
        t_rep = silhouette.measure(tear_p, tear_f)
        # the FUNCTION: mouth, lips, family — bit for bit
        assert t_rep.mouth_gap == pytest.approx(r_rep.mouth_gap, abs=1e-9)
        assert t_rep.upper_lip_len == pytest.approx(r_rep.upper_lip_len, abs=1e-9)
        assert t_rep.lower_lip_len == pytest.approx(r_rep.lower_lip_len, abs=1e-9)
        assert t_rep.family_ok

    def test_all_joints_smooth(self, bundle_d):
        profile, _ = build_molded_side_hook_profile(
            params(bundle_d, "teardrop"), MOLDED_UTILITY_PART
        )
        sharp = [
            1 for a, b in profile.outer.joints()
            if not joint_is_tangent(a, b) and not ((a.tags | b.tags) & INTENTIONAL_TAGS)
        ]
        assert sharp == []

    def test_hook_deeper_by_teardrop_tail(self, bundle_d):
        _, round_f = build_molded_side_hook_profile(
            params(bundle_d, "round"), MOLDED_UTILITY_PART
        )
        tear_p, tear_f = build_molded_side_hook_profile(
            params(bundle_d, "teardrop"), MOLDED_UTILITY_PART
        )
        r_o = round_f["r_outer"]
        assert tear_f["hook_bot_v"] == pytest.approx(
            round_f["hook_bot_v"] - r_o * (math.sqrt(2.0) - 1.0), abs=1e-9
        )
        assert tear_f["cavity_teardrop"] == 1.0
        lo, _ = tear_p.outer.bbox()
        # actual bottom sits between the theoretical sharp peak and the
        # round bottom (the molded pass rounds the peak slightly)
        assert tear_f["hook_bot_v"] - 0.1 <= lo.v <= round_f["hook_bot_v"]

    def test_chamfers_are_45_degrees(self, bundle_d):
        from artifact_forge_ng.form.section import LineSeg

        profile, frame = build_molded_side_hook_profile(
            params(bundle_d, "teardrop"), MOLDED_UTILITY_PART
        )
        chamfers = [
            s for s in profile.outer.tagged("cavity_inner")
            if isinstance(s, LineSeg) and s.length > 1.0
        ]
        assert len(chamfers) == 2
        for seg in chamfers:
            t = seg.tangent_at_start()
            assert abs(abs(t.u) - abs(t.v)) < 1e-6  # exactly 45 degrees


def test_round_default_regression():
    """The default profile must be untouched by the teardrop machinery."""
    profile, frame = build_molded_side_hook_profile(
        params(20.0, "round"), MOLDED_UTILITY_PART
    )
    assert frame["cavity_teardrop"] == 0.0
    assert frame["hook_bot_v"] == pytest.approx(frame["cavity_center_v"] - frame["r_outer"])
    assert len(profile.outer.segments) == 22  # the original segment count
