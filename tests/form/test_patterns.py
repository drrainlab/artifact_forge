"""Hole-pattern expansion and min-web analytics (K4), plus cut-keepout and
revolve-axis IR checks (K3/K5) — all without CAD."""

import math

import pytest

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_cuts import check_cuts_respect_keepouts
from artifact_forge_ng.form.part import (
    BoreFeature,
    CutBoxFeature,
    HoleFeature,
    PartForm,
)
from artifact_forge_ng.form.patterns import (
    CircleOutline,
    RectOutline,
    bolt_circle_centers,
    grid_centers,
    hole_keep_radius,
    holes_from_centers,
    line_centers,
    min_web_violations,
)
from artifact_forge_ng.form.regions import Box3, Rect2D, Region, RegionRole
from artifact_forge_ng.form.section import ArcSeg, ProfileLoop, Pt
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART


class TestCenters:
    def test_line(self):
        assert line_centers(2, 50, center=(15, 0)) == [(-10.0, 0.0), (40.0, 0.0)]
        assert line_centers(1, 50) == [(0.0, 0.0)]

    def test_grid(self):
        centers = grid_centers(2, 2, 30, 20)
        assert set(centers) == {(-15, -10), (15, -10), (-15, 10), (15, 10)}

    def test_bolt_circle_exact(self):
        centers = bolt_circle_centers(4, 40)
        assert centers[0] == pytest.approx((20.0, 0.0), abs=1e-9)
        assert centers[1] == pytest.approx((0.0, 20.0), abs=1e-9)
        for x, y in centers:
            assert math.hypot(x, y) == pytest.approx(20.0, abs=1e-9)

    def test_holes_from_centers(self):
        holes = holes_from_centers([(0, 0), (10, 0)], 5.0, 5.0, "M3", "top")
        assert len(holes) == 2 and holes[0].countersink_face == "top"


class TestMinWeb:
    def make_holes(self, positions, screw="M4"):
        return holes_from_centers(positions, 5.0, 5.0, screw)

    def test_close_holes_violate(self):
        holes = self.make_holes([(0, 0), (1, 0)])
        outline = RectOutline(Rect2D(-50, -50, 50, 50))
        problems = min_web_violations(holes, outline, min_web=3.0)
        assert any("web" in p and "edge" not in p for p in problems)

    def test_spaced_holes_pass(self):
        holes = self.make_holes([(-20, 0), (20, 0)])
        outline = RectOutline(Rect2D(-40, -20, 40, 20))
        assert min_web_violations(holes, outline, min_web=3.0) == []

    def test_edge_violation_in_corner(self):
        holes = self.make_holes([(36, 16)])  # inside the corner radius zone
        outline = RectOutline(Rect2D(-40, -20, 40, 20), corner_r=8)
        problems = min_web_violations(holes, outline, min_web=3.0)
        assert any("edge web" in p for p in problems)

    def test_circle_outline_inner_bore(self):
        holes = self.make_holes([(8, 0)], screw="M3")
        outline = CircleOutline(center=(0, 0), outer_r=25, inner_r=6)
        problems = min_web_violations(holes, outline, min_web=3.0)
        assert any("edge web" in p for p in problems)  # too close to the bore

    def test_countersink_head_dominates(self):
        h = holes_from_centers([(0, 0)], 5, 5, "M4")[0]
        assert hole_keep_radius(h) == pytest.approx(7.0 / 2 + 0.3)


def _minimal_form(**kwargs) -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop(
        [
            ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
            ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
        ]
    )
    from artifact_forge_ng.form.section import SectionProfile

    return PartForm(
        name="t",
        params=kwargs.pop("params", {}),
        frame=kwargs.pop("frame", {}),
        section=SectionProfile(name="test", outer=loop),
        width=10.0,
        style=MOLDED_UTILITY_PART,
        **kwargs,
    )


class TestCutsRespectKeepouts:
    def test_cut_in_keepout_fails(self):
        form = _minimal_form(
            cutboxes=[CutBoxFeature("cut", Box3(0, 0, 0, 10, 10, 10))],
            regions=[
                Region("screws", RegionRole.FASTENER_KEEPOUT, Box3(5, 5, 5, 8, 8, 8))
            ],
        )
        finding = check_cuts_respect_keepouts(form)
        assert finding.status is Status.FAIL and finding.critical

    def test_clear_cut_passes(self):
        form = _minimal_form(
            bores=[BoreFeature("bore", "Z", (30, 30, 0), 5.0, (0, 10))],
            regions=[
                Region("screws", RegionRole.FASTENER_KEEPOUT, Box3(0, 0, 0, 10, 10, 10))
            ],
        )
        assert check_cuts_respect_keepouts(form).status is Status.PASS

    def test_infinite_cutbox_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            CutBoxFeature("bad", Box3(0, 0, 0, 10, 10))  # z1 = +inf


class TestRevolveAxisCheck:
    def test_clear_profile_passes(self):
        from artifact_forge_ng.form.checks_revolve import (
            check_revolve_profile_clear_of_axis,
        )
        from artifact_forge_ng.form.section import LineSeg, SectionProfile

        loop = ProfileLoop(
            [
                LineSeg(Pt(4, 0), Pt(20, 0)),
                LineSeg(Pt(20, 0), Pt(20, 30)),
                LineSeg(Pt(20, 30), Pt(4, 30)),
                LineSeg(Pt(4, 30), Pt(4, 0)),
            ]
        )
        form = _minimal_form(frame={"axis_clear_r": 4.0})
        form.section = SectionProfile(name="cup", outer=loop, plane="XZ", width_axis="Y")
        assert check_revolve_profile_clear_of_axis(form).status is Status.PASS

    def test_profile_touching_axis_fails(self):
        from artifact_forge_ng.form.checks_revolve import (
            check_revolve_profile_clear_of_axis,
        )
        from artifact_forge_ng.form.section import LineSeg, SectionProfile

        loop = ProfileLoop(
            [
                LineSeg(Pt(0, 0), Pt(20, 0)),
                LineSeg(Pt(20, 0), Pt(20, 30)),
                LineSeg(Pt(20, 30), Pt(0, 30)),
                LineSeg(Pt(0, 30), Pt(0, 0)),
            ]
        )
        form = _minimal_form(frame={"axis_clear_r": 4.0})
        form.section = SectionProfile(name="cup", outer=loop, plane="XZ", width_axis="Y")
        finding = check_revolve_profile_clear_of_axis(form)
        assert finding.status is Status.FAIL
