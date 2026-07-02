"""Sideprint variant, tier-1: the tongue profile keeps the hook's function
bit-for-bit, the constant-section claim is checked (and checkable), screws
land behind the hook where a driver reaches them."""

from pathlib import Path

import pytest

from artifact_forge_ng.form import silhouette
from artifact_forge_ng.form.part import PlateFeature
from artifact_forge_ng.form.profiles import (
    SideHookParams,
    build_molded_side_hook_profile,
    build_tongue_side_hook_profile,
)
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.form.validators import (
    check_constant_section,
    check_mount_face_flat,
    check_screw_access_clear,
)
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


def params(bundle_d: float) -> SideHookParams:
    return SideHookParams(
        bundle_d=bundle_d, clearance=0.8, wall=3.2,
        mouth_gap=min(10.0, bundle_d * 0.55),
        upper_lip_len=6.0, lower_lip_len=15.0, neck_drop=8.0,
    )


@pytest.mark.parametrize("bundle_d", [8.0, 20.0, 40.0])
def test_function_identical_to_v2(bundle_d):
    """The tongue changes WHERE the part mounts, never what it holds."""
    v2_p, v2_f = build_molded_side_hook_profile(params(bundle_d), MOLDED_UTILITY_PART)
    v3_p, v3_f = build_tongue_side_hook_profile(
        params(bundle_d), -(params(bundle_d).r_outer + 40.0), 5.0, MOLDED_UTILITY_PART
    )
    r2 = silhouette.measure(v2_p, v2_f)
    r3 = silhouette.measure(v3_p, v3_f)
    assert r3.family_ok, r3.family_problems
    assert r3.mouth_gap == pytest.approx(r2.mouth_gap, abs=1e-9)
    assert r3.upper_lip_len == pytest.approx(r2.upper_lip_len, abs=1e-9)
    assert r3.lower_lip_len == pytest.approx(r2.lower_lip_len, abs=1e-9)


@pytest.fixture(scope="module")
def sideprint_state():
    return run_pre_cad(EXAMPLES / "desk_cable_clip_20mm_sideprint.yaml", None)


def test_example_form_checks_green(sideprint_state):
    fails = [
        f for f in sideprint_state.report.findings if f.status.value == "fail"
    ]
    assert fails == []


def test_print_orientation_declared(sideprint_state):
    assert sideprint_state.form.print_orientation == "side_profile"


def test_constant_section_and_mount_face(sideprint_state):
    form = sideprint_state.form
    assert check_constant_section(form).status.value == "pass"
    assert check_mount_face_flat(form).status.value == "pass"
    assert not form.plates  # the flange is IN the profile, not welded on


def test_screws_behind_hook_with_access(sideprint_state):
    form = sideprint_state.form
    r_o = form.frame["r_outer"]
    for i in range(2):
        assert form.frame[f"screw_y_{i}"] < -r_o
    assert check_screw_access_clear(form).status.value == "pass"


def test_negative_plate_breaks_constant_section(sideprint_state):
    """Sabotage: welding a plate onto the sideprint form must kill the
    constant-section claim — the support-free feature is verified, never
    grandfathered."""
    form = sideprint_state.form
    form.plates.append(
        PlateFeature(name="rogue", x0=-10, y0=-10, x1=10, y1=10,
                     z_bottom=0.0, thickness=4.0)
    )
    try:
        finding = check_constant_section(form)
        assert finding.status.value == "fail"
        assert "plates" in finding.message
    finally:
        form.plates.clear()


def test_negative_screw_over_hook_blocked(sideprint_state):
    """A hole moved over the hook footprint is unreachable by a driver."""
    from artifact_forge_ng.form.part import HoleFeature

    form = sideprint_state.form
    bad = HoleFeature(at=(form.width / 2.0, 0.0, form.frame["tongue_t"]),
                      screw="M4", through=5.0)
    form.holes.append(bad)
    try:
        finding = check_screw_access_clear(form)
        assert finding.status.value == "fail"
    finally:
        form.holes.remove(bad)
