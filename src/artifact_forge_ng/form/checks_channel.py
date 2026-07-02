"""IR check for wiring channels — every bore must keep the minimum wall
inside its host cross-section, verified from the frame before CAD.
Self-registers.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm

MIN_CHANNEL_WALL = 2.0


def check_channel_inside_walls(form: PartForm) -> Finding:
    channel_d = form.params.get("channel_d")
    arm_w = form.params.get("arm_w")
    arm_h = form.params.get("arm_h")
    if channel_d is None or arm_w is None or arm_h is None:
        return Finding(
            check="form.channel_inside_walls",
            status=Status.FAIL,
            level=Level.FORM,
            message="channel/arm dimensions missing from params",
            critical=True,
        )
    margin = min(arm_w, arm_h) / 2.0 - channel_d / 2.0
    ok = margin >= MIN_CHANNEL_WALL - 1e-9
    return Finding(
        check="form.channel_inside_walls",
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=(
            f"channel d {channel_d:g} leaves {margin:.1f} mm wall in the "
            f"{arm_w:g}x{arm_h:g} arm (needs >= {MIN_CHANNEL_WALL:g})"
        ),
        critical=not ok,
        measured=margin,
        limit=MIN_CHANNEL_WALL,
        unit="mm",
    )


register_probe("form.channel_inside_walls")(
    lambda form, ctx: check_channel_inside_walls(form)
)
