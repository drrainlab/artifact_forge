"""Binary STL writer/reader — byte-deterministic by construction.

Own writer (no exporter dependency): a fixed 80-byte header (no
timestamps, no versions), little-endian records via one numpy structured
array. Two identical meshes serialize to identical bytes — the
determinism gate diffs files, not "similar" geometry.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

_HEADER = b"artifact-forge-ng implicit exoskeleton skin (Bio-4M)"
_RECORD = np.dtype(
    [("normal", "<f4", (3,)), ("verts", "<f4", (3, 3)), ("attr", "<u2")]
)


def write_binary_stl(path: str | Path, verts: np.ndarray, faces: np.ndarray) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tri = verts[faces].astype(np.float64)  # (F, 3, 3)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    norm = np.linalg.norm(n, axis=1)
    safe = norm > 1e-12
    n = np.where(safe[:, None], n / np.where(safe, norm, 1.0)[:, None], 0.0)
    rec = np.zeros(len(faces), dtype=_RECORD)
    rec["normal"] = n.astype(np.float32)
    rec["verts"] = tri.astype(np.float32)
    header = _HEADER + b"\x00" * (80 - len(_HEADER))
    path.write_bytes(header + struct.pack("<I", len(faces)) + rec.tobytes())
    return path


def read_binary_stl(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Returns (normals (F, 3), triangles (F, 3, 3)) — the round-trip test's
    other half."""
    raw = Path(path).read_bytes()
    (count,) = struct.unpack_from("<I", raw, 80)
    rec = np.frombuffer(raw, dtype=_RECORD, count=count, offset=84)
    return rec["normal"].copy(), rec["verts"].copy()
