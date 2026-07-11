"""Jig-domain form checks — press-fit bushing seats and the registration
fence, measured from the frame keys the jig ops publish."""
from __future__ import annotations

from artifact_forge_ng.core.findings import Finding
from artifact_forge_ng.form.checks_common import make_finding
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.validators.probes import register_probe

from ..ops.jig import FENCE_DROP_BAND, PRESS_FIT_BAND, SEAT_ENGAGEMENT_K, SEAT_WALL_MIN

_finding = make_finding


def check_bushing_fit_ok(form: PartForm) -> Finding:
    """The steel bushing must press in and stay: interference inside the
    band, real engagement depth, and plastic wall left inside the outline."""
    check = "form.bushing_fit_ok"
    f = form.frame
    if "bushing_od" not in f:
        return _finding(check, True, "n/a — no bushing seats on this part",
                        critical=False)
    lo, hi = PRESS_FIT_BAND
    problems: list[str] = []
    press = f["bushing_press_fit"]
    if not lo <= press <= hi:
        problems.append(f"press fit {press:g} outside [{lo:g}, {hi:g}]")
    need_t = SEAT_ENGAGEMENT_K * f["bushing_od"]
    if f["seat_engagement"] < need_t - 1e-6:
        problems.append(
            f"plate {f['seat_engagement']:g} thinner than {need_t:g} "
            f"({SEAT_ENGAGEMENT_K:g}x bushing OD) — not enough grip")
    half_row = f["bushing_spacing"] * (f["bushing_count"] - 1) / 2.0
    reach = half_row + f["bushing_od"] / 2.0 + SEAT_WALL_MIN
    u1 = f.get("outline_u1")
    if u1 is not None and reach > u1:
        problems.append(
            f"outer seat needs {reach:g} half-length, plate gives {u1:g} — "
            f"wall under {SEAT_WALL_MIN:g}")
    web = f["bushing_spacing"] - f["bushing_od"]
    if f["bushing_count"] >= 2 and web < SEAT_WALL_MIN:
        problems.append(
            f"web between seats {web:g} < {SEAT_WALL_MIN:g}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{f['bushing_count']:g} seats at Ø{f['bushing_seat_d']:g} "
        f"(OD {f['bushing_od']:g} - {press:g} press), engagement "
        f"{f['seat_engagement']:g}",
        measured=press, limit=hi)


def check_stop_registration_ok(form: PartForm) -> Finding:
    """The fence must span the full plate edge and reach far enough below
    the plate to actually hook the workpiece."""
    check = "form.stop_registration_ok"
    f = form.frame
    if "fence_len" not in f:
        return _finding(check, True, "n/a — no stop fence on this part",
                        critical=False)
    lo, hi = FENCE_DROP_BAND
    problems: list[str] = []
    if f["fence_len"] < f["fence_plate_len"] - 1e-6:
        problems.append("fence shorter than the plate edge")
    if not lo <= f["fence_drop"] <= hi:
        problems.append(
            f"fence drop {f['fence_drop']:g} outside [{lo:g}, {hi:g}]")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"fence spans the full {f['fence_len']:g} edge, hooks "
        f"{f['fence_drop']:g} below the plate",
        measured=f["fence_drop"], limit=hi)


register_probe("form.bushing_fit_ok")(
    lambda form, ctx: check_bushing_fit_ok(form))
register_probe("form.stop_registration_ok")(
    lambda form, ctx: check_stop_registration_ok(form))
