"""Vertical Farm Pack v1 recipe ops (docs/VERTICAL_FARM_PACK.md) — the
water rail, the substrate cassette and the snap retainer frame, composed
per the builder contract: geometry + semantic regions + frame keys +
mandatory validators.

The frame keys published here ARE the Cassette Interface Standard: the
rail publishes seat_*/channel_*, every cassette publishes cassette_*/
window_* plus the shell keys the snap joint reads, and the assembly joints
(removable_insert, tongue_groove, snap_joint) verify the two halves
against each other in the pose. A future sprout/rockwool cassette that
publishes the same keys mates with the same rail untouched.

Imported at the bottom of recipe_ops.py so the registry stays whole.

Shim: ops live in the recipe_ops_water_* family modules; importing this
module registers all of them in the original order.
"""
from __future__ import annotations

from .recipe_ops_water_common import (  # noqa: F401
    CAP_COVERED_RUN_MAX, CORRIDOR_MARGIN, DRIP_INSET, FALL_ENTRY,
    FLOOR_MARGIN_MIN, ORIFICE_LEN,
)
from . import recipe_ops_water_rail  # noqa: E402,F401
from . import recipe_ops_water_dock  # noqa: E402,F401
from . import recipe_ops_water_cassette  # noqa: E402,F401
from . import recipe_ops_water_retainer  # noqa: E402,F401
from . import recipe_ops_water_adapters  # noqa: E402,F401
