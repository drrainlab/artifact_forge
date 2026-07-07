"""The always-on manufacturing suite runs on EVERY part — the vertical
farm cleanability checks must short-circuit to PASS ("not applicable") on
parts with no water geometry, and really measure on a rail-like solid."""

import math

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.bores import cut_channel  # noqa: E402
from artifact_forge_ng.cad.geometry import Geometry  # noqa: E402
from artifact_forge_ng.core.findings import Status  # noqa: E402
from artifact_forge_ng.form.part import ChannelCutFeature, CutBoxFeature, PartForm  # noqa: E402
from artifact_forge_ng.form.regions import Box3, Region  # noqa: E402
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile  # noqa: E402
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART  # noqa: E402
from artifact_forge_ng.product.archetype import RegionRole  # noqa: E402
from artifact_forge_ng.validators.manufacturing import (  # noqa: E402
    brush_access_to_water_channel,
    no_hidden_wet_crevices,
    no_unwashable_snap_pockets,
)
from artifact_forge_ng.validators.topology import (  # noqa: E402
    water_channel_floor_solid,
    water_channel_open,
)

L, W, H = 100.0, 200.0, 30.0


def plain_form(**over) -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    kw: dict = dict(
        name="t", params={}, frame={},
        section=SectionProfile(name="t", outer=loop),
        width=5.0, style=MOLDED_UTILITY_PART,
    )
    kw.update(over)
    return PartForm(**kw)


def make_channel(**over) -> ChannelCutFeature:
    drop = W * math.tan(math.radians(1.25))
    kw: dict = dict(
        center_x=0.0, y0=W / 2.0, y1=-W / 2.0, z_top=H,
        width=16.0, depth_start=5.0, depth_end=5.0 + drop, bottom_r=1.2,
    )
    kw.update(over)
    return ChannelCutFeature(name="water", **kw)


def box_geometry() -> Geometry:
    return Geometry(cq.Workplane("XY").rect(L, W).extrude(H))


def rail_geometry(ch: ChannelCutFeature) -> Geometry:
    body, ok = cut_channel(cq.Workplane("XY").rect(L, W).extrude(H), ch)
    assert ok
    return Geometry(body)


def test_na_fast_path_on_dry_parts():
    """A part with no water geometry pays nothing for the water contract."""
    geometry = box_geometry()
    form = plain_form()
    for check in (brush_access_to_water_channel, no_hidden_wet_crevices,
                  no_unwashable_snap_pockets):
        finding = check(geometry, form)
        assert finding.status is Status.PASS, finding.check
        assert "not applicable" in finding.message


def test_brush_access_on_open_rail():
    ch = make_channel()
    form = plain_form(channels=[ch], frame={"channel_top_z": H})
    finding = brush_access_to_water_channel(rail_geometry(ch), form)
    assert finding.status is Status.PASS, finding.message


def test_brush_access_fails_on_roofed_channel():
    ch = make_channel()
    body, ok = cut_channel(cq.Workplane("XY").rect(L, W).extrude(H), ch)
    assert ok
    # weld a roof plate over the middle of the channel
    roof = cq.Workplane("XY", origin=(0.0, 0.0, H)).rect(30.0, 40.0).extrude(3.0)
    finding = brush_access_to_water_channel(
        Geometry(body.union(roof)),
        plain_form(channels=[ch], frame={"channel_top_z": H}),
    )
    assert finding.status is Status.FAIL


def test_narrow_channel_fails_brush_access():
    ch = make_channel(width=12.0)
    narrow = make_channel(width=8.0, bottom_r=1.0)
    finding = brush_access_to_water_channel(
        rail_geometry(ch), plain_form(channels=[narrow])
    )
    assert finding.status is Status.FAIL


def test_crevice_in_wet_region_flagged():
    wet = Region("water_channel", RegionRole.TRANSIENT_WATER_PATH,
                 Box3(-8.0, -100.0, 15.0, 8.0, 100.0, 30.0))
    sliver = CutBoxFeature("sliver", Box3(-8.0, -50.0, 20.0, 8.0, -48.8, 30.0))
    form = plain_form(regions=[wet], cutboxes=[sliver])
    finding = no_hidden_wet_crevices(box_geometry(), form)
    assert finding.status is Status.FAIL
    assert "sliver" in finding.message


def test_water_topology_probes_on_solid():
    ch = make_channel()
    geometry = rail_geometry(ch)
    form = plain_form(channels=[ch])
    assert water_channel_open(geometry, form).status is Status.PASS
    assert water_channel_floor_solid(geometry, form).status is Status.PASS
    # an uncut box: the channel path is solid -> open fails, floor passes
    assert water_channel_open(box_geometry(), form).status is Status.FAIL
