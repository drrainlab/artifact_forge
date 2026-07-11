"""Example L0/L1 pack — data only."""
from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"


def register(ctx) -> None:
    ctx.add_data_dir(_DATA_DIR)
