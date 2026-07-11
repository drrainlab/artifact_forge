"""Thread form checks — spec/turns/fit measured from the namespaced
frame keys the thread ops publish."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_thread import THREAD_FIT_BAND, THREAD_MIN_TURNS

_finding = make_finding


def check_thread_spec_ok(form: PartForm) -> Finding:
    """Every declared thread must carry enough turns at a printable fit
    compensation — rows discovered by their namespaced keys."""
    check = "form.thread_spec_ok"
    f = form.frame
    rows = [k[: -len("_thread_major")] for k in f
            if k.endswith("_thread_major")]
    if not rows:
        return _finding(check, True, "n/a — no modeled threads",
                        critical=False)
    problems: list[str] = []
    lo, hi = THREAD_FIT_BAND
    for n in rows:
        if f[f"{n}_thread_turns"] < THREAD_MIN_TURNS - 1e-6:
            problems.append(
                f"{n}: {f[f'{n}_thread_turns']:.1f} turns < "
                f"{THREAD_MIN_TURNS:g}")
        if not lo <= f[f"{n}_thread_fit"] <= hi:
            problems.append(
                f"{n}: fit {f[f'{n}_thread_fit']:g} outside [{lo:g}, {hi:g}]")
    if problems:
        return _finding(check, False, "; ".join(problems))
    kinds = ", ".join(
        f"{n}(Ø{f[f'{n}_thread_major']:g}x{f[f'{n}_thread_pitch']:g}, "
        f"{f[f'{n}_thread_turns']:.1f}t)"
        for n in rows)
    return _finding(check, True, f"threads measured: {kinds}")


register_probe("form.thread_spec_ok")(
    lambda form, ctx: check_thread_spec_ok(form))
