"""Compiled-solid topology probes (shim).

The probes live in the ``topology_*`` family modules; importing this module
registers all of them (side effect), exactly as before the split. Import
paths are preserved: every probe function and the raw cad-probe helpers
remain importable from here.
"""
from __future__ import annotations

from .topology_common import _finding, box_probe, channel_probe, solid_fraction  # noqa: F401
from .topology_solids import (  # noqa: F401
    single_connected_solid, cavity_open, mouth_opens_sideways,
    asymmetric_lips_geometry, flange_above_cradle, tool_void_open,
    revolve_cavity_open, bay_open, tunnel_open, cutout_present,
    payload_void_open,
)
from .topology_fasteners import (  # noqa: F401
    screw_holes_open, countersinks_present, channel_continuous,
    slots_open, bores_open,
)
from .topology_structure import (  # noqa: F401
    hex_field_present, ribs_present, bar_follows_arc, pins_present,
    arm_reaches_tip, seat_lips_present, pockets_present, rail_present,
    exoskeleton_ribs_materialized, organic_windows_open,
)
from .topology_water import (  # noqa: F401
    water_channel_open, water_channel_floor_solid, contact_window_present,
    fluid_path_open,
)
