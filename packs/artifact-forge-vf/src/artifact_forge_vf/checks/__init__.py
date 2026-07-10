"""VF form checks — importing this package registers every check."""
from __future__ import annotations

from .common import (  # noqa: F401
    _boxes_overlap, _wet_regions, _blind_bore_drained_below,
    _pocket_drained_by_through_bore,
)
from .channel import (  # noqa: F401
    check_water_channel_constant_depth_ok,
    check_water_channel_dims_ok,
    check_no_standing_water_ir,
    check_lap_joint_geometry_ok,
    check_lap_slot_leak_path_controlled,
    check_lap_receiver_has_floor,
    check_lap_receiver_residual_volume_ok,
    check_rail_universal_inlet_accepts_cap_and_lap,
    check_drainage_requires_mount,
    check_magnet_pockets_outside_water_zone,
    check_magnet_pockets_do_not_break_wall,
    check_dock_pockets_dry,
    check_screen_open_area_ratio_ok,
    check_screen_debris_capacity_ok,
    check_collector_sump_is_lowest_point,
    check_tray_floor_slopes_to_sump,
    check_basket_not_transverse_flow_barrier,
    check_no_standing_water_before_screen,
    check_lightweight_windows_dry_ok,
)
from .cassette import (  # noqa: F401
    check_cassette_support_span_ok,
    check_no_secondary_water_channel,
    check_cassette_seat_fit_ok,
    check_tongue_groove_profile_ok,
    check_profile_seat_dry_ok,
    check_root_chamber_ok,
)
from .adapters import (  # noqa: F401
    check_hose_bore_ok,
    check_spout_drop_path_ok,
    check_cap_water_path_visible,
    check_collector_tray_drains,
    check_collector_structure_sturdy,
    check_profile_ref_geometry_ok,
)
from .receiver import (  # noqa: F401
    check_collector_receiver_matches_final_lap,
    check_receiver_open_top_cleanable,
    check_collector_drain_bore_supportless,
)
from .substrate_cassette import (  # noqa: F401
    check_mesh_floor_orthogonal_ok,
    check_cassette_no_reservoir,
    check_contact_window_geometry_ok,
    check_snap_pockets_cleanable,
    check_lift_access_ok,
    check_substrate_retained_under_mount,
)
