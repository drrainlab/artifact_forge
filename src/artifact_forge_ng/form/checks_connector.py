"""Connector form checks — socket engagement and bore isolation on the
multi-socket hub family, measured from the frame keys socket_arm
publishes."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_connector import SOCKET_ENGAGE_K, SOCKET_WALL_MIN

_finding = make_finding


def _sockets(form: PartForm) -> list[str]:
    return [k[: -len("_socket_depth")] for k in form.frame
            if k.endswith("_socket_depth")]


def check_socket_engagement_ok(form: PartForm) -> Finding:
    """Every socket must hold its rod: depth at least k x rod diameter
    and a real wall around the bore."""
    check = "form.socket_engagement_ok"
    names = _sockets(form)
    if not names:
        return _finding(check, True, "n/a — no rod sockets on this part",
                        critical=False)
    f = form.frame
    problems: list[str] = []
    for n in names:
        need = SOCKET_ENGAGE_K * f[f"{n}_rod_d"]
        if f[f"{n}_socket_depth"] < need - 1e-6:
            problems.append(
                f"{n}: depth {f[f'{n}_socket_depth']:g} < {need:g} "
                f"({SOCKET_ENGAGE_K:g}x rod)")
        if f[f"{n}_wall_eff"] < SOCKET_WALL_MIN - 1e-6:
            problems.append(
                f"{n}: wall {f[f'{n}_wall_eff']:.2f} < {SOCKET_WALL_MIN:g}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{len(names)} sockets engage >= {SOCKET_ENGAGE_K:g}x rod with "
        f"walls >= {SOCKET_WALL_MIN:g}")


def check_socket_bores_isolated(form: PartForm) -> Finding:
    """Blind socket ends must stay clear of the hub center whenever more
    than one socket exists — merged sockets turn a connector into an
    accidental through-tunnel and rods bottom out on each other."""
    check = "form.socket_bores_isolated"
    names = _sockets(form)
    if not names:
        return _finding(check, True, "n/a — no rod sockets on this part",
                        critical=False)
    if len(names) == 1:
        return _finding(check, True, "single socket — nothing to isolate")
    f = form.frame
    max_bore_r = max(f[f"{n}_socket_bore_d"] for n in names) / 2.0
    need = max_bore_r + 1.0
    problems = [
        f"{n}: blind end {f[f'{n}_inner_dist']:.1f} from center < {need:.1f}"
        for n in names if f[f"{n}_inner_dist"] < need - 1e-6
    ]
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{len(names)} blind ends keep >= {need:.1f} to the hub center")


register_probe("form.socket_engagement_ok")(
    lambda form, ctx: check_socket_engagement_ok(form))
register_probe("form.socket_bores_isolated")(
    lambda form, ctx: check_socket_bores_isolated(form))


def check_tube_wall_ok(form: PartForm) -> Finding:
    """Every limb of a branched tube keeps a real wall."""
    check = "form.tube_wall_ok"
    f = form.frame
    if "tee_run_wall" not in f:
        return _finding(check, True, "n/a — not a branched tube",
                        critical=False)
    problems: list[str] = []
    for what, key in (("run", "tee_run_wall"), ("branch", "tee_branch_wall")):
        if f[key] < SOCKET_WALL_MIN - 1e-6:
            problems.append(f"{what} wall {f[key]:.2f} < {SOCKET_WALL_MIN:g}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"run wall {f['tee_run_wall']:g}, branch wall "
        f"{f['tee_branch_wall']:g} >= {SOCKET_WALL_MIN:g}")


def check_branch_path_connected(form: PartForm) -> Finding:
    """Each branch bore's inner end must land INSIDE the main run bore —
    a fluid tee whose branch stops short is a decorative stub."""
    check = "form.branch_path_connected"
    f = form.frame
    if "tee_branch_inner_x" not in f:
        return _finding(check, True, "n/a — not a branched tube",
                        critical=False)
    reach = abs(f["tee_branch_inner_x"])
    limit = f["tee_run_bore_r"] - 0.5
    ok = reach <= limit + 1e-6
    return _finding(
        check, ok,
        f"branch inner end at |x|={reach:g} "
        f"{'inside' if ok else 'OUTSIDE'} the run bore (r={f['tee_run_bore_r']:g})",
        measured=reach, limit=limit)


register_probe("form.tube_wall_ok")(
    lambda form, ctx: check_tube_wall_ok(form))
register_probe("form.branch_path_connected")(
    lambda form, ctx: check_branch_path_connected(form))


def check_tube_run_open(form: PartForm) -> Finding:
    """The run bore must serve every limb: a THROUGH run is open by
    construction (the wrapped adapter profile carries its own guards); a
    CAPPED run (elbow) must swallow the whole branch junction, or the
    corner never turns."""
    check = "form.tube_run_open"
    f = form.frame
    if "run_capped" not in f:
        return _finding(check, True, "n/a — not a branched tube",
                        critical=False)
    if f["run_capped"] < 1.0:
        return _finding(check, True, "through run — open end to end by "
                                     "construction")
    need = f["tee_branch_z"] + f["tee_branch_bore_d"] / 2.0 + 1.5
    ok = f["run_bore_top"] >= need - 1e-6
    return _finding(
        check, ok,
        f"blind run bore tops at {f['run_bore_top']:g} "
        f"({'≥' if ok else '<'} branch junction + margin {need:g})",
        measured=f["run_bore_top"], limit=need)


register_probe("form.tube_run_open")(
    lambda form, ctx: check_tube_run_open(form))
