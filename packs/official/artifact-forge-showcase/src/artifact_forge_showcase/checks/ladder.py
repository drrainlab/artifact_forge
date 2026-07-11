"""Education-domain form check — the shared fit-ladder capability. It
measures the EMITTED bores, never the frame echo: monotonic diameters,
constant pitch, every clearance inside the printable band."""
from __future__ import annotations

from artifact_forge_ng.core.findings import Finding
from artifact_forge_ng.form.checks_common import make_finding
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.validators.probes import register_probe

from ..ops.ladder import LADDER_STEP_BAND

_finding = make_finding


def check_ladder_steps_ok(form: PartForm) -> Finding:
    check = "form.ladder_steps_ok"
    f = form.frame
    if "ladder_pin_d" not in f:
        return _finding(check, True, "n/a — no tolerance ladder on this part",
                        critical=False)
    steps = sorted(
        (b for b in form.bores if "_step_" in b.name),
        key=lambda b: b.center[0])
    if len(steps) < 2:
        return _finding(check, False, "ladder declared but bores missing")
    lo, hi = LADDER_STEP_BAND
    pin_d = f["ladder_pin_d"]
    problems: list[str] = []
    diffs = [b2.d - b1.d for b1, b2 in zip(steps, steps[1:])]
    if any(d <= 0 for d in diffs):
        problems.append("bore diameters not strictly increasing")
    if max(diffs) - min(diffs) > 1e-6:
        problems.append("step pitch is not constant")
    clearances = [b.d - pin_d for b in steps]
    if clearances[0] < lo - 1e-9:
        problems.append(f"first clearance {clearances[0]:g} below {lo:g}")
    if clearances[-1] > hi + 1e-9:
        problems.append(f"last clearance {clearances[-1]:g} above {hi:g}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{len(steps)} steps, clearance {clearances[0]:g}..{clearances[-1]:g} "
        f"in {diffs[0]:g} increments around a Ø{pin_d:g} pin",
        measured=clearances[-1], limit=hi)


register_probe("form.ladder_steps_ok")(
    lambda form, ctx: check_ladder_steps_ok(form))
