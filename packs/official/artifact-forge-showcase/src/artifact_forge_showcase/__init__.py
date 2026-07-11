"""Artifact Forge — Showcase Pack (free, official).

Entry point for the ``artifact_forge_ng.packs`` group: :func:`register`
declares the pack's check vocabulary, imports the self-registering check
modules and contributes the catalog data (features + archetypes across
the studio / repair / jigs / education domains).
"""
from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"

# The check vocabulary is declared the moment ANY pack module is imported —
# the check modules register probes against these names at import time.
from .declarations import declare as _declare  # noqa: E402

_declare()


def register(ctx) -> None:
    from . import checks  # noqa: F401  (self-registering check modules)

    ctx.add_data_dir(_DATA_DIR)
