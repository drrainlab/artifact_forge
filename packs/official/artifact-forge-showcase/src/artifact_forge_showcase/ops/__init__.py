"""Showcase recipe ops — importing this package registers every op.
The spare/jig ops were promoted to core (artifact_forge_ng.form
.recipe_ops_spare / .recipe_ops_jig); only ladder remains pack-side."""
from __future__ import annotations

from . import ladder  # noqa: F401
