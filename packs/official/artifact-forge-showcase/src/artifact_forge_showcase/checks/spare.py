"""Repair-domain form checks — the measuring half of the Spare Fit
Standard. Every check reads the frame keys the spare ops publish; a part
without those keys is honestly n/a, never a false PASS."""
from __future__ import annotations

from artifact_forge_ng.core.findings import Finding
from artifact_forge_ng.form.checks_common import make_finding
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.validators.probes import register_probe

from ..ops.spare import BARB_H_BAND, SOCKET_DEPTH_K, SQ_FIT_BAND

_finding = make_finding


def check_barb_retention_ok(form: PartForm) -> Finding:
    """Each spigot's barbs must actually retain a pushed-on hose: barb
    height inside the retention band (too low slips, too high splits the
    hose) and at least two barbs per spigot."""
    check = "form.barb_retention_ok"
    f = form.frame
    if "spigot_d_a" not in f:
        return _finding(check, True, "n/a — no hose spigots on this part",
                        critical=False)
    lo, hi = BARB_H_BAND
    problems: list[str] = []
    for side in ("a", "b"):
        h = f.get(f"barb_h_{side}", 0.0)
        n = f.get(f"barb_count_{side}", 0.0)
        if not lo <= h <= hi:
            problems.append(
                f"spigot {side}: barb height {h:g} outside [{lo:g}, {hi:g}]")
        if n < 2:
            problems.append(f"spigot {side}: {n:g} barbs < 2")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"barbs {f['barb_h_a']:g} mm on both spigots "
        f"({f['barb_count_a']:g} + {f['barb_count_b']:g} teeth), "
        f"inside the [{lo:g}, {hi:g}] retention band",
        measured=f["barb_h_a"], limit=hi)


def check_shaft_fit_ok(form: PartForm) -> Finding:
    """The square socket must fit the measured shaft: across-flats
    clearance inside the fit band and enough engagement depth."""
    check = "form.shaft_fit_ok"
    f = form.frame
    if "shaft_sq" not in f:
        return _finding(check, True, "n/a — no shaft socket on this part",
                        critical=False)
    lo, hi = SQ_FIT_BAND
    gap = f["socket_w_eff"] - f["shaft_sq"]
    min_depth = SOCKET_DEPTH_K * f["shaft_sq"]
    if not lo <= gap <= hi:
        return _finding(
            check, False,
            f"across-flats clearance {gap:.2f} outside [{lo:g}, {hi:g}] — "
            "binds when the print swells or rocks on the shaft",
            measured=gap, limit=hi)
    if f["socket_depth"] < min_depth:
        return _finding(
            check, False,
            f"socket depth {f['socket_depth']:g} < {min_depth:g} "
            f"({SOCKET_DEPTH_K:g}x shaft) — not enough engagement",
            measured=f["socket_depth"], limit=min_depth)
    return _finding(
        check, True,
        f"clearance {gap:.2f} in band, engagement "
        f"{f['socket_depth']:g} >= {min_depth:g}",
        measured=gap, limit=hi)


def check_knob_torque_wall_ok(form: PartForm) -> Finding:
    """The wall between the socket corners and the grip surface carries
    the hand torque — it must not thin below the material floor."""
    check = "form.knob_torque_wall_ok"
    f = form.frame
    if "torque_wall" not in f:
        return _finding(check, True, "n/a — not a knob", critical=False)
    need = max(2.4, 0.25 * f.get("shaft_sq", 0.0))
    wall = f["torque_wall"]
    ok = wall >= need - 1e-6
    return _finding(
        check, ok,
        f"corner wall {wall:.2f} {'≥' if ok else '<'} required {need:.2f}",
        measured=wall, limit=need)


register_probe("form.barb_retention_ok")(
    lambda form, ctx: check_barb_retention_ok(form))
register_probe("form.shaft_fit_ok")(
    lambda form, ctx: check_shaft_fit_ok(form))
register_probe("form.knob_torque_wall_ok")(
    lambda form, ctx: check_knob_torque_wall_ok(form))
