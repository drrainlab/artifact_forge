"""Shared plumbing for the ``topology_*`` probe modules.

Re-exports the raw cad probes so probe modules and tests have one import
point; ``_finding`` is the common Finding factory at TOPOLOGY level.
"""
from __future__ import annotations

from ..cad.probes import box_probe, channel_probe, solid_fraction  # noqa: F401
from ..core.findings import Finding, Level, Status

def _finding(check: str, ok: bool, message: str, measured: float | None = None,
             limit: float | None = None) -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.TOPOLOGY,
        message=message,
        critical=True,
        measured=measured,
        limit=limit,
    )

