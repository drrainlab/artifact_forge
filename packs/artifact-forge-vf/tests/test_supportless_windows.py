"""VF-4.1 always-on printability checks, measured on real solids: a blind
bottom pocket with a wide flat ceiling is a bridge (WARN <= 35, FAIL
above), a THROUGH opening is supportless by construction, a horizontal
circular bore over d8 sags unless teardrop-roofed — and every dry part
without such features takes the n/a fast-path."""

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.geometry import Geometry  # noqa: E402
from artifact_forge_ng.core.findings import Status  # noqa: E402
from artifact_forge_ng.form.part import BoreFeature, CutBoxFeature, PartForm  # noqa: E402
from artifact_forge_ng.form.regions import Box3  # noqa: E402
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile  # noqa: E402
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART  # noqa: E402
from artifact_forge_vf.manufacturing import (  # noqa: E402
    supportless_lightweight_windows_ok,
)

L, W, H = 120.0, 120.0, 30.0


def make_form(cutboxes=(), bores=(), orientation="as_modeled") -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    return PartForm(
        name="t", params={}, frame={},
        section=SectionProfile(name="t", outer=loop),
        width=H, style=MOLDED_UTILITY_PART,
        print_orientation=orientation,
        cutboxes=list(cutboxes), bores=list(bores),
    )


def solid_with(cutboxes=()) -> Geometry:
    body = cq.Workplane("XY").box(L, W, H, centered=(True, True, False))
    for c in cutboxes:
        b = c.box
        cutter = (cq.Workplane("XY", origin=((b.x0 + b.x1) / 2,
                                             (b.y0 + b.y1) / 2, b.z0))
                  .rect(b.x1 - b.x0, b.y1 - b.y0).extrude(b.z1 - b.z0))
        body = body.cut(cutter)
    return Geometry(body)


BLIND_40 = CutBoxFeature("body_lwin_a", Box3(-20.0, -20.0, -1.0, 20.0, 20.0, 20.0))
BLIND_30 = CutBoxFeature("body_lwin_b", Box3(-15.0, -15.0, -1.0, 15.0, 15.0, 20.0))
THROUGH_40 = CutBoxFeature("body_lwin_c", Box3(-20.0, -20.0, -1.0, 20.0, 20.0, 31.0))


def test_wide_blind_flat_ceiling_fails():
    form = make_form(cutboxes=[BLIND_40])
    f = supportless_lightweight_windows_ok(solid_with([BLIND_40]), form)
    assert f.status is Status.FAIL
    assert "flat ceiling" in f.message


def test_medium_blind_ceiling_warns():
    form = make_form(cutboxes=[BLIND_30])
    f = supportless_lightweight_windows_ok(solid_with([BLIND_30]), form)
    assert f.status is Status.WARN
    assert "sag" in f.message


def test_through_opening_passes():
    """The open-skeleton case: the pocket exits into open air above (here
    modeled as a cut through the whole body) — no ceiling, no bridge."""
    # IR says the box stops at z=20, geometry says the material above is
    # gone (through cut) — the SOLID is the truth the check reads
    form = make_form(cutboxes=[CutBoxFeature("body_lwin_c",
                                             Box3(-20.0, -20.0, -1.0, 20.0, 20.0, 20.0))])
    f = supportless_lightweight_windows_ok(solid_with([THROUGH_40]), form)
    assert f.status is Status.PASS
    assert "through-open" in f.message


def test_no_bottom_pockets_is_na():
    form = make_form()
    f = supportless_lightweight_windows_ok(solid_with(), form)
    assert f.status is Status.PASS
    assert "n/a" in f.message


def test_sideprint_is_na():
    form = make_form(cutboxes=[BLIND_40], orientation="side_profile")
    f = supportless_lightweight_windows_ok(solid_with([BLIND_40]), form)
    assert f.status is Status.PASS


