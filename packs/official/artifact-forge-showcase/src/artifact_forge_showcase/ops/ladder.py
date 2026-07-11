"""Education-domain recipe op — the tolerance ladder: a row of test bores
of monotonically growing clearance around one reference pin printed on
the same plate. Print it, predict which step fits, then measure your
printer's real clearance band by hand. This IS the shared fit-ladder
capability (CAPABILITIES.md §1) later fit-workflow waves consume."""
from __future__ import annotations

from typing import Any

from artifact_forge_ng.form.part import BoreFeature, PinFeature
from artifact_forge_ng.form.recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register

LADDER_STEP_BAND = (0.05, 0.6)   # printable clearance steps, mm
LADDER_MIN_COUNT = 4


def _tolerance_ladder(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """N through bores along a line: bore k = pin_d + start + k*step, plus
    the reference pin welded at the row's far end. Step marking is a bore
    count for now — engraved labels wait for the text op."""
    state.require_base("tolerance_ladder")
    pin_d, start, step = p["pin_d"], p["clearance_start"], p["clearance_step"]
    count = int(p["count"])
    spacing, cy = p["spacing"], p["cy"]
    lo, hi = LADDER_STEP_BAND
    if count < LADDER_MIN_COUNT:
        raise RecipeError(f"a ladder under {LADDER_MIN_COUNT} steps teaches nothing")
    if step < lo:
        raise RecipeError(f"clearance step {step:g} below printable {lo:g}")
    top = start + (count - 1) * step
    if top > hi:
        raise RecipeError(
            f"last step clearance {top:g} past {hi:g} — everything rattles")
    t = state.width
    name = op_id or "ladder"
    x0 = -spacing * (count - 1) / 2.0
    for i in range(count):
        state.bores.append(BoreFeature(
            name=f"{name}_step_{i}", axis="Z",
            d=pin_d + start + i * step,
            center=(x0 + i * spacing, cy, 0.0), span=(0.0, t),
            overshoot=(1.0, 1.0)))
    pin_x = x0 + count * spacing
    state.pins.append(PinFeature(
        name=f"{name}_pin", at=(pin_x, cy), d=pin_d,
        z0=t - 0.5, length=p["pin_len"] + 0.5))
    state.frame.update(
        ladder_pin_d=pin_d,
        ladder_start=start,
        ladder_step=step,
        ladder_count=float(count),
        ladder_spacing=spacing,
        ladder_pin_len=p["pin_len"],
    )


_register(RecipeOpDecl(
    name="tolerance_ladder",
    kind="feature",
    params={
        "pin_d": ("length", 6.0), "clearance_start": ("length", 0.05),
        "clearance_step": ("length", 0.05), "count": ("count", 8),
        "spacing": ("length", 12.0), "cy": ("length", 0.0),
        "pin_len": ("length", 12.0),
    },
    validators=("form.ladder_steps_ok", "topology.bores_open",
                "topology.pins_present"),
    apply=_tolerance_ladder,
    description="row of test bores of monotonically growing clearance "
                "around one reference pin printed on the same plate",
))
