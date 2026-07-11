"""Ratchet form checks — tooth geometry measured from the published
frame, plus the family's honesty note: a wheel without its pawl is not
yet a ratchet MECHANISM."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_ratchet import (
    RATCHET_DEPTH_MIN, RATCHET_STEEP_FRAC_MAX, RATCHET_TEETH_BAND,
    RATCHET_TIP_ARC_MIN)

_finding = make_finding


def check_ratchet_teeth_ok(form: PartForm) -> Finding:
    """The teeth must lock one way and ramp the other, at a printable
    pitch and depth."""
    check = "form.ratchet_teeth_ok"
    f = form.frame
    if "ratchet_teeth" not in f:
        return _finding(check, True, "n/a — no ratchet teeth on this part",
                        critical=False)
    problems: list[str] = []
    lo, hi = RATCHET_TEETH_BAND
    if not lo <= f["ratchet_teeth"] <= hi:
        problems.append(f"{f['ratchet_teeth']:g} teeth outside [{lo}, {hi}]")
    if f["ratchet_tooth_depth"] < RATCHET_DEPTH_MIN - 1e-6:
        problems.append(
            f"depth {f['ratchet_tooth_depth']:g} < {RATCHET_DEPTH_MIN:g}")
    if f["ratchet_steep_frac"] > RATCHET_STEEP_FRAC_MAX + 1e-9:
        problems.append(
            f"locking face {f['ratchet_steep_frac']:g} of the pitch — "
            "a worm ramp, not a ratchet")
    if f["ratchet_pitch_arc"] < RATCHET_TIP_ARC_MIN - 1e-6:
        problems.append(
            f"pitch arc {f['ratchet_pitch_arc']:.1f} < "
            f"{RATCHET_TIP_ARC_MIN:g}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{f['ratchet_teeth']:g} teeth, depth "
        f"{f['ratchet_tooth_depth']:g}, locking face "
        f"{f['ratchet_steep_frac']:g} of pitch — locks one way, ramps "
        "the other")


def check_ratchet_pawl_unverified(form: PartForm) -> Finding:
    """Honesty note: the WHEEL is verified; the sprung pawl (flexure
    geometry + fatigue) is its own iteration — until it lands, this is
    a toothed wheel, not a complete ratchet mechanism."""
    check = "form.ratchet_pawl_unverified"
    if "ratchet_teeth" not in form.frame:
        return _finding(check, True, "n/a — no ratchet teeth on this part",
                        critical=False)
    return _finding(
        check, True,
        "wheel geometry verified; the sprung pawl is a separate "
        "iteration — pair with a hardware pawl or a printed flexure at "
        "your own measure",
        critical=False)


register_probe("form.ratchet_teeth_ok")(
    lambda form, ctx: check_ratchet_teeth_ok(form))
register_probe("form.ratchet_pawl_unverified")(
    lambda form, ctx: check_ratchet_pawl_unverified(form))
