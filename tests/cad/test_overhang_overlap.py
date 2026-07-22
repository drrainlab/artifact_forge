"""Layer-overlap self-support (manufacturing.overhang_overlap): the
micro-scale model f = 1 - h*tan(alpha)/w measured on the tessellated
solid in the PRINT pose. The limit is derived from the instance's real
layer height and line width — a 60 deg underside fails at 0.2 mm layers
and legitimately passes at 0.1 mm; near-horizontal undersides are
handed to the span checks, never double-punished here."""

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.geometry import Geometry  # noqa: E402
from artifact_forge_ng.core.findings import Status  # noqa: E402
from artifact_forge_ng.form.part import PartForm  # noqa: E402
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile  # noqa: E402
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART  # noqa: E402
from artifact_forge_ng.validators.manufacturing import overhang_overlap  # noqa: E402


def make_form(h=0.2, w=0.4, orientation="as_modeled") -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    return PartForm(
        name="t", params={"layer_height": h, "nozzle_d": w}, frame={},
        section=SectionProfile(name="t", outer=loop),
        width=30.0, style=MOLDED_UTILITY_PART,
        print_orientation=orientation,
    )


def shelf(overhang_dx: float) -> Geometry:
    """A shelf whose underside slopes from (0,10) out to (-dx,20): the
    sloped downward face's angle from vertical is atan(dx/10)."""
    wp = (cq.Workplane("XZ")
          .polyline([(0, 0), (10, 0), (10, 30), (-overhang_dx, 30),
                     (-overhang_dx, 20), (0, 10)])
          .close().extrude(20))
    return Geometry(wp)


def test_plain_box_has_no_overhangs():
    box = Geometry(cq.Workplane("XY").box(40, 40, 20,
                                          centered=(True, True, False)))
    f = overhang_overlap(box, make_form())
    assert f.status is Status.PASS
    assert "self-supporting by construction" in f.message


def test_45deg_underside_is_exactly_the_folklore_limit():
    f = overhang_overlap(shelf(10.0), make_form())  # 45 deg from vertical
    assert f.status is Status.PASS
    assert f.limit == pytest.approx(45.0)
    assert f.measured == pytest.approx(45.0, abs=0.5)


def test_60deg_underside_fails_at_02_layers():
    f = overhang_overlap(shelf(17.32), make_form(h=0.2))
    assert f.status is Status.FAIL
    assert "at-risk region" in f.message
    assert "thinner layers" in f.suggestion


def test_60deg_underside_passes_at_01_layers():
    """The whole point over the flat 45 deg rule: thinner layers EARN
    steeper faces — same geometry, different print profile, honest pass."""
    f = overhang_overlap(shelf(17.32), make_form(h=0.1))
    assert f.status is Status.PASS
    assert f.limit == pytest.approx(63.4, abs=0.1)


def test_flat_cantilever_goes_to_the_bridge_domain():
    t = (cq.Workplane("XY").box(10, 40, 20, centered=(True, True, False))
         .union(cq.Workplane("XY", origin=(0, 0, 20))
                .box(40, 40, 10, centered=(True, True, False))))
    f = overhang_overlap(Geometry(t), make_form())
    assert f.status is Status.PASS  # micro regime clean; macro owned by spans
    assert "bridge/support domain" in f.message


def test_perforation_roofs_stay_in_the_micro_regime():
    """A perforated vertical plate: every window roof is steep (60 deg
    from vertical > the h0.2 limit) but perforation-scale — anchored on
    both cell walls, cooling-dominated. Reported, never gated: the sum
    of tiny roofs must not fail like one big sloped surface would."""
    plate = cq.Workplane("XY").box(60, 4, 40, centered=(True, True, False))
    for x0 in (-25.0, -11.0, 3.0, 17.0):
        win = (cq.Workplane("XZ", origin=(0, 5, 0))
               .polyline([(x0, 10), (x0 + 10, 10), (x0 + 10, 18),
                          (x0 + 5, 20.89), (x0, 18)])
               .close().extrude(10))
        plate = plate.cut(win)
    f = overhang_overlap(Geometry(plate), make_form())
    assert f.status is Status.PASS
    assert "micro roofs" in f.message


def test_sideprint_pose_rescues_the_steep_shelf():
    """The same 60 deg shelf extruded along X prints support-free lying
    on its constant section — the probe must judge the PRINT pose."""
    wp = (cq.Workplane("YZ")
          .polyline([(0, 0), (10, 0), (10, 30), (-17.32, 30),
                     (-17.32, 20), (0, 10)])
          .close().extrude(20))
    as_modeled = overhang_overlap(Geometry(wp), make_form())
    sideprint = overhang_overlap(Geometry(wp),
                                 make_form(orientation="side_profile"))
    assert as_modeled.status is Status.FAIL
    assert sideprint.status is Status.PASS
