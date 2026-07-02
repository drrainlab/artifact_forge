import math

import pytest

from artifact_forge_ng.form.section import (
    ArcSeg,
    LineSeg,
    ProfileLoop,
    Pt,
    plane_mapping,
)


def square(side: float = 10.0) -> list[LineSeg]:
    a, b, c, d = Pt(0, 0), Pt(side, 0), Pt(side, side), Pt(0, side)
    return [LineSeg(a, b), LineSeg(b, c), LineSeg(c, d), LineSeg(d, a)]


class TestProfileLoop:
    def test_square_area_and_perimeter(self):
        loop = ProfileLoop(square())
        assert loop.area() == pytest.approx(100.0)
        assert loop.perimeter() == pytest.approx(40.0)

    def test_cw_input_auto_reversed_to_ccw(self):
        cw = [s.reversed() for s in reversed(square())]
        loop = ProfileLoop(cw)
        assert loop.area() == pytest.approx(100.0)  # positive => CCW stored

    def test_unclosed_loop_rejected(self):
        segs = square()
        segs[2] = LineSeg(segs[2].a, Pt(99, 99))
        with pytest.raises(ValueError, match="not closed"):
            ProfileLoop(segs)

    def test_circle_area_from_two_arcs(self):
        c = Pt(0, 0)
        right = ArcSeg(Pt(0, -5), Pt(0, 5), c, ccw=True)
        left = ArcSeg(Pt(0, 5), Pt(0, -5), c, ccw=True)
        loop = ProfileLoop([right, left])
        assert loop.area() == pytest.approx(math.pi * 25, rel=1e-9)
        assert loop.perimeter() == pytest.approx(2 * math.pi * 5, rel=1e-9)

    def test_arc_radius_mismatch_rejected(self):
        with pytest.raises(ValueError, match="radii differ"):
            ArcSeg(Pt(0, -5), Pt(0, 6), Pt(0, 0), ccw=True)

    def test_arc_tangents(self):
        arc = ArcSeg(Pt(5, 0), Pt(0, 5), Pt(0, 0), ccw=True)
        t = arc.tangent_at_start()
        assert (t.u, t.v) == pytest.approx((0.0, 1.0))

    def test_tagging(self):
        segs = square()
        segs[0] = segs[0].with_tags("bottom")
        loop = ProfileLoop(segs)
        assert len(loop.tagged("bottom")) == 1


class TestPlaneMapping:
    def test_flagship_mapping(self):
        m = plane_mapping("YZ", "X")
        assert m(2.0, -3.0, 15.0) == (15.0, 2.0, -3.0)

    def test_unsupported_pair_raises(self):
        with pytest.raises(ValueError, match="unsupported plane"):
            plane_mapping("YZ", "Y")
