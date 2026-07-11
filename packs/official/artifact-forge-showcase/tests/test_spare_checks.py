"""Spare Fit Standard checks — PASS / FAIL / n-a branches, measured on
real op-built forms (never on hand-typed frames)."""
from __future__ import annotations

import pytest

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState

from artifact_forge_showcase.checks.spare import (
    check_barb_retention_ok,
    check_knob_torque_wall_ok,
    check_shaft_fit_ok,
)


def _adapter(**over) -> RecipeState:
    st = RecipeState()
    p = {"spigot_d_a": 32.0, "spigot_d_b": 35.0,
         "spigot_len_a": 30.0, "spigot_len_b": 30.0,
         "wall": 2.4, "barb_h": 0.8, "barb_count_a": 3, "barb_count_b": 3,
         "flange_t": 4.0, "flange_lip": 2.5}
    p.update(over)
    RECIPE_OPS["hose_adapter_body"].apply(st, p, "body")
    return st


def _knob(**over) -> RecipeState:
    st = RecipeState()
    p = {"grip_d": 35.0, "grip_h": 18.0, "shaft_sq": 6.0,
         "socket_depth": 10.0, "fit_clearance": 0.25, "top_chamfer": 2.0}
    p.update(over)
    RECIPE_OPS["knob_body"].apply(st, p, "body")
    return st


# -- barb retention -----------------------------------------------------------

def test_healthy_adapter_barbs_pass():
    f = check_barb_retention_ok(_adapter())
    assert f.status is Status.PASS
    assert "retention band" in f.message


def test_low_barbs_fail():
    f = check_barb_retention_ok(_adapter(barb_h=0.2))
    assert f.status is Status.FAIL
    assert "outside" in f.message


def test_single_barb_refused_by_op():
    with pytest.raises(RecipeError, match="at least 2 barbs"):
        _adapter(barb_count_a=1)


def test_barb_check_na_on_knob():
    f = check_barb_retention_ok(_knob())
    assert f.status is Status.PASS
    assert "n/a" in f.message


def test_tiny_spigots_refused_by_op():
    with pytest.raises(RecipeError, match="bore radius"):
        _adapter(spigot_d_a=8.0, spigot_d_b=8.0)


def test_adapter_profile_is_closed_and_clear_of_axis():
    st = _adapter()
    assert st.kind == "profile_revolve"
    lo, _ = st.section.outer.bbox()
    assert lo.u >= st.frame["axis_clear_r"] - 1e-6
    assert st.frame["bore_d"] > 0


# -- shaft fit ----------------------------------------------------------------

def test_healthy_knob_fit_passes():
    f = check_shaft_fit_ok(_knob())
    assert f.status is Status.PASS


def test_zero_clearance_binds():
    f = check_shaft_fit_ok(_knob(fit_clearance=0.02))
    assert f.status is Status.FAIL
    assert "clearance" in f.message


def test_shallow_socket_fails():
    f = check_shaft_fit_ok(_knob(socket_depth=4.0))
    assert f.status is Status.FAIL
    assert "engagement" in f.message


def test_fit_check_na_on_adapter():
    f = check_shaft_fit_ok(_adapter())
    assert f.status is Status.PASS
    assert "n/a" in f.message


# -- torque wall --------------------------------------------------------------

def test_torque_wall_passes_on_default():
    f = check_knob_torque_wall_ok(_knob())
    assert f.status is Status.PASS


def test_thin_wall_refused_or_failed():
    # a huge shaft in a small grip must be refused by the op itself
    with pytest.raises(RecipeError, match="break out"):
        _knob(grip_d=20.0, shaft_sq=12.0)


def test_torque_check_na_on_adapter():
    f = check_knob_torque_wall_ok(_adapter())
    assert f.status is Status.PASS
    assert "n/a" in f.message
