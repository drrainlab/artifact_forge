"""Shared helpers for the ``checks_*`` modules.

Every checks module used to carry its own private ``_finding`` factory with
a slightly different signature; this is the one factory that covers all of
them. Import it under the local convention::

    from .checks_common import make_finding as _finding

``critical`` defaults to True so ``critical and not ok`` reduces to the
common ``not ok`` behaviour; pass ``critical=False`` for advisory checks.
"""
from __future__ import annotations

from ..core.findings import Finding, Level, Status


def make_finding(check: str, ok: bool, message: str, *,
                 measured: float | None = None,
                 limit: float | None = None,
                 suggestion: str = "",
                 critical: bool = True,
                 unit: str = "") -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=critical and not ok,
        measured=measured,
        limit=limit,
        suggestion=suggestion,
        unit=unit,
    )
