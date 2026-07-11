"""Jig checks — PASS / FAIL / n-a branches on real op-built forms.
Promoted from the showcase pack together with the ops."""
from __future__ import annotations

import pytest

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_jig import (
    check_bushing_fit_ok,
    check_stop_registration_ok,
)
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState


def _jig(*, plate=(120.0, 40.0, 6.0), bushing_od=8.0, press=0.1,
         count=4, spacing=25.0, cy=-0.0, fence=True, fence_drop=8.0) -> RecipeState:
    st = RecipeState()
    l, w, t = plate
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": l, "w": w, "t": t, "corner_r": 4.0}, "plate")
    RECIPE_OPS["bushing_seat_line"].apply(
        st, {"bushing_od": bushing_od, "press_fit": press, "count": count,
             "spacing": spacing, "cx": 0.0, "cy": cy}, "bushings")
    if fence:
        RECIPE_OPS["stop_fence"].apply(
            st, {"fence_t": 5.0, "fence_drop": fence_drop}, "fence")
    return st


def test_healthy_jig_passes_both():
    st = _jig()
    assert check_bushing_fit_ok(st).status is Status.PASS
    assert check_stop_registration_ok(st).status is Status.PASS


def test_press_fit_out_of_band_refused_by_op():
    with pytest.raises(RecipeError, match="press_fit"):
        _jig(press=0.5)


def test_thin_plate_fails_engagement():
    f = check_bushing_fit_ok(_jig(plate=(120.0, 40.0, 3.0)))
    assert f.status is Status.FAIL
    assert "grip" in f.message


def test_seats_too_close_fail_web():
    f = check_bushing_fit_ok(_jig(spacing=10.0))
    assert f.status is Status.FAIL
    assert "web" in f.message


def test_row_past_plate_end_fails_wall():
    f = check_bushing_fit_ok(_jig(spacing=40.0))
    assert f.status is Status.FAIL
    assert "wall" in f.message


def test_fence_drop_out_of_band_refused_by_op():
    with pytest.raises(RecipeError, match="fence_drop"):
        _jig(fence_drop=40.0)


def test_checks_na_without_jig_features():
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 80.0, "w": 40.0, "t": 4.0, "corner_r": 4.0}, "plate")
    assert "n/a" in check_bushing_fit_ok(st).message
    assert "n/a" in check_stop_registration_ok(st).message
