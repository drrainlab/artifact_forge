"""Pegboard form checks — peg-in-hole fit, board pass-through and hook
retention, measured from the frame keys peg_pattern publishes."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_pegboard import MIN_HOOK_LEN, PEG_FIT_BAND

_finding = make_finding


def check_peg_engagement_ok(form: PartForm) -> Finding:
    """The pegs must actually engage the declared board: diametral fit in
    band, length past the board, hooks long enough to retain, and an
    anti-lift peg whenever the pattern hooks."""
    check = "form.peg_engagement_ok"
    f = form.frame
    if "peg_pitch" not in f:
        return _finding(check, True, "n/a — no pegboard pegs on this part",
                        critical=False)
    lo, hi = PEG_FIT_BAND
    problems: list[str] = []
    fit = f["board_hole_d"] - f["peg_d"]
    if not lo <= fit <= hi:
        problems.append(
            f"peg fit {fit:.2f} outside [{lo:g}, {hi:g}] — the peg either "
            "jams in the hole or rattles")
    if f["peg_len"] < f["board_t"] + 1.0 - 1e-6:
        problems.append(
            f"peg {f['peg_len']:g} never passes the {f['board_t']:g} board")
    if f["peg_hook_count"] > 0:
        if f["peg_hook_len"] < MIN_HOOK_LEN - 1e-6:
            problems.append(
                f"hook tip {f['peg_hook_len']:g} < {MIN_HOOK_LEN:g}")
        if f["peg_anti_lift"] < 1:
            problems.append(
                "hooked pattern carries no anti-lift peg — the part "
                "rotates out of the board under load")
    if problems:
        return _finding(check, False, "; ".join(problems),
                        measured=fit, limit=hi)
    return _finding(
        check, True,
        f"{f['peg_count']:g} pegs fit the board at {fit:.2f} diametral "
        f"({f['peg_hook_count']:g} hooked, "
        f"{f['peg_anti_lift']:g} anti-lift)",
        measured=fit, limit=hi)


register_probe("form.peg_engagement_ok")(
    lambda form, ctx: check_peg_engagement_ok(form))
