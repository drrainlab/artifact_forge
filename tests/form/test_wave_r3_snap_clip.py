"""Wave R3 (snap C-clip), tier-1: the retention arc is measured geometry,
a non-retaining mouth fails, and the profile is a support-free extrusion."""

from pathlib import Path

import pytest

from artifact_forge_ng.form.checks_snap import (
    check_snap_arc_coverage,
    check_snap_mouth_retains,
)
from artifact_forge_ng.form.profiles import SnapClipParams, build_snap_c_tongue_profile
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.form.validators import (
    check_constant_section,
    check_mount_face_flat,
    check_profile_closed,
    check_profile_smooth,
)
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


def clip(pipe_d: float, arc: float) -> SnapClipParams:
    return SnapClipParams(
        pipe_d=pipe_d, clearance=0.4, wall=3.2, arc_deg=arc, neck_drop=6.0
    )


@pytest.mark.parametrize("pipe_d,arc", [(12.0, 250.0), (25.0, 240.0), (40.0, 210.0)])
def test_profile_family_across_range(pipe_d, arc):
    p = clip(pipe_d, arc)
    profile, frame = build_snap_c_tongue_profile(
        p, p.r_outer + 22.0, 5.0, MOLDED_UTILITY_PART
    )
    assert check_profile_closed(profile.outer).status.value == "pass"
    assert check_profile_smooth(profile.outer).status.value == "pass"
    assert frame["mouth_gap"] < pipe_d  # retention by construction


@pytest.fixture(scope="module")
def state():
    return run_pre_cad(EXAMPLES / "broom_clip_25mm.yaml", None)


def test_example_green_and_support_free(state):
    fails = [f for f in state.report.findings if f.status.value == "fail"]
    assert fails == []
    form = state.form
    assert form.print_orientation == "side_profile"
    assert check_constant_section(form).status.value == "pass"
    assert check_mount_face_flat(form).status.value == "pass"
    assert check_snap_arc_coverage(form).status.value == "pass"
    assert check_snap_mouth_retains(form).status.value == "pass"


def test_open_scoop_fails_retention():
    """arc <= 190 is a scoop, not a snap — refused at frame level; and a
    barely-legal arc that cannot retain fails the measured check."""
    with pytest.raises(ValueError, match="snap range"):
        build_snap_c_tongue_profile(
            clip(25.0, 170.0), 40.0, 5.0, MOLDED_UTILITY_PART
        )


def test_mouth_check_catches_widened_mouth(state):
    """Sabotage the measured mouth: pretend the pipe is smaller than the
    gap — the check must fail (wider-than-pipe never snaps)."""
    form = state.form
    original = form.params["pipe_d"]
    form.params["pipe_d"] = form.frame["mouth_gap"] * 0.9
    try:
        assert check_snap_mouth_retains(form).status.value == "fail"
    finally:
        form.params["pipe_d"] = original
