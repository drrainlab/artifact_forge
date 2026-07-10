"""Vertical Farm water checks (shim).

Checks live in the checks_water_* family modules; importing this module
registers all of them (side effect) and every check keeps its import path.
"""
from __future__ import annotations

from .checks_water_common import (  # noqa: F401
    _boxes_overlap, _wet_regions, _blind_bore_drained_below,
    _pocket_drained_by_through_bore,
    MOUNT_SLOPE_BAND, CONST_DEPTH_TOL, CHANNEL_D_BAND, CHANNEL_W_BAND, BOTTOM_R_BAND,
    FLOOR_MARGIN_MIN, SEAT_CLEARANCE_BAND, TG_SIDE_CLEARANCE_BAND, TG_BOTTOM_MARGIN, LAP_LIP_LEN_BAND,
    LAP_LIP_T_BAND, LAP_SIDE_CLEAR_BAND, LAP_SLOT_BAND, FACE_GAP_BAND, LAP_LATERAL_CLEAR_MIN,
    MAGNET_WET_WALL_MIN, MAGNET_FIT_BAND, LW_RIB_MIN, CASSETTE_COVER, CASSETTE_SPAN_MAX,
)
from .checks_water_channel import (  # noqa: F401
    check_basket_not_transverse_flow_barrier,
    check_collector_sump_is_lowest_point,
    check_dock_pockets_dry,
    check_drainage_requires_mount,
    check_lap_joint_geometry_ok,
    check_lap_receiver_has_floor,
    check_lap_receiver_residual_volume_ok,
    check_lap_slot_leak_path_controlled,
    check_lightweight_windows_dry_ok,
    check_magnet_pockets_do_not_break_wall,
    check_magnet_pockets_outside_water_zone,
    check_no_standing_water_before_screen,
    check_no_standing_water_ir,
    check_rail_universal_inlet_accepts_cap_and_lap,
    check_screen_debris_capacity_ok,
    check_screen_open_area_ratio_ok,
    check_tray_floor_slopes_to_sump,
    check_water_channel_constant_depth_ok,
    check_water_channel_dims_ok,
)
from .checks_water_cassette import (  # noqa: F401
    check_cassette_seat_fit_ok,
    check_cassette_support_span_ok,
    check_no_secondary_water_channel,
    check_profile_seat_dry_ok,
    check_root_chamber_ok,
    check_tongue_groove_profile_ok,
)
from .checks_water_adapters import (  # noqa: F401
    check_cap_water_path_visible,
    check_collector_structure_sturdy,
    check_collector_tray_drains,
    check_hose_bore_ok,
    check_profile_ref_geometry_ok,
    check_spout_drop_path_ok,
)
from .checks_water_receiver import (  # noqa: F401
    check_collector_drain_bore_supportless,
    check_collector_receiver_matches_final_lap,
    check_receiver_open_top_cleanable,
)
