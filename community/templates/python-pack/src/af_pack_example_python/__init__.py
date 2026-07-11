"""Example L2 pack — data + checks."""
from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"
_PACK_YAML = Path(__file__).resolve().parents[2] / "pack.yaml"

# Declare the check vocabulary the moment any pack module is imported.
from .declarations import declare as _declare  # noqa: E402

_declare()


def register(ctx) -> None:
    from . import checks  # noqa: F401  (self-registering)

    ctx.add_pack_manifest(_PACK_YAML)
    ctx.add_data_dir(_DATA_DIR)
