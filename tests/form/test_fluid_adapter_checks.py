"""Mutation tests for the VF-3 fluid adapter checks: a healthy hand-built
cap IR (vertical hose drop through a descending spout) and collector IR
(sloped catch tray into a through drain) pass; each surgical break fails
exactly the owning check."""

import math

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_water import (
    check_collector_tray_drains,
    check_hose_bore_ok,
    check_spout_drop_path_ok,
)
from artifact_forge_ng.form.part import (
    BoreFeature,
    ChannelCutFeature,
    PartForm,
    RibFeature,
)
from artifact_forge_ng.form.regions import Box3
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART

TUBE_OD = 9.0
BORE_D = 9.4


def make_form(name="adapter", frame=None, bores=None, ribs=None,
              channels=None) -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    return PartForm(
        name=name, params={}, frame=frame or {},
        section=SectionProfile(name=name, outer=loop),
        width=22.0, style=MOLDED_UTILITY_PART,
        bores=bores or [], ribs=ribs or [], channels=channels or [],
    )


# -- inlet cap ---------------------------------------------------------------

def cap_frame(**over) -> dict:
    f = dict(
        hose_tube_od=TUBE_OD, spout_w=14.0, rail_channel_w=16.0,
        channel_floor_z_outlet=-8.5, saddle_floor_z=8.0,
    )
    f.update(over)
    return f


def cap_bore(**over) -> BoreFeature:
    kw: dict = dict(
        name="hose_drop", axis="Z", center=(0.0, -14.0, 0.0),
        d=BORE_D, span=(-8.5, 22.0), overshoot=(1.0, 1.0),
    )
    kw.update(over)
    return BoreFeature(**kw)


def cap_spout() -> RibFeature:
    return RibFeature("cap_spout", Box3(-9.0, -18.0, -9.5, 9.0, -10.0, 0.6))


def healthy_cap() -> PartForm:
    return make_form("cap", frame=cap_frame(), bores=[cap_bore()],
                     ribs=[cap_spout()])


def test_healthy_cap_passes():
    form = healthy_cap()
    for check in (check_hose_bore_ok, check_spout_drop_path_ok):
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_loose_hose_bore_rejected():
    form = make_form("cap", frame=cap_frame(),
                     bores=[cap_bore(d=TUBE_OD + 1.5)], ribs=[cap_spout()])
    assert check_hose_bore_ok(form).status is Status.FAIL


def test_blind_hose_bore_rejected():
    form = make_form("cap", frame=cap_frame(),
                     bores=[cap_bore(overshoot=(0.0, 1.0))], ribs=[cap_spout()])
    finding = check_hose_bore_ok(form)
    assert finding.status is Status.FAIL
    assert "blind" in finding.message


def test_missing_spout_rejected():
    form = make_form("cap", frame=cap_frame(), bores=[cap_bore()])
    finding = check_spout_drop_path_ok(form)
    assert finding.status is Status.FAIL
    assert "no spout rib" in finding.message


def test_spout_above_body_rejected():
    form = make_form("cap", frame=cap_frame(channel_floor_z_outlet=2.0),
                     bores=[cap_bore()], ribs=[cap_spout()])
    finding = check_spout_drop_path_ok(form)
    assert finding.status is Status.FAIL
    assert "descend" in finding.message


def test_wide_spout_rejected():
    form = make_form("cap", frame=cap_frame(spout_w=15.5),
                     bores=[cap_bore()], ribs=[cap_spout()])
    finding = check_spout_drop_path_ok(form)
    assert finding.status is Status.FAIL
    assert "channel" in finding.message


def test_interrupted_drop_rejected():
    form = make_form("cap", frame=cap_frame(),
                     bores=[cap_bore(span=(-2.0, 22.0))], ribs=[cap_spout()])
    finding = check_spout_drop_path_ok(form)
    assert finding.status is Status.FAIL
    assert "interrupted" in finding.message


# -- collector ----------------------------------------------------------------

TRAY_RUN = 20.0
TRAY_DROP = TRAY_RUN * math.tan(math.radians(1.5))


def tray_channel(**over) -> ChannelCutFeature:
    kw: dict = dict(
        center_x=0.0, y0=10.0, y1=-10.0, z_top=8.0,
        width=20.0, depth_start=3.0, depth_end=3.0 + TRAY_DROP, bottom_r=1.0,
    )
    kw.update(over)
    return ChannelCutFeature(name="tray", **kw)


#: tray floor low point (design z) at the deep end and its Y (VF-4.2).
FLOOR_LOW = 8.0 - (3.0 + TRAY_DROP)
DRAIN_Y = -9.0


def drain_bore(**over) -> BoreFeature:
    # VF-4.2: VERTICAL bore descending from the tray low floor out the
    # bottom — the tube pushes in from below.
    kw: dict = dict(
        name="drain_hose", axis="Z", center=(0.0, DRAIN_Y, 0.0),
        d=BORE_D, span=(-2.0, FLOOR_LOW + 0.5), overshoot=(1.0, 1.0),
    )
    kw.update(over)
    return BoreFeature(**kw)


def collector_frame(**over) -> dict:
    f = {"hose_tube_od": TUBE_OD, "tray_floor_low_z": FLOOR_LOW,
         "drain_low_y": DRAIN_Y}
    f.update(over)
    return f


def healthy_collector() -> PartForm:
    return make_form("collector", frame=collector_frame(),
                     channels=[tray_channel()], bores=[drain_bore()])


def test_healthy_collector_passes():
    form = healthy_collector()
    for check in (check_hose_bore_ok, check_collector_tray_drains):
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_flat_tray_rejected():
    form = make_form("collector", frame=collector_frame(),
                     channels=[tray_channel(depth_end=3.0001)],
                     bores=[drain_bore()])
    assert check_collector_tray_drains(form).status is Status.FAIL


def test_missing_drain_rejected():
    form = make_form("collector", frame=collector_frame(),
                     channels=[tray_channel()])
    finding = check_collector_tray_drains(form)
    assert finding.status is Status.FAIL
    assert "reservoir" in finding.message


def test_horizontal_drain_rejected():
    """A horizontal drain is the old sideways spit — VF-4.2 drains down."""
    form = make_form("collector", frame=collector_frame(),
                     channels=[tray_channel()],
                     bores=[drain_bore(axis="Y")])
    finding = check_collector_tray_drains(form)
    assert finding.status is Status.FAIL
    assert "VERTICALLY" in finding.message


def test_drain_short_of_floor_rejected():
    """A vertical bore whose top stops below the tray low floor leaves
    standing water above it."""
    form = make_form("collector", frame=collector_frame(),
                     channels=[tray_channel()],
                     bores=[drain_bore(span=(-2.0, FLOOR_LOW - 3.0),
                                       overshoot=(1.0, 0.0))])
    finding = check_collector_tray_drains(form)
    assert finding.status is Status.FAIL
    assert "never reaches" in finding.message


def test_drain_not_at_low_point_rejected():
    form = make_form("collector", frame=collector_frame(),
                     channels=[tray_channel()],
                     bores=[drain_bore(center=(0.0, 5.0, 0.0))])
    finding = check_collector_tray_drains(form)
    assert finding.status is Status.FAIL
    assert "low point" in finding.message


def test_blind_drain_rejected():
    """A bore that does not exit the bottom traps water."""
    form = make_form("collector", frame=collector_frame(),
                     channels=[tray_channel()],
                     bores=[drain_bore(overshoot=(0.0, 1.0))])
    finding = check_collector_tray_drains(form)
    assert finding.status is Status.FAIL
    assert "exit the bottom" in finding.message
