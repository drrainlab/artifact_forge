"""VF recipe ops — importing this package registers every op."""
from __future__ import annotations

from .water_common import (  # noqa: F401
    CAP_COVERED_RUN_MAX, CORRIDOR_MARGIN, DRIP_INSET, FALL_ENTRY,
    FLOOR_MARGIN_MIN, ORIFICE_LEN,
)
from . import rail  # noqa: E402,F401
from . import dock  # noqa: E402,F401
from . import cassette  # noqa: E402,F401
from . import retainer  # noqa: E402,F401
from . import adapters  # noqa: E402,F401
