"""Bio-1 split branch clamp, tier-1: the pure profile builders — loop
closure/simplicity, saddle circle exactness, pad land count/width/recess,
real dovetail (top wider than root), and honest refusals at the edge
cases. No CAD, no catalog."""

import math

import pytest

from artifact_forge_ng.form.profiles_clamp import (
    ClampHalfParams,
    build_clamp_lower_profile,
    build_clamp_upper_profile,
    clamp_lower_frame,
    clamp_upper_frame,
)
from artifact_forge_ng.form.section import ArcSeg, LineSeg, Pt
from artifact_forge_ng.form.validators import check_profile_closed, check_profile_smooth

BRANCHES = [30.0, 45.0, 60.0, 80.0, 100.0]


def _params(branch_d: float, **over) -> ClampHalfParams:
    defaults = dict(branch_d=branch_d, bolt_y=branch_d / 2.0 + 8.0)
    defaults.update(over)
    return ClampHalfParams(**defaults)


def _dist_point_line(c: Pt, a: Pt, b: Pt) -> float:
    ab = b - a
    return abs(ab.cross(c - a)) / ab.norm()


@pytest.mark.parametrize("branch_d", BRANCHES)
@pytest.mark.parametrize("half", ["lower", "upper"])
def test_sweep_loop_closes_and_measures(branch_d, half):
    p = _params(branch_d)
    build = build_clamp_lower_profile if half == "lower" else build_clamp_upper_profile
    profile, f = build(p)
    loop = profile.outer

    # one closed simple CCW loop with positive area
    assert check_profile_closed(loop).status.value == "pass"
    assert check_profile_smooth(loop).status.value == "pass"
    assert loop.area() > 0.0

    # the saddle arcs ARE the declared branch circle, centered gap/2 beyond
    # the mating plane
    center = Pt(0.0, f["saddle_cz"])
    arcs = [s for s in loop.tagged("saddle_contact") if isinstance(s, ArcSeg)]
    assert arcs
    for a in arcs:
        assert a.radius == pytest.approx(branch_d / 2.0, abs=1e-6)
        assert a.center.dist(center) < 1e-6
    assert abs(f["saddle_cz"] - f["mate_z"]) == pytest.approx(p.gap / 2.0)

    # the mouth is OPEN at the mating plane: extreme arc endpoints land on it
    tips = [pt for a in arcs for pt in (a.a, a.b)
            if abs(pt.v - f["mate_z"]) < 1e-6]
    assert len(tips) == 2
    assert sorted(pt.u for pt in tips) == pytest.approx(
        [-f["saddle_mouth_half"], f["saddle_mouth_half"]])

    # pad lands: count, width, recess (distance from the saddle center to
    # the flat's LINE is exactly r + pad_recess)
    lands = [s for s in loop.tagged("pad_land") if isinstance(s, LineSeg)]
    assert len(lands) == (2 if half == "lower" else 1)
    assert int(f["land_count"]) == len(lands)
    for flat in lands:
        assert flat.length == pytest.approx(p.land_w, abs=1e-6)
        assert _dist_point_line(center, flat.a, flat.b) == pytest.approx(
            branch_d / 2.0 + p.pad_recess, abs=1e-6)
    walls = [s for s in loop.tagged("pad_wall") if isinstance(s, LineSeg)]
    assert len(walls) == 2 * len(lands)
    for wall in walls:  # radial, never tangent
        mid = wall.point_at(0.5)
        radial = (mid - center).unit()
        along = (wall.b - wall.a).unit()
        assert abs(radial.cross(along)) < 1e-6


@pytest.mark.parametrize("branch_d", BRANCHES)
def test_sweep_dovetail_is_real(branch_d):
    p = _params(branch_d)
    profile, f = build_clamp_upper_profile(p)
    flanks = profile.outer.tagged("rail_flank")
    top = profile.outer.tagged("rail_top")
    assert len(flanks) == 2 and len(top) == 1
    assert f["rail_top_w"] > f["rail_root_w"]
    expected_root = p.rail_w - 2.0 * p.rail_h * math.tan(math.radians(p.rail_angle))
    assert f["rail_root_w"] == pytest.approx(expected_root)
    # measured on segments, not the frame: undercut really exists
    root_us = sorted(pt.u for s in flanks for pt in (s.a, s.b)
                     if abs(pt.v - f["rail_v0"]) < 1e-6)
    top_us = sorted(pt.u for s in flanks for pt in (s.a, s.b)
                    if abs(pt.v - f["rail_v1"]) < 1e-6)
    assert top_us[1] - top_us[0] > root_us[1] - root_us[0]


def test_lower_frame_math():
    p = _params(60.0)
    f = clamp_lower_frame(p)
    assert f["saddle_r"] == pytest.approx(30.0)
    assert f["mate_z"] == pytest.approx(8.0 + 30.0 - 1.5)
    assert f["saddle_cz"] == pytest.approx(f["mate_z"] + 1.5)
    assert f["saddle_apex_v"] == pytest.approx(8.0)
    assert f["saddle_mouth_half"] == pytest.approx(math.sqrt(30.0**2 - 1.5**2))
    assert f["mouth_gap"] == pytest.approx(2.0 * f["saddle_mouth_half"])
    assert f["cavity_center_v"] == pytest.approx(f["saddle_cz"])
    assert f["r_cavity"] == pytest.approx(30.0)


def test_upper_frame_math():
    p = _params(60.0)
    f = clamp_upper_frame(p)
    assert f["mate_z"] == 0.0
    assert f["saddle_cz"] == pytest.approx(-1.5)
    assert f["saddle_apex_v"] == pytest.approx(28.5)
    assert f["rail_v0"] == pytest.approx(28.5 + 20.0)
    assert f["rail_v1"] == pytest.approx(28.5 + 20.0 + 6.0)


def test_shallow_flange_edge_case_collapses_the_step():
    """Wings narrower than the body: the profile degrades to straight
    sides instead of a self-intersecting step."""
    p = _params(60.0, bolt_y=25.0, edge_m=6.0, wall=4.0)
    # wing_u_out=31 < body_half=34: no step
    profile, f = build_clamp_lower_profile(p)
    assert check_profile_closed(profile.outer).status.value == "pass"
    lo, hi = profile.outer.bbox()
    assert hi.u == pytest.approx(f["wing_u_out"], abs=1e-6)


def test_wing_inside_the_mouth_is_refused():
    with pytest.raises(ValueError, match="inside the saddle mouth"):
        clamp_lower_frame(_params(60.0, bolt_y=12.0, edge_m=2.0))


def test_overlapping_lands_are_refused():
    with pytest.raises(ValueError, match="pad land"):
        build_clamp_lower_profile(_params(30.0, land_w=26.0))


def test_degenerate_gap_and_rail_are_refused():
    with pytest.raises(ValueError, match="compression gap"):
        clamp_lower_frame(_params(60.0, gap=0.2))
    with pytest.raises(ValueError, match="dovetail root"):
        clamp_upper_frame(_params(60.0, rail_w=10.0, rail_h=8.0, rail_angle=25.0))
    with pytest.raises(ValueError, match="rail_angle"):
        clamp_upper_frame(_params(60.0, rail_angle=40.0))


def test_rail_angle_zero_builds_a_rectangle_not_a_crash():
    """rail_angle 0 is legal at the profile level — the dovetail CHECK is
    what fails it (negative covered in test_clamp_recipe)."""
    profile, f = build_clamp_upper_profile(_params(60.0, rail_angle=0.0))
    assert f["rail_top_w"] == pytest.approx(f["rail_root_w"])
    assert check_profile_closed(profile.outer).status.value == "pass"
