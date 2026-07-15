"""Canonical hashing primitives — shared by the evaluation cache and the
build library. Pure stdlib, no project imports (usable from any layer).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    """sha256 of the canonical JSON form: sorted keys, compact separators,
    unicode kept. ``default=str`` coerces non-native values — fine for
    pydantic ``model_dump(mode="json")`` output, lossy for exotic types."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def file_sha256(path: Path) -> tuple[str, int]:
    """Streaming sha256 + size of a file — the integrity fingerprint the
    library manifests carry for every archived artifact."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size
