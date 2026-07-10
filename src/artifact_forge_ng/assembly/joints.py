"""The joint registry (shim).

Implementation lives in joints_core / joints_mechanical / joints_fluid;
importing this module registers every joint type exactly as before the
split, and every public and test-consumed name keeps its import path.
"""
from __future__ import annotations

from .joints_core import (  # noqa: F401
    IDENTITY_POSE, PILOT_PREFIX, POSITION_TOL, JointDecl, JointError,
    JOINT_TYPES, Pose, compute_pose, rotate_point, _finding,
)
from .joints_mechanical import (  # noqa: F401
    MIN_COMPRESSION_GAP, SNAP_STRAIN_LIMIT, SNAP_STRAIN_WARN,
    _butt_pin_ir, _compression_gap_ir, _lid_seat_ir, _press_fit_ir,
    _screw_joint_ir, _snap_joint_ir,
)
from .joints_fluid import (  # noqa: F401
    _cap_drip_lands_in_channel_safe_floor, _dovetail_ir, _drop_in_screen_ir,
    _fluid_joint_ir, _lap_flow_ir, _profile_perch_ir, _removable_insert_ir,
    _saddle_hang_ir, _tongue_groove_ir,
)
