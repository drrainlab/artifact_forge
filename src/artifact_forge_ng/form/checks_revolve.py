"""IR check for revolve profiles — the half-section must stay strictly on
the +u side of the revolve axis, at least ``axis_clear_r`` away (the cup's
cable-exit radius). A profile touching u=0 would revolve into a degenerate
or self-intersecting solid. Self-registers on import.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm

_TOL = 1e-6


def check_revolve_profile_clear_of_axis(form: PartForm) -> Finding:
    clear_r = form.frame.get("axis_clear_r", 0.0)
    lo, _hi = form.section.outer.bbox()
    min_u = lo.u
    ok = clear_r > _TOL and min_u >= clear_r - 1e-4
    if clear_r <= _TOL:
        message = "frame declares no positive axis_clear_r"
    else:
        message = f"profile min u {min_u:.3f} vs required clearance {clear_r:.3f}"
    return Finding(
        check="form.revolve_profile_clear_of_axis",
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=not ok,
        measured=min_u,
        limit=clear_r,
        unit="mm",
    )


register_probe("form.revolve_profile_clear_of_axis")(
    lambda form, ctx: check_revolve_profile_clear_of_axis(form)
)
