"""Mutation tests for the fluid adapter checks. VF-9.2 cap: a healthy
hand-built chute-cap IR (stepped tube socket with a stop shoulder, drip
orifice, covered chamber, OPEN U-trough) and collector IR (sloped catch tray
into a through drain) pass; each surgical break fails exactly the owning
check."""

import math

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_water import (
    check_cap_water_path_visible,
    check_collector_tray_drains,
    check_hose_bore_ok,
    check_no_standing_water_ir,
    check_spout_drop_path_ok,
)
from artifact_forge_ng.form.part import (
    BoreFeature,
    ChannelCutFeature,
    CutBoxFeature,
    PartForm,
    RibFeature,
)
from artifact_forge_ng.form.regions import Box3, Region
from artifact_forge_ng.form.section import ArcSeg, Pt, ProfileLoop, SectionProfile
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.archetype import RegionRole

TUBE_OD = 9.0
BORE_D = 9.4


def make_form(name="adapter", frame=None, bores=None, ribs=None,
              channels=None, cutboxes=None, regions=None,
              datums=None) -> PartForm:
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
        cutboxes=cutboxes or [], regions=regions or [], datums=datums or {},
    )


# -- inlet cap (VF-9.2 chute-cap geometry, mirroring the op's numbers) ---------

Y_SOCK = 6.7        # socket/orifice axis
STOP_Z = 10.0       # tube-stop shoulder plane (cap_h 22 - socket_depth 12)
CHAMBER_TOP = 6.0   # chamber ceiling = orifice exit
TIP_Y = -4.5        # chute tip (DRIP_INSET inboard of the rail face)
Z_EXIT = -8.5       # drip height (trough floor top)


def cap_frame(**over) -> dict:
    f = dict(
        hose_tube_od=TUBE_OD, hose_bore_d=BORE_D,
        hose_socket_depth=12.0, hose_socket_y=Y_SOCK, drip_orifice_d=5.0,
        chute_tip_y=TIP_Y, chute_uphill_y=9.5,
        spout_w=14.0, rail_channel_w=16.0, channel_top_z=22.0,
        channel_floor_z_outlet=Z_EXIT, saddle_floor_z=8.0,
    )
    f.update(over)
    return f


def cap_socket(**over) -> BoreFeature:
    kw: dict = dict(
        name="cap_hose_socket", axis="Z", center=(0.0, Y_SOCK, 0.0),
        d=BORE_D, span=(STOP_Z, 22.0), overshoot=(0.0, 1.0),
    )
    kw.update(over)
    return BoreFeature(**kw)


def cap_orifice(**over) -> BoreFeature:
    kw: dict = dict(
        name="cap_hose_drop", axis="Z", center=(0.0, Y_SOCK, 0.0),
        d=5.0, span=(CHAMBER_TOP, STOP_Z), overshoot=(1.0, 1.0),
    )
    kw.update(over)
    return BoreFeature(**kw)


def cap_trough() -> list[RibFeature]:
    return [
        RibFeature("cap_nose_wall_e", Box3(5.0, TIP_Y, Z_EXIT - 1.0, 7.0, 9.5, 8.0)),
        RibFeature("cap_nose_wall_w", Box3(-7.0, TIP_Y, Z_EXIT - 1.0, -5.0, 9.5, 8.0)),
        RibFeature("cap_nose_floor", Box3(-7.0, TIP_Y, Z_EXIT - 1.0, 7.0, 9.5, Z_EXIT)),
    ]


def cap_cuts() -> list[CutBoxFeature]:
    return [
        CutBoxFeature("cap_chamber", Box3(-5.0, 0.4, -9.5, 5.0, 9.5, CHAMBER_TOP)),
        CutBoxFeature("cap_chute_sky", Box3(-5.0, -4.0, -9.5, 5.0, 0.4, 23.0)),
    ]


def healthy_cap(**frame_over) -> PartForm:
    return make_form(
        "cap", frame=cap_frame(**frame_over),
        bores=[cap_socket(), cap_orifice()],
        ribs=cap_trough(), cutboxes=cap_cuts(),
        datums={"spout": {"at": [0.0, TIP_Y, Z_EXIT], "rotate": [0.0, 0.0, 0.0]}},
    )


def test_healthy_cap_passes():
    form = healthy_cap()
    for check in (check_hose_bore_ok, check_spout_drop_path_ok,
                  check_cap_water_path_visible):
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_loose_socket_grip_rejected():
    form = healthy_cap()
    form.bores[0] = cap_socket(d=TUBE_OD + 1.5)
    assert check_hose_bore_ok(form).status is Status.FAIL


def test_through_socket_no_stop_rejected():
    """VF-9.2 core mutation: a socket open at the bottom has NO stop — the
    tube can be pushed clean through the cap."""
    form = healthy_cap()
    form.bores[0] = cap_socket(span=(CHAMBER_TOP, 22.0), overshoot=(1.0, 1.0))
    finding = check_hose_bore_ok(form)
    assert finding.status is Status.FAIL
    assert "pushed clean through" in finding.message


def test_wide_orifice_rejected():
    """An orifice as wide as the tube leaves no stop shoulder."""
    form = healthy_cap()
    form.bores[1] = cap_orifice(d=TUBE_OD - 1.0)
    finding = check_hose_bore_ok(form)
    assert finding.status is Status.FAIL
    assert "stop" in finding.message


def test_offset_orifice_rejected():
    form = healthy_cap()
    form.bores[1] = cap_orifice(center=(3.0, Y_SOCK, 0.0))
    finding = check_hose_bore_ok(form)
    assert finding.status is Status.FAIL
    assert "coaxial" in finding.message


def test_interrupted_orifice_rejected():
    """An orifice that stops short of the socket bottom leaves solid plastic
    between them — the water path is interrupted at the stop."""
    form = healthy_cap()
    form.bores[1] = cap_orifice(span=(CHAMBER_TOP, STOP_Z - 2.0))
    finding = check_hose_bore_ok(form)
    assert finding.status is Status.FAIL
    assert "interrupted" in finding.message


def test_plugged_socket_without_orifice_rejected():
    """A blind socket with NO draining orifice is a hidden sump: hose_bore_ok
    misses its pair AND no_standing_water_ir flags the undrained blind bore."""
    form = make_form(
        "cap", frame=cap_frame(),
        bores=[cap_socket()], ribs=cap_trough(), cutboxes=cap_cuts(),
        regions=[Region("spout_path", RegionRole.TRANSIENT_WATER_PATH,
                        Box3(-5.0, -5.0, -9.6, 5.0, 11.5, 22.5))],
        datums={"spout": {"at": [0.0, TIP_Y, Z_EXIT], "rotate": [0.0, 0.0, 0.0]}},
    )
    assert check_hose_bore_ok(form).status is Status.FAIL
    standing = check_no_standing_water_ir(form)
    assert standing.status is Status.FAIL
    assert "blind bore" in standing.message


def test_missing_floor_rejected():
    form = healthy_cap()
    form.ribs[:] = [r for r in form.ribs if "floor" not in r.name]
    finding = check_spout_drop_path_ok(form)
    assert finding.status is Status.FAIL
    assert "floor" in finding.message


def test_missing_wall_rejected():
    form = healthy_cap()
    form.ribs[:] = [r for r in form.ribs if "wall_w" not in r.name]
    finding = check_spout_drop_path_ok(form)
    assert finding.status is Status.FAIL
    assert "wall" in finding.message


def test_tip_above_body_rejected():
    form = healthy_cap(channel_floor_z_outlet=2.0)
    finding = check_spout_drop_path_ok(form)
    assert finding.status is Status.FAIL
    assert "descend" in finding.message


def test_wide_trough_rejected():
    form = healthy_cap(spout_w=15.5)
    finding = check_spout_drop_path_ok(form)
    assert finding.status is Status.FAIL
    assert "channel" in finding.message


def test_closed_tunnel_no_sky_rejected():
    """VF-9.2 user rule: without the sky opening the chute is a roofed
    horizontal water tunnel — the path is hidden."""
    form = healthy_cap()
    form.cutboxes[:] = [c for c in form.cutboxes if "sky" not in c.name]
    finding = check_cap_water_path_visible(form)
    assert finding.status is Status.FAIL
    assert "hidden" in finding.message


def test_long_covered_chamber_rejected():
    form = healthy_cap()
    form.cutboxes[0] = CutBoxFeature(
        "cap_chamber", Box3(-5.0, 0.4, -9.5, 5.0, 12.5, CHAMBER_TOP))
    finding = check_cap_water_path_visible(form)
    assert finding.status is Status.FAIL
    assert "tunnel" in finding.message


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
