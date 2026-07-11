"""Fit-ladder check — PASS / FAIL / n-a branches; the check measures the
emitted bores, so the tests tamper with the bores, not the frame."""
from __future__ import annotations

from dataclasses import replace

import pytest

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState

from artifact_forge_showcase.checks.ladder import check_ladder_steps_ok


def _ladder(**over) -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 140.0, "w": 24.0, "t": 5.0, "corner_r": 4.0}, "plate")
    p = {"pin_d": 6.0, "clearance_start": 0.05, "clearance_step": 0.05,
         "count": 8, "spacing": 12.0, "cy": 0.0, "pin_len": 12.0}
    p.update(over)
    RECIPE_OPS["tolerance_ladder"].apply(st, p, "ladder")
    return st


def test_healthy_ladder_passes():
    f = check_ladder_steps_ok(_ladder())
    assert f.status is Status.PASS
    assert "8 steps" in f.message


def test_too_few_steps_refused_by_op():
    with pytest.raises(RecipeError, match="teaches nothing"):
        _ladder(count=3)


def test_overwide_ladder_refused_by_op():
    with pytest.raises(RecipeError, match="rattles"):
        _ladder(clearance_step=0.2, count=8)


def test_tampered_bore_breaks_monotonicity():
    st = _ladder()
    idx = next(i for i, b in enumerate(st.bores) if b.name == "ladder_step_3")
    st.bores[idx] = replace(st.bores[idx], d=st.bores[idx].d - 0.2)
    f = check_ladder_steps_ok(st)
    assert f.status is Status.FAIL
    assert "increasing" in f.message or "pitch" in f.message


def test_na_without_ladder():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 80.0, "w": 24.0, "t": 5.0, "corner_r": 4.0}, "plate")
    f = check_ladder_steps_ok(st)
    assert f.status is Status.PASS
    assert "n/a" in f.message
