"""Recipe-op registry (shim).

Ops live in the recipe_ops_* family modules; importing this module
registers all of them in the original order. Public names keep their
import path.
"""
from __future__ import annotations

from .recipe_ops_core import (  # noqa: F401
    BEARINGS, KEEPOUT_CLEARANCE, PORT_SIZES, RECIPE_OPS,
    RecipeError, RecipeOpDecl, RecipeState, _register,
)
from . import recipe_ops_base  # noqa: E402,F401
from . import recipe_ops_fasteners  # noqa: E402,F401
from . import recipe_ops_mount  # noqa: E402,F401
from . import recipe_ops_wearable  # noqa: E402,F401
from . import recipe_ops_dovetail  # noqa: E402,F401
