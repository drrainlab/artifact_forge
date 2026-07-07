"""Mutation tests for the water rail form checks: a healthy hand-built
rail IR (matching the frame-key contract the water_rail ops publish) passes
everything; each surgically broken variant fails exactly the check that
owns the defect."""

import math

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_water import (
    check_cassette_seat_fit_ok,
    check_no_secondary_water_channel,
    check_no_standing_water_ir,
    check_overflow_lip_geometry_ok,
    check_profile_seat_dry_ok,
    check_tongue_groove_profile_ok,
    check_water_channel_dims_ok,
    check_water_channel_slope_ok,
)
from artifact_forge_ng.form.part import (
    BlendDirective,
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

RAIL_CHECKS = (
    check_water_channel_slope_ok,
    check_water_channel_dims_ok,
    check_no_standing_water_ir,
    check_overflow_lip_geometry_ok,
    check_no_secondary_water_channel,
    check_cassette_seat_fit_ok,
    check_tongue_groove_profile_ok,
    check_profile_seat_dry_ok,
)

# -- the healthy rail: 248x248x30 body, seat floor at 16, channel 16 wide --
HALF = 124.0
SEAT_FLOOR = 16.0
DEPTH_IN = 5.0
DROP = 2.0 * HALF * math.tan(math.radians(1.25))
DEPTH_OUT = DEPTH_IN + DROP
LIP_Z = SEAT_FLOOR - DEPTH_OUT
LIP_H = 2.0
AIR_GAP = 1.5


def good_channel(**over) -> ChannelCutFeature:
    kw: dict = dict(
        center_x=0.0, y0=HALF, y1=-HALF, z_top=SEAT_FLOOR,
        width=16.0, depth_start=DEPTH_IN, depth_end=DEPTH_OUT, bottom_r=1.2,
    )
    kw.update(over)
    return ChannelCutFeature(name="water", **kw)


def good_frame(**over) -> dict:
    f = dict(
        rail_y0=-HALF, rail_y1=HALF,
        channel_top_z=SEAT_FLOOR, channel_slope_deg=1.25,
        channel_floor_margin=SEAT_FLOOR - DEPTH_OUT,
        lip_z=LIP_Z, lip_h=LIP_H, air_gap=AIR_GAP, lip_r_assumed=0.4,
        seat_u0=-110.75, seat_v0=-110.75, seat_u1=110.75, seat_v1=110.75,
        seat_floor_z=SEAT_FLOOR, seat_depth=14.0, seat_clearance=0.75,
        tongue_w=6.0, tongue_h=4.0, tongue_len=3.6,
        groove_w=6.8, groove_depth=4.0, edge_clearance=0.4,
        tongue_cy=0.0, groove_cy=0.0, tongue_z0=4.0, groove_z0=4.0,
        profile_size=20.0, profile_slot_w=20.4,
        profile_slot_clearance=0.2, profile_slot_depth=6.0,
        module_pitch=250.0,
    )
    f.update(over)
    return f


def good_regions() -> list[Region]:
    return [
        Region("water_channel", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-8.0, -HALF, LIP_Z - 0.5, 8.0, HALF, SEAT_FLOOR)),
        Region("overflow_lip", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-8.0, -HALF - 1.0, LIP_Z - LIP_H, 8.0, -HALF + 2.0, SEAT_FLOOR)),
        Region("drip_receiver", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-10.0, -HALF - 1.0, -1.0, 10.0, -HALF + AIR_GAP, LIP_Z - LIP_H)),
        Region("cassette_seat_walls", RegionRole.INTERFACE_KEEPOUT,
               Box3(-113.0, -113.0, SEAT_FLOOR, 113.0, 113.0, 30.0)),
    ]


def good_cutboxes() -> list[CutBoxFeature]:
    return [
        CutBoxFeature("body_seat", Box3(-110.75, -110.75, SEAT_FLOOR, 110.75, 110.75, 31.0)),
        CutBoxFeature("body_corridor_out", Box3(-10.0, -124.5, SEAT_FLOOR, 10.0, -110.0, 31.0)),
        CutBoxFeature("body_corridor_in", Box3(-10.0, 110.0, SEAT_FLOOR, 10.0, 124.5, 31.0)),
        CutBoxFeature("lip_relief", Box3(-10.0, -HALF - 1.0, -1.0, 10.0, -HALF + AIR_GAP, LIP_Z - LIP_H)),
        CutBoxFeature("edges_groove", Box3(-124.0, -3.4, 4.0, -120.0, 3.4, 8.0)),
        CutBoxFeature("body_profile_slot_e", Box3(89.8, -HALF, 0.0, 110.2, HALF, 6.0)),
        CutBoxFeature("body_profile_slot_w", Box3(-110.2, -HALF, 0.0, -89.8, HALF, 6.0)),
    ]


def make_rail(channels=None, frame=None, cutboxes=None, regions=None,
              ribs=None, blends=None, bores=None, params=None) -> PartForm:
    c = Pt(0.0, -10.0)
    loop = ProfileLoop([
        ArcSeg(Pt(0, -5), Pt(0, -15), c, ccw=True),
        ArcSeg(Pt(0, -15), Pt(0, -5), c, ccw=True),
    ])
    return PartForm(
        name="rail",
        params={"cassette_l": 220.0, "cassette_w": 220.0, **(params or {})},
        frame=good_frame() if frame is None else frame,
        section=SectionProfile(name="rail", outer=loop),
        width=30.0, style=MOLDED_UTILITY_PART,
        channels=[good_channel()] if channels is None else channels,
        cutboxes=good_cutboxes() if cutboxes is None else cutboxes,
        regions=good_regions() if regions is None else regions,
        ribs=[RibFeature("edges_tongue", Box3(124.0, -3.0, 4.0, 127.6, 3.0, 8.0))]
        if ribs is None else ribs,
        blends=blends or [],
        bores=bores or [],
    )


def failing(form: PartForm) -> set:
    return {c.__name__ for c in RAIL_CHECKS if c(form).status is Status.FAIL}


def test_healthy_rail_passes_everything():
    form = make_rail()
    for check in RAIL_CHECKS:
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_zero_slope_rejected():
    form = make_rail(channels=[good_channel(depth_end=DEPTH_IN + 0.001)],
                     frame=good_frame(channel_slope_deg=0.0))
    assert failing(form) == {"check_water_channel_slope_ok"}


def test_reversed_slope_rejected():
    form = make_rail(
        channels=[good_channel(depth_start=DEPTH_OUT, depth_end=DEPTH_IN)],
        frame=good_frame(channel_floor_margin=SEAT_FLOOR - DEPTH_OUT),
    )
    assert "check_water_channel_slope_ok" in failing(form)


def test_channel_without_exit_rejected():
    form = make_rail(channels=[good_channel(y1=-100.0, depth_end=DEPTH_IN + 200.0 * math.tan(math.radians(1.25)))],
                     frame=good_frame(channel_slope_deg=1.25))
    assert "check_water_channel_dims_ok" in failing(form)


def test_wide_channel_rejected():
    form = make_rail(channels=[good_channel(width=25.0)])
    assert failing(form) == {"check_water_channel_dims_ok"}


def test_thin_floor_rejected():
    form = make_rail(frame=good_frame(channel_floor_margin=1.0))
    assert failing(form) == {"check_water_channel_dims_ok"}


def test_blind_bore_in_wet_path_rejected():
    sump = BoreFeature("sump", axis="Z", center=(0.0, 0.0, SEAT_FLOOR),
                       d=8.0, span=(3.0, SEAT_FLOOR), overshoot=(0.0, 1.0))
    form = make_rail(bores=[sump])
    assert failing(form) == {"check_no_standing_water_ir"}


def test_small_air_gap_rejected():
    form = make_rail(frame=good_frame(air_gap=0.8))
    assert failing(form) == {"check_overflow_lip_geometry_ok"}


def test_rounded_lip_rejected():
    blend = BlendDirective(
        zone=Box3(-8.0, -HALF - 1.0, LIP_Z - LIP_H, 8.0, -HALF + 2.0, SEAT_FLOOR),
        radius=1.5,
    )
    form = make_rail(blends=[blend])
    assert failing(form) == {"check_overflow_lip_geometry_ok"}


def test_missing_relief_rejected():
    cuts = [c for c in good_cutboxes() if c.name != "lip_relief"]
    form = make_rail(cutboxes=cuts)
    assert failing(form) == {"check_overflow_lip_geometry_ok"}


def test_second_channel_rejected():
    form = make_rail(channels=[good_channel(), good_channel(center_x=40.0)])
    assert failing(form) == {"check_no_secondary_water_channel"}


def test_trough_in_receiver_rejected():
    cuts = good_cutboxes() + [
        CutBoxFeature("second_trough", Box3(-8.0, -HALF - 0.5, 1.0, 8.0, -HALF + 1.0, 3.0)),
    ]
    form = make_rail(cutboxes=cuts)
    assert "check_no_secondary_water_channel" in failing(form)


def test_loose_seat_clearance_rejected():
    form = make_rail(frame=good_frame(
        seat_clearance=2.0, seat_u0=-112.0, seat_u1=112.0,
        seat_v0=-112.0, seat_v1=112.0,
    ))
    assert failing(form) == {"check_cassette_seat_fit_ok"}


def test_seat_floor_off_channel_plane_rejected():
    form = make_rail(frame=good_frame(seat_floor_z=20.0))
    assert failing(form) == {"check_cassette_seat_fit_ok"}


def test_tongue_groove_clearance_band():
    form = make_rail(frame=good_frame(groove_w=7.4))
    assert failing(form) == {"check_tongue_groove_profile_ok"}
    form = make_rail(frame=good_frame(groove_w=6.4, edge_clearance=0.2))
    assert failing(form) == {"check_tongue_groove_profile_ok"}


def test_bottoming_tongue_rejected():
    form = make_rail(frame=good_frame(tongue_len=3.9))
    assert failing(form) == {"check_tongue_groove_profile_ok"}


def test_wet_profile_slot_rejected():
    cuts = [c for c in good_cutboxes() if "profile" not in c.name] + [
        CutBoxFeature("body_profile_slot_e", Box3(-10.2, -HALF, 0.0, 10.2, HALF, 6.0)),
    ]
    form = make_rail(cutboxes=cuts)
    assert failing(form) == {"check_profile_seat_dry_ok"}
