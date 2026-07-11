"""Jig form checks — press-fit bushing seats and the registration fence,
measured from the frame keys the jig ops publish (promoted from the
showcase pack)."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_jig import FENCE_DROP_BAND, PRESS_FIT_BAND, SEAT_ENGAGEMENT_K, SEAT_WALL_MIN

_finding = make_finding


def check_bushing_fit_ok(form: PartForm) -> Finding:
    """Every bushing ROW must press in and stay: interference inside the
    band, real engagement depth, and plastic wall left inside the
    outline. Rows are discovered by their namespaced frame keys."""
    check = "form.bushing_fit_ok"
    f = form.frame
    rows = [k[: -len("_bushing_od")] for k in f if k.endswith("_bushing_od")]
    if not rows:
        return _finding(check, True, "n/a — no bushing seats on this part",
                        critical=False)
    lo, hi = PRESS_FIT_BAND
    problems: list[str] = []
    total = 0.0
    worst_press = 0.0
    for name in rows:
        od = f[f"{name}_bushing_od"]
        press = f[f"{name}_press_fit"]
        count = f[f"{name}_bushing_count"]
        spacing = f[f"{name}_spacing"]
        engagement = f[f"{name}_seat_engagement"]
        total += count
        worst_press = max(worst_press, press)
        if not lo <= press <= hi:
            problems.append(
                f"{name}: press fit {press:g} outside [{lo:g}, {hi:g}]")
        need_t = SEAT_ENGAGEMENT_K * od
        if engagement < need_t - 1e-6:
            problems.append(
                f"{name}: plate {engagement:g} thinner than {need_t:g} "
                f"({SEAT_ENGAGEMENT_K:g}x bushing OD) — not enough grip")
        half_row = spacing * (count - 1) / 2.0
        reach = half_row + od / 2.0 + SEAT_WALL_MIN
        u1 = f.get("outline_u1")
        if u1 is not None and reach > u1:
            problems.append(
                f"{name}: outer seat needs {reach:g} half-length, plate "
                f"gives {u1:g} — wall under {SEAT_WALL_MIN:g}")
        web = spacing - od
        if count >= 2 and web < SEAT_WALL_MIN:
            problems.append(
                f"{name}: web between seats {web:g} < {SEAT_WALL_MIN:g}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{total:g} seats across {len(rows)} row(s), press interference "
        f"in band, engagement and walls real",
        measured=worst_press, limit=hi)


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
