"""K3/K5 smoke: revolve produces a valid solid of revolution; bores and box
cuts remove material and revert cleanly."""

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.bores import cut_bore, cut_box  # noqa: E402
from artifact_forge_ng.cad.geometry import Geometry  # noqa: E402
from artifact_forge_ng.compiler.wires import revolve_section_profile  # noqa: E402
from artifact_forge_ng.form.part import BoreFeature, CutBoxFeature  # noqa: E402
from artifact_forge_ng.form.regions import Box3  # noqa: E402
from artifact_forge_ng.form.section import LineSeg, ProfileLoop, Pt, SectionProfile  # noqa: E402

import math  # noqa: E402


def cup_half_section() -> SectionProfile:
    """Annular cup: base ring 4..20, wall up to 30 at r 16..20."""
    pts = [
        Pt(4, 0), Pt(20, 0), Pt(20, 30), Pt(16, 30), Pt(16, 5), Pt(4, 5),
    ]
    segs = [LineSeg(a, b) for a, b in zip(pts, pts[1:] + pts[:1])]
    return SectionProfile(name="cup", outer=ProfileLoop(segs), plane="XZ", width_axis="Y")


def test_revolve_produces_valid_hollow_solid():
    solid = revolve_section_profile(cup_half_section())
    g = Geometry(solid)
    assert g.solid_count() == 1
    assert g.is_valid()
    bb = g.bounding_box()
    assert bb.width == pytest.approx(40.0, abs=0.1)  # diameter
    assert bb.height == pytest.approx(30.0, abs=0.1)
    # Hollow: much less than the full cylinder, and the axis hole is real.
    assert g.volume() < math.pi * 20**2 * 30 * 0.6


def test_revolve_rejects_wrong_plane():
    profile = cup_half_section()
    profile.plane = "YZ"
    with pytest.raises(ValueError, match="XZ"):
        revolve_section_profile(profile)


def test_cut_bore_and_box():
    body = cq.Workplane("XY").box(40, 40, 10, centered=(True, True, False))
    body, ok = cut_bore(
        body, BoreFeature("b", "Z", (0.0, 0.0, 0.0), 6.0, (0.0, 10.0))
    )
    assert ok
    body, ok = cut_box(
        body, CutBoxFeature("c", Box3(10, -5, -1, 18, 5, 11))
    )
    assert ok
    g = Geometry(body)
    assert g.solid_count() == 1 and g.is_valid()
    assert g.volume() < 40 * 40 * 10 - 200


def test_fragmenting_cut_reverts():
    # A box cut spanning the whole body would split it in two — must revert.
    body = cq.Workplane("XY").box(40, 10, 10, centered=(True, True, False))
    body, ok = cut_box(body, CutBoxFeature("split", Box3(-2, -6, -1, 2, 6, 11)))
    assert not ok
    assert Geometry(body).solid_count() == 1
