"""Mutation tests for the water rail form checks (tilted flush row canon):
a healthy hand-built rail IR (matching the frame-key contract the
water_rail ops publish) passes everything; each surgically broken variant
fails exactly the check that owns the defect.

The healthy rail is LEVEL: constant-depth channel, lap lip continuing the
floor plane past the outlet face, a shallow FLOORED lip-seat receiver in the
inlet floor (VF-9: closed bottom, no through hole under the water path). Slope
is the mount's job (assembly.row_drains_under_mount)."""

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_water import (
    check_cassette_seat_fit_ok,
    check_cassette_support_span_ok,
    check_drainage_requires_mount,
    check_lap_joint_geometry_ok,
    check_lap_receiver_has_floor,
    check_lap_receiver_residual_volume_ok,
    check_lap_slot_leak_path_controlled,
    check_lightweight_windows_dry_ok,
    check_magnet_pockets_do_not_break_wall,
    check_magnet_pockets_outside_water_zone,
    check_no_secondary_water_channel,
    check_no_standing_water_ir,
    check_profile_seat_dry_ok,
    check_rail_universal_inlet_accepts_cap_and_lap,
    check_tongue_groove_profile_ok,
    check_water_channel_constant_depth_ok,
    check_water_channel_dims_ok,
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

RAIL_CHECKS = (
    check_water_channel_constant_depth_ok,
    check_water_channel_dims_ok,
    check_drainage_requires_mount,
    check_no_standing_water_ir,
    check_lap_joint_geometry_ok,
    check_lap_slot_leak_path_controlled,
    check_lap_receiver_has_floor,
    check_lap_receiver_residual_volume_ok,
    check_rail_universal_inlet_accepts_cap_and_lap,
    check_magnet_pockets_outside_water_zone,
    check_magnet_pockets_do_not_break_wall,
    check_lightweight_windows_dry_ok,
    check_cassette_support_span_ok,
    check_no_secondary_water_channel,
    check_cassette_seat_fit_ok,
    check_tongue_groove_profile_ok,
    check_profile_seat_dry_ok,
)

# -- the healthy flush rail: 248x248x30 body, seat floor 16, channel 16x5 --
HALF = 124.0
SEAT_FLOOR = 16.0
DEPTH = 5.0
FLOOR = SEAT_FLOOR - DEPTH  # 11.0
FACE_GAP = 0.4
LIP_LEN, LIP_T, LIP_W = 4.0, 1.4, 18.0
POCKET_LEN, POCKET_W = 6.0, 18.8
LIP_CLR = 0.3
POCKET_DEPTH = LIP_T + LIP_CLR      # 1.7 — a shallow lip-SEAT
POCKET_FLOOR = FLOOR - POCKET_DEPTH  # 9.3 — solid below, no through hole


def good_channel(**over) -> ChannelCutFeature:
    kw: dict = dict(
        center_x=0.0, y0=HALF, y1=-HALF, z_top=SEAT_FLOOR,
        width=16.0, depth_start=DEPTH, depth_end=DEPTH, bottom_r=1.2,
    )
    kw.update(over)
    return ChannelCutFeature(name="water", **kw)


def good_frame(**over) -> dict:
    f = dict(
        rail_y0=-HALF, rail_y1=HALF,
        channel_w=16.0, channel_top_z=SEAT_FLOOR, channel_slope_deg=0.0,
        channel_floor_z_inlet=FLOOR, channel_floor_z_outlet=FLOOR,
        channel_floor_margin=FLOOR,
        face_gap=FACE_GAP, flush_pitch=248.0 + FACE_GAP,
        lap_lip_len=LIP_LEN, lap_lip_w=LIP_W, lap_lip_t=LIP_T,
        lap_lip_top_z=FLOOR, lap_lip_tip_y=-HALF - LIP_LEN,
        lap_pocket_len=POCKET_LEN, lap_pocket_w=POCKET_W,
        lap_pocket_floor_z=POCKET_FLOOR, lap_pocket_depth=POCKET_DEPTH,
        lap_side_clearance=0.4,
        seat_u0=-110.75, seat_v0=-110.75, seat_u1=110.75, seat_v1=110.75,
        seat_floor_z=SEAT_FLOOR, seat_depth=14.0, seat_clearance=0.75,
        tongue_w=6.0, tongue_h=4.0, tongue_len=3.6,
        groove_w=6.8, groove_depth=4.0, edge_clearance=0.4,
        tongue_cy=0.0, groove_cy=0.0, tongue_z0=4.0, groove_z0=4.0,
        profile_size=20.0, profile_slot_w=20.4,
        profile_slot_clearance=0.2, profile_slot_depth=6.0,
        profile_slot_x=100.0,
        module_pitch=250.0,
        lw_enabled=False, lw_window_count=0, lw_rib=2.0,
        lw_span_max=0.0,
    )
    f.update(over)
    return f


def good_regions() -> list[Region]:
    return [
        Region("water_channel", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-8.0, -HALF, FLOOR - 0.5, 8.0, HALF, SEAT_FLOOR)),
        Region("lap_lip", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-LIP_W / 2.0, -HALF - LIP_LEN - 0.5, FLOOR - LIP_T - 0.5,
                    LIP_W / 2.0, -HALF + 2.0, SEAT_FLOOR)),
        Region("lap_receiver", RegionRole.TRANSIENT_WATER_PATH,
               Box3(-POCKET_W / 2.0, HALF - POCKET_LEN - 0.5, POCKET_FLOOR,
                    POCKET_W / 2.0, HALF + 0.5, SEAT_FLOOR)),
        Region("cassette_seat_walls", RegionRole.INTERFACE_KEEPOUT,
               Box3(-113.0, -113.0, SEAT_FLOOR, 113.0, 113.0, 30.0)),
        Region("dry_zone_back", RegionRole.MOUNTING_SURFACE,
               Box3(14.0, 111.0, 0.0, 120.0, HALF, 30.0)),
    ]


def good_cutboxes() -> list[CutBoxFeature]:
    return [
        CutBoxFeature("body_seat", Box3(-110.75, -110.75, SEAT_FLOOR, 110.75, 110.75, 31.0)),
        CutBoxFeature("body_corridor_out", Box3(-10.0, -124.5, SEAT_FLOOR, 10.0, -110.0, 31.0)),
        CutBoxFeature("body_corridor_in", Box3(-10.0, 110.0, SEAT_FLOOR, 10.0, 124.5, 31.0)),
        CutBoxFeature("lap_in_lap_receiver",
                      Box3(-POCKET_W / 2.0, HALF - POCKET_LEN, POCKET_FLOOR,
                           POCKET_W / 2.0, HALF + 0.5, FLOOR + 0.2)),
        CutBoxFeature("edges_groove", Box3(-124.0, -3.4, 4.0, -120.0, 3.4, 8.0)),
        CutBoxFeature("body_profile_slot_e", Box3(89.8, -HALF, 0.0, 110.2, HALF, 6.0)),
        CutBoxFeature("body_profile_slot_w", Box3(-110.2, -HALF, 0.0, -89.8, HALF, 6.0)),
    ]


def good_ribs() -> list[RibFeature]:
    return [
        RibFeature("edges_tongue", Box3(124.0, -3.0, 4.0, 127.6, 3.0, 8.0)),
        RibFeature("lap_out_lap_lip",
                   Box3(-LIP_W / 2.0, -HALF - LIP_LEN, FLOOR - LIP_T,
                        LIP_W / 2.0, -HALF + 0.6, FLOOR)),
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
        ribs=good_ribs() if ribs is None else ribs,
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


def test_drainage_note_is_info_not_warn():
    """PASS-with-note, grade-neutral: the message says INFO and the finding
    is not critical."""
    finding = check_drainage_requires_mount(make_rail())
    assert finding.status is Status.PASS
    assert not finding.critical
    assert "INFO" in finding.message
    assert "mount" in finding.message


# -- constant depth: any slope in the RAIL is now the defect -----------------


def test_sloped_channel_rejected():
    form = make_rail(
        channels=[good_channel(depth_end=DEPTH + 5.41)],
        frame=good_frame(channel_slope_deg=1.25,
                         channel_floor_z_outlet=FLOOR - 5.41),
    )
    fails = failing(form)
    assert "check_water_channel_constant_depth_ok" in fails
    assert "check_drainage_requires_mount" in fails


def test_reversed_depth_rejected():
    form = make_rail(channels=[good_channel(depth_start=DEPTH + 2.0)])
    assert "check_water_channel_constant_depth_ok" in failing(form)


def test_nonzero_declared_slope_rejected():
    form = make_rail(frame=good_frame(channel_slope_deg=1.25))
    assert failing(form) == {"check_water_channel_constant_depth_ok"}


def test_depth_out_of_band_rejected():
    form = make_rail(channels=[good_channel(depth_start=10.0, depth_end=10.0)])
    assert "check_water_channel_constant_depth_ok" in failing(form)


def test_channel_without_exit_rejected():
    form = make_rail(channels=[good_channel(y1=-100.0)])
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


# -- lap-flow handover geometry ------------------------------------------------


def test_missing_lip_rejected():
    ribs = [r for r in good_ribs() if "lap_lip" not in r.name]
    form = make_rail(ribs=ribs)
    assert "check_lap_joint_geometry_ok" in failing(form)


def test_dam_lip_rejected():
    """A lip whose top rides ABOVE the floor plane is a dam — at 1.5 deg a
    1.4 head backs up a ~53 mm pool. The check kills it at the IR."""
    ribs = [good_ribs()[0], RibFeature(
        "lap_out_lap_lip",
        Box3(-LIP_W / 2.0, -HALF - LIP_LEN, FLOOR, LIP_W / 2.0, -HALF + 0.6,
             FLOOR + LIP_T))]
    form = make_rail(ribs=ribs)
    assert "check_lap_joint_geometry_ok" in failing(form)


def test_through_receiver_rejected():
    """VF-9 inversion: a through open-bottom receiver (z0=-1) is now the defect
    — water leaks straight down at the seam. It fails the lap geometry, the
    leak-path control AND the has-floor guard."""
    cuts = [c for c in good_cutboxes() if "lap_receiver" not in c.name] + [
        CutBoxFeature("lap_in_lap_receiver",
                      Box3(-POCKET_W / 2.0, HALF - POCKET_LEN, -1.0,
                           POCKET_W / 2.0, HALF + 0.5, FLOOR + 0.2)),
    ]
    form = make_rail(cutboxes=cuts)
    fails = failing(form)
    assert "check_lap_joint_geometry_ok" in fails
    assert "check_lap_slot_leak_path_controlled" in fails
    assert "check_lap_receiver_has_floor" in fails


def test_deep_sump_receiver_rejected():
    """A FLOORED but too-deep receiver is a hidden reservoir, not a lip-seat:
    it passes has-floor but fails the residual-volume guard AND the
    standing-water guard (depth > the shallow-seat exemption)."""
    deep_floor = 2.0
    cuts = [c for c in good_cutboxes() if "lap_receiver" not in c.name] + [
        CutBoxFeature("lap_in_lap_receiver",
                      Box3(-POCKET_W / 2.0, HALF - POCKET_LEN, deep_floor,
                           POCKET_W / 2.0, HALF + 0.5, FLOOR + 0.2)),
    ]
    form = make_rail(
        cutboxes=cuts,
        frame=good_frame(lap_pocket_floor_z=deep_floor,
                         lap_pocket_depth=FLOOR - deep_floor),  # 9.0 mm deep
    )
    fails = failing(form)
    assert "check_lap_receiver_has_floor" not in fails   # it IS floored...
    assert "check_lap_receiver_residual_volume_ok" in fails   # ...but a reservoir
    assert "check_no_standing_water_ir" in fails


def test_missing_receiver_rejected():
    cuts = [c for c in good_cutboxes() if "lap_receiver" not in c.name]
    form = make_rail(cutboxes=cuts)
    fails = failing(form)
    assert "check_lap_joint_geometry_ok" in fails
    assert "check_lap_slot_leak_path_controlled" in fails


def test_lip_protrusion_out_of_band_rejected():
    form = make_rail(frame=good_frame(lap_lip_len=8.0))
    assert "check_lap_joint_geometry_ok" in failing(form)


def test_slot_out_of_band_rejected():
    # pocket 12 with lip 4 leaves an 8.4 slot — far beyond the 0.5..2.5 seam
    form = make_rail(frame=good_frame(lap_pocket_len=12.0))
    assert "check_lap_joint_geometry_ok" in failing(form)


def test_side_clearance_out_of_band_rejected():
    form = make_rail(frame=good_frame(lap_pocket_w=LIP_W + 2.0))
    assert "check_lap_joint_geometry_ok" in failing(form)


def test_leak_path_near_profile_rejected():
    """Profile slots creeping toward the centerline put aluminum under the
    seam slot — the leak path is no longer controlled."""
    form = make_rail(frame=good_frame(profile_slot_x=30.0))
    assert "check_lap_slot_leak_path_controlled" in failing(form)


# -- magnets: sealed dry pockets, alignment only -------------------------------


def _magnet(name: str, x: float, *, through: bool = False) -> BoreFeature:
    span = (HALF - 2.4, HALF)
    return BoreFeature(name, axis="Y", center=(x, 0.0, 8.0), d=6.4,
                       span=span, overshoot=(1.0, 1.0) if through else (0.0, 1.0))


def test_magnets_absent_is_green():
    form = make_rail()
    assert check_magnet_pockets_outside_water_zone(form).status is Status.PASS
    assert check_magnet_pockets_do_not_break_wall(form).status is Status.PASS


def test_magnet_in_wet_zone_rejected():
    form = make_rail(bores=[_magnet("magnets_pocket_in_c", 0.0)],
                     frame=good_frame(magnet_count=1, magnet_x_offset=0.0,
                                      magnet_pocket_d=6.4))
    assert "check_magnet_pockets_outside_water_zone" in failing(form)


def test_through_magnet_pocket_rejected():
    form = make_rail(bores=[_magnet("magnets_pocket_in_e", 60.0, through=True)],
                     frame=good_frame(magnet_count=1, magnet_x_offset=60.0,
                                      magnet_pocket_d=6.4))
    assert "check_magnet_pockets_do_not_break_wall" in failing(form)


def test_healthy_magnets_pass():
    form = make_rail(
        bores=[_magnet("magnets_pocket_in_e", 60.0),
               _magnet("magnets_pocket_in_w", -60.0)],
        frame=good_frame(magnet_count=2, magnet_x_offset=60.0,
                         magnet_pocket_d=6.4),
    )
    assert "check_magnet_pockets_outside_water_zone" not in failing(form)
    assert "check_magnet_pockets_do_not_break_wall" not in failing(form)


# -- lightweight dry shell ------------------------------------------------------


def _window(name: str, box: Box3) -> CutBoxFeature:
    return CutBoxFeature(name, box)


def test_lightweight_off_is_green():
    assert check_lightweight_windows_dry_ok(make_rail()).status is Status.PASS


def test_healthy_windows_pass():
    cuts = good_cutboxes() + [
        _window("body_lwin_e00", Box3(13.0, -100.0, -1.0, 49.0, -60.0, 16.5)),
        _window("body_lwin_w00", Box3(-49.0, -100.0, -1.0, -13.0, -60.0, 16.5)),
    ]
    form = make_rail(cutboxes=cuts,
                     frame=good_frame(lw_enabled=True, lw_window_count=2,
                                      lw_span_max=40.0))
    fails = failing(form)
    assert "check_lightweight_windows_dry_ok" not in fails
    assert "check_cassette_support_span_ok" not in fails


def test_window_into_channel_band_rejected():
    cuts = good_cutboxes() + [
        _window("body_lwin_e00", Box3(6.0, -100.0, -1.0, 49.0, -60.0, 16.5)),
    ]
    form = make_rail(cutboxes=cuts,
                     frame=good_frame(lw_enabled=True, lw_window_count=1,
                                      lw_span_max=43.0))
    assert "check_lightweight_windows_dry_ok" in failing(form)


def test_blind_window_rejected():
    cuts = good_cutboxes() + [
        _window("body_lwin_e00", Box3(13.0, -100.0, 2.0, 49.0, -60.0, 16.5)),
    ]
    form = make_rail(cutboxes=cuts,
                     frame=good_frame(lw_enabled=True, lw_window_count=1,
                                      lw_span_max=40.0))
    assert "check_lightweight_windows_dry_ok" in failing(form)


def test_flat_ceiling_pocket_rejected():
    """The pre-4.1 geometry: a blind pocket roofed 2.4 under the seat floor
    — a 36mm bridge on FDM. The through rule kills it at the IR."""
    cuts = good_cutboxes() + [
        _window("body_lwin_e00", Box3(13.0, -100.0, -1.0, 49.0, -60.0, 13.6)),
    ]
    form = make_rail(cutboxes=cuts,
                     frame=good_frame(lw_enabled=True, lw_window_count=1,
                                      lw_span_max=40.0))
    fails = failing(form)
    assert "check_lightweight_windows_dry_ok" in fails


def test_window_in_profile_band_rejected():
    cuts = good_cutboxes() + [
        _window("body_lwin_e00", Box3(60.0, -100.0, -1.0, 92.0, -60.0, 16.5)),
    ]
    form = make_rail(cutboxes=cuts,
                     frame=good_frame(lw_enabled=True, lw_window_count=1,
                                      lw_span_max=40.0))
    assert "check_lightweight_windows_dry_ok" in failing(form)


def test_window_poking_from_under_cassette_rejected():
    """A through opening reaching past the seat footprint minus margin
    would peek out from under the cassette AND gnaw the seat wall base."""
    cuts = good_cutboxes() + [
        _window("body_lwin_e00", Box3(13.0, -100.0, -1.0, 49.0, -108.0 + 216.0, 16.5)),
    ]
    form = make_rail(cutboxes=cuts,
                     frame=good_frame(lw_enabled=True, lw_window_count=1,
                                      lw_span_max=40.0))
    assert "check_cassette_support_span_ok" in failing(form)


def test_oversized_span_rejected():
    cuts = good_cutboxes() + [
        _window("body_lwin_e00", Box3(13.0, -100.0, -1.0, 73.0, -40.0, 16.5)),
    ]
    form = make_rail(cutboxes=cuts,
                     frame=good_frame(lw_enabled=True, lw_window_count=1,
                                      lw_span_max=60.0))
    assert "check_cassette_support_span_ok" in failing(form)


def test_merged_windows_rejected():
    """Two openings with no rib between them — the support grid is gone."""
    cuts = good_cutboxes() + [
        _window("body_lwin_e00", Box3(13.0, -100.0, -1.0, 49.0, -60.0, 16.5)),
        _window("body_lwin_e01", Box3(13.0, -60.5, -1.0, 49.0, -20.0, 16.5)),
    ]
    form = make_rail(cutboxes=cuts,
                     frame=good_frame(lw_enabled=True, lw_window_count=2,
                                      lw_span_max=40.0))
    assert "check_cassette_support_span_ok" in failing(form)


def test_lightweight_off_support_is_na():
    assert check_cassette_support_span_ok(make_rail()).status is Status.PASS


# -- the untouched neighbours ---------------------------------------------------


def test_second_channel_rejected():
    form = make_rail(channels=[good_channel(), good_channel(center_x=40.0)])
    assert failing(form) == {"check_no_secondary_water_channel"}


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
    # a centerline profile slot reaching up into the channel floor plane is wet
    cuts = [c for c in good_cutboxes() if "profile" not in c.name] + [
        CutBoxFeature("body_profile_slot_e", Box3(-10.2, -HALF, 0.0, 10.2, HALF, 12.0)),
    ]
    form = make_rail(cutboxes=cuts)
    assert "check_profile_seat_dry_ok" in failing(form)
