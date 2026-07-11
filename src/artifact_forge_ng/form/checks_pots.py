"""Revolve-family form checks — spool flanges, pot taper and drainage,
net pot mesh and wall slots. Measured from the frame keys and features
the revolve-family ops publish; anything else is honestly n/a."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_revolve import POT_TAPER_MAX_DEG, SLOT_LIGAMENT_MIN, SPOOL_CORD_MARGIN

_finding = make_finding

#: Open-area band for a net pot floor: below it the roots choke, above it
#: the substrate falls through.
FLOOR_OPEN_BAND = (0.2, 0.85)


def check_spool_flanges_ok(form: PartForm) -> Finding:
    """The flanges must out-reach the barrel enough to actually hold a
    wound cord."""
    check = "form.spool_flanges_ok"
    f = form.frame
    if "flange_margin" not in f:
        return _finding(check, True, "n/a — not a spool", critical=False)
    margin = f["flange_margin"]
    ok = margin >= SPOOL_CORD_MARGIN - 1e-6
    return _finding(
        check, ok,
        f"flange out-reaches the barrel by {margin:.1f} "
        f"({'≥' if ok else '<'} {SPOOL_CORD_MARGIN:g})",
        measured=margin, limit=SPOOL_CORD_MARGIN)


def check_pot_taper_ok(form: PartForm) -> Finding:
    """The vessel must open upward and its wall lean must stay inside the
    printable band."""
    check = "form.pot_taper_ok"
    f = form.frame
    if "pot_taper_deg" not in f:
        return _finding(check, True, "n/a — not a tapered vessel",
                        critical=False)
    taper = f["pot_taper_deg"]
    if taper < -1e-6:
        return _finding(check, False,
                        f"vessel narrows upward ({taper:.1f} deg)",
                        measured=taper, limit=0.0)
    ok = taper <= POT_TAPER_MAX_DEG + 1e-6
    return _finding(
        check, ok,
        f"wall leans {taper:.1f} deg outward "
        f"({'≤' if ok else '>'} printable {POT_TAPER_MAX_DEG:g})",
        measured=taper, limit=POT_TAPER_MAX_DEG)


def check_pot_floor_drains(form: PartForm) -> Finding:
    """At least one vertical bore must span the raised floor slab so the
    cavity actually drains into the air gap beneath it."""
    check = "form.pot_floor_drains"
    f = form.frame
    if "pot_floor_z0" not in f:
        return _finding(check, True, "n/a — no raised pot floor",
                        critical=False)
    z0, z1 = f["pot_floor_z0"], f["pot_floor_top"]
    r_in = f["pot_inner_r_floor"]
    drains = [
        b for b in form.bores
        if b.axis == "Z"
        and b.span[0] <= z0 + 0.1 and b.span[1] >= z1 - 0.1
        and (b.center[0] ** 2 + b.center[1] ** 2) ** 0.5 <= r_in + 1e-6
    ]
    if not drains:
        return _finding(
            check, False,
            "no drainage bore spans the raised floor — the pot is a "
            "bucket, not a planter")
    return _finding(
        check, True,
        f"{len(drains)} drainage bores pierce the raised floor into the "
        "air gap")


def check_floor_open_area_ok(form: PartForm) -> Finding:
    """The mesh floor's open-area ratio must sit in the working band."""
    check = "form.floor_open_area_ok"
    f = form.frame
    if "floor_open_ratio" not in f:
        return _finding(check, True, "n/a — no mesh floor", critical=False)
    lo, hi = FLOOR_OPEN_BAND
    ratio = f["floor_open_ratio"]
    ok = lo <= ratio <= hi
    return _finding(
        check, ok,
        f"floor open area {ratio:.2f} "
        f"({'inside' if ok else 'outside'} [{lo:g}, {hi:g}])",
        measured=ratio, limit=hi)


def check_wall_slots_ok(form: PartForm) -> Finding:
    """The wall slot ring must keep real ligaments and stay inside the
    band between floor and flange."""
    check = "form.wall_slots_ok"
    f = form.frame
    if "wall_slot_count" not in f:
        return _finding(check, True, "n/a — no wall slot ring",
                        critical=False)
    problems: list[str] = []
    if f["wall_slot_gap"] < SLOT_LIGAMENT_MIN - 1e-6:
        problems.append(
            f"ligament {f['wall_slot_gap']:.1f} < {SLOT_LIGAMENT_MIN:g}")
    floor_t = f.get("net_floor_t", 0.0)
    if f["wall_slot_z0"] < floor_t + 1.5 - 1e-6:
        problems.append("slots reach into the floor band")
    rim = f.get("net_rim_z", 0.0) - f.get("net_flange_t", 0.0)
    if f["wall_slot_z1"] > rim - 1.5 + 1e-6:
        problems.append("slots reach into the flange band")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{f['wall_slot_count']:g} slots, ligament "
        f"{f['wall_slot_gap']:.1f}, band clear of floor and flange")


register_probe("form.spool_flanges_ok")(
    lambda form, ctx: check_spool_flanges_ok(form))
register_probe("form.pot_taper_ok")(
    lambda form, ctx: check_pot_taper_ok(form))
register_probe("form.pot_floor_drains")(
    lambda form, ctx: check_pot_floor_drains(form))
register_probe("form.floor_open_area_ok")(
    lambda form, ctx: check_floor_open_area_ok(form))
register_probe("form.wall_slots_ok")(
    lambda form, ctx: check_wall_slots_ok(form))


def check_foot_press_fit_ok(form: PartForm) -> Finding:
    """The press spigot must hold in the tube: interference inside the
    band, real engagement, and a shoulder around the spigot."""
    from .recipe_ops_revolve import FOOT_ENGAGE_K, FOOT_PRESS_BAND

    check = "form.foot_press_fit_ok"
    f = form.frame
    if "foot_spigot_d" not in f:
        return _finding(check, True, "n/a — no press-fit foot spigot",
                        critical=False)
    lo, hi = FOOT_PRESS_BAND
    problems: list[str] = []
    if not lo <= f["foot_press"] <= hi:
        problems.append(
            f"press {f['foot_press']:g} outside [{lo:g}, {hi:g}]")
    need = FOOT_ENGAGE_K * f["foot_tube_id"]
    if f["foot_spigot_l"] < need - 1e-6:
        problems.append(
            f"spigot {f['foot_spigot_l']:g} < {need:g} "
            f"({FOOT_ENGAGE_K:g}x tube bore)")
    if f["foot_spigot_d"] / 2.0 + 2.0 > f["foot_pad_r"] + 1e-6:
        problems.append("no pad shoulder around the spigot")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"spigot Ø{f['foot_spigot_d']:g} presses {f['foot_press']:g} into "
        f"the tube, engagement {f['foot_spigot_l']:g}",
        measured=f["foot_press"], limit=hi)


register_probe("form.foot_press_fit_ok")(
    lambda form, ctx: check_foot_press_fit_ok(form))
