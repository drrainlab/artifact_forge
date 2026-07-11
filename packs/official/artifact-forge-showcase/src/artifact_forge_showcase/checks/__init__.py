"""Showcase form checks — importing this package registers every check.
The spare/jig checks were promoted to core (artifact_forge_ng.form
.checks_spare / .checks_jig); only ladder remains pack-side."""
from __future__ import annotations

from . import ladder  # noqa: F401
