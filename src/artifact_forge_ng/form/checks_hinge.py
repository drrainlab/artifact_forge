"""Hinge form checks — pin fit, knuckle geometry and the family's
honesty note: AF verifies the printed geometry; hinge torque, wear and
friction preload live in the hardware and the assembled pair."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_hinge import HINGE_GAP_BAND, HINGE_PIN_SLIP_BAND, HINGE_WELD_BITE

_finding = make_finding


def check_hinge_pin_fit_ok(form: PartForm) -> Finding:
    """Pin mode: the barrel bore must SLIP on the hardware pin — the
    band keeps it turning without wobble. Bolt mode: the bore is the
    screw's own clearance table entry, pass by construction."""
    check = "form.hinge_pin_fit_ok"
    f = form.frame
    if "hinge_pin_d" not in f:
        return _finding(check, True, "n/a — no hinge on this part",
                        critical=False)
    if f["hinge_is_bolt"] > 0:
        return _finding(check, True,
                        "bolt mode — clearance from the screw table")
    lo, hi = HINGE_PIN_SLIP_BAND
    slip = f["hinge_bore_d"] - f["hinge_pin_d"]
    ok = lo <= slip <= hi
    return _finding(
        check, ok,
        f"bore slips the pin by {slip:.2f} "
        f"({'inside' if ok else 'outside'} [{lo:g}, {hi:g}])",
        measured=slip, limit=hi)


def check_hinge_knuckle_geometry_ok(form: PartForm) -> Finding:
    """The knuckle pattern must actually mesh with its sibling: axial
    gap in band, the barrel biting the plate edge, real barrel wall."""
    check = "form.hinge_knuckle_geometry_ok"
    f = form.frame
    if "hinge_knuckle_d" not in f:
        return _finding(check, True, "n/a — no hinge on this part",
                        critical=False)
    problems: list[str] = []
    lo, hi = HINGE_GAP_BAND
    if not lo <= f["hinge_gap"] <= hi:
        problems.append(f"gap {f['hinge_gap']:g} outside [{lo:g}, {hi:g}]")
    bite = f["hinge_knuckle_d"] / 2.0 - (f["hinge_axis_y"] - f["outline_v1"])
    if bite < HINGE_WELD_BITE - 1e-6:
        problems.append(f"barrel bites the plate by {bite:.2f} < "
                        f"{HINGE_WELD_BITE:g}")
    wall = (f["hinge_knuckle_d"] - f["hinge_bore_d"]) / 2.0
    if wall < 1.0 - 1e-6:
        problems.append(f"barrel wall {wall:.2f} < 1.0")
    mine = f["hinge_knuckles_mine"]
    total = f["hinge_knuckles_total"]
    expect = (total + 1) // 2 if f["hinge_side"] < 0.5 else total // 2
    if mine != expect:
        problems.append(
            f"{mine:g} segments built, side expects {expect:g}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{mine:g}/{total:g} knuckles, gap {f['hinge_gap']:g}, barrel "
        f"wall {wall:.2f} — meshes its sibling by construction")


def check_hinge_motion_unverified(form: PartForm) -> Finding:
    """Honesty note: AF measures the printed geometry only — hinge
    torque, friction preload and cycle life live in the hardware pin /
    bolt and the assembled pair."""
    check = "form.hinge_motion_unverified"
    f = form.frame
    if "hinge_pin_d" not in f:
        return _finding(check, True, "n/a — no hinge on this part",
                        critical=False)
    return _finding(
        check, True,
        "geometry verified; torque/friction/cycle-life are hardware and "
        "assembly properties, not printed ones",
        critical=False)


register_probe("form.hinge_pin_fit_ok")(
    lambda form, ctx: check_hinge_pin_fit_ok(form))
register_probe("form.hinge_knuckle_geometry_ok")(
    lambda form, ctx: check_hinge_knuckle_geometry_ok(form))
register_probe("form.hinge_motion_unverified")(
    lambda form, ctx: check_hinge_motion_unverified(form))


# -- rail slider (R2.12 — mechanics family shares this module) -----------------


def check_rail_slider_fit_ok(form: PartForm) -> Finding:
    """The shoe must SLIDE its rail: lateral and vertical clearance in
    band, and enough travel not to yaw."""
    from .recipe_ops_dovetail import (
        SLIDE_LAT_BAND, SLIDE_VERT_BAND, SLIDER_ENGAGE_K)

    check = "form.rail_slider_fit_ok"
    f = form.frame
    if "slider_travel" not in f:
        return _finding(check, True, "n/a — not a rail slider",
                        critical=False)
    problems: list[str] = []
    lo, hi = SLIDE_LAT_BAND
    if not lo <= f["slider_lat_clearance"] <= hi:
        problems.append(
            f"lateral {f['slider_lat_clearance']:g} outside [{lo:g}, {hi:g}]")
    vlo, vhi = SLIDE_VERT_BAND
    if not vlo <= f["slider_vert_clearance"] <= vhi:
        problems.append(
            f"vertical {f['slider_vert_clearance']:g} outside "
            f"[{vlo:g}, {vhi:g}]")
    need = SLIDER_ENGAGE_K * f["slider_rail_top_w"]
    if f["slider_travel"] < need - 1e-6:
        problems.append(
            f"travel {f['slider_travel']:g} < {need:g} — the shoe yaws")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"slides at {f['slider_lat_clearance']:g}/"
        f"{f['slider_vert_clearance']:g} clearance over "
        f"{f['slider_travel']:g} travel")


def check_rail_slider_walls_ok(form: PartForm) -> Finding:
    """The shoe's side walls and ceiling must stay real — they carry
    the payload moment across the slot."""
    from .recipe_ops_dovetail import SLIDER_WALL_MIN

    check = "form.rail_slider_walls_ok"
    f = form.frame
    if "slider_travel" not in f:
        return _finding(check, True, "n/a — not a rail slider",
                        critical=False)
    problems: list[str] = []
    if f["slider_wall"] < SLIDER_WALL_MIN - 1e-6:
        problems.append(f"side wall {f['slider_wall']:g} < {SLIDER_WALL_MIN:g}")
    if f["slider_ceiling"] < 3.0 - 1e-6:
        problems.append(f"ceiling {f['slider_ceiling']:g} < 3")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"walls {f['slider_wall']:g}, ceiling {f['slider_ceiling']:g} real")


register_probe("form.rail_slider_fit_ok")(
    lambda form, ctx: check_rail_slider_fit_ok(form))
register_probe("form.rail_slider_walls_ok")(
    lambda form, ctx: check_rail_slider_walls_ok(form))


# -- living hinge (R2.13) -------------------------------------------------------


def check_living_hinge_web_ok(form: PartForm) -> Finding:
    """The flex web must sit in the band that folds without tearing."""
    from .recipe_ops_hinge import LIVING_GROOVE_BAND, LIVING_WEB_BAND

    check = "form.living_hinge_web_ok"
    f = form.frame
    if "lh_web_t" not in f:
        return _finding(check, True, "n/a — no living hinge on this part",
                        critical=False)
    problems: list[str] = []
    lo, hi = LIVING_WEB_BAND
    if not lo <= f["lh_web_t"] <= hi:
        problems.append(f"web {f['lh_web_t']:g} outside [{lo:g}, {hi:g}]")
    glo, ghi = LIVING_GROOVE_BAND
    if not glo <= f["lh_groove_w"] <= ghi:
        problems.append(
            f"groove {f['lh_groove_w']:g} outside [{glo:g}, {ghi:g}]")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"web {f['lh_web_t']:g} in the fold band, groove "
        f"{f['lh_groove_w']:g} gives the bend its radius",
        measured=f["lh_web_t"], limit=hi)


def check_living_hinge_fatigue_unverified(form: PartForm) -> Finding:
    """Honesty note: fold-cycle life is a MATERIAL property AF cannot
    measure — PETG/PLA webs survive tens of folds, polypropylene
    thousands. The geometry is verified; the fatigue is not."""
    check = "form.living_hinge_fatigue_unverified"
    f = form.frame
    if "lh_web_t" not in f:
        return _finding(check, True, "n/a — no living hinge on this part",
                        critical=False)
    return _finding(
        check, True,
        "web geometry verified; fold-cycle life is a material property "
        "(PETG/PLA: tens of folds; PP: the real living hinge)",
        critical=False)


register_probe("form.living_hinge_web_ok")(
    lambda form, ctx: check_living_hinge_web_ok(form))
register_probe("form.living_hinge_fatigue_unverified")(
    lambda form, ctx: check_living_hinge_fatigue_unverified(form))
