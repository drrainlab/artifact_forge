"""IR check for tie tunnels — the measured tunnel section (exact, from
tagged vertical walls and roof) must fit the declared tie plus clearances.
Self-registers.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm
from .section import LineSeg


def check_tunnel_fits_tie(form: PartForm) -> Finding:
    tie_w = form.params.get("tie_w")
    tie_t = form.params.get("tie_t")
    walls = [
        s for s in form.section.outer.tagged("tunnel") if isinstance(s, LineSeg)
    ]
    roof = [
        s for s in form.section.outer.tagged("tunnel_roof") if isinstance(s, LineSeg)
    ]
    ok = False
    message = "tunnel walls/roof missing from the profile"
    if tie_w is not None and tie_t is not None and len(walls) >= 2 and roof:
        us = sorted(s.a.u for s in walls)
        measured_w = us[-1] - us[0]
        measured_h = min(min(s.a.v, s.b.v) for s in roof)
        ok = measured_w >= tie_w - 1e-6 and measured_h >= tie_t + 0.2
        message = (
            f"tunnel {measured_w:.2f} x {measured_h:.2f} vs tie "
            f"{tie_w:.2f} x {tie_t:.2f} (+clearances)"
        )
    return Finding(
        check="form.tunnel_fits_tie",
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=not ok,
    )


register_probe("form.tunnel_fits_tie")(lambda form, ctx: check_tunnel_fits_tie(form))
