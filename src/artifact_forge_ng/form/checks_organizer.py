"""Organizer form checks — dividers, finger scoop, stacking lip. Every
check measures the frame keys and features the organizer ops publish;
parts without them are honestly n/a."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_organizer import MIN_LIP_WALL, SCOOP_FLOOR_MIN, WELD

_finding = make_finding


def check_dividers_span_cavity(form: PartForm) -> Finding:
    """Every divider wall must weld into BOTH host walls and the floor —
    a floating divider is a loose blade, not a divider."""
    check = "form.dividers_span_cavity"
    f = form.frame
    if "divider_nx" not in f:
        return _finding(check, True, "n/a — no dividers on this part",
                        critical=False)
    dividers = [r for r in form.ribs if "_div_" in r.name]
    declared = int(f["divider_nx"] + f["divider_ny"])
    problems: list[str] = []
    if len(dividers) != declared:
        problems.append(
            f"{len(dividers)} divider ribs found, {declared} declared")
    u0, v0 = f["inner_u0"], f["inner_v0"]
    u1, v1 = f["inner_u1"], f["inner_v1"]
    floor_t = f["floor_t"]
    for r in dividers:
        b = r.box
        if b.z0 > floor_t - WELD + 1e-6:
            problems.append(f"{r.name}: root {b.z0:.2f} misses the floor weld")
        along_y = (b.y1 - b.y0) > (b.x1 - b.x0)
        if along_y and (b.y0 > v0 - WELD + 1e-6 or b.y1 < v1 + WELD - 1e-6):
            problems.append(f"{r.name}: does not span wall to wall")
        if not along_y and (b.x0 > u0 - WELD + 1e-6 or b.x1 < u1 + WELD - 1e-6):
            problems.append(f"{r.name}: does not span wall to wall")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"{declared} dividers welded wall-to-wall and into the floor")


def check_divider_cells_min_size(form: PartForm) -> Finding:
    """The cells the dividers create must stay usable — measured against
    the min_cell the op published."""
    check = "form.divider_cells_min_size"
    f = form.frame
    if "divider_nx" not in f:
        return _finding(check, True, "n/a — no dividers on this part",
                        critical=False)
    min_cell = f["divider_min_cell"]
    problems: list[str] = []
    if f["divider_nx"] >= 1 and f["cell_w"] < min_cell - 1e-6:
        problems.append(f"cells {f['cell_w']:.1f} wide < {min_cell:g}")
    if f["divider_ny"] >= 1 and f["cell_l"] < min_cell - 1e-6:
        problems.append(f"cells {f['cell_l']:.1f} long < {min_cell:g}")
    if problems:
        return _finding(check, False, "; ".join(problems),
                        measured=min(f["cell_w"], f["cell_l"]), limit=min_cell)
    return _finding(
        check, True,
        f"cells {f['cell_w']:.1f} x {f['cell_l']:.1f} >= {min_cell:g}",
        measured=min(f["cell_w"], f["cell_l"]), limit=min_cell)


def check_scoop_clears_floor(form: PartForm) -> Finding:
    """The finger cove must leave a real wall band above the floor."""
    check = "form.scoop_clears_floor"
    f = form.frame
    if "scoop_bottom_z" not in f:
        return _finding(check, True, "n/a — no finger scoop on this part",
                        critical=False)
    floor_t = f.get("floor_t", 0.0)
    clear = f["scoop_bottom_z"] - floor_t
    ok = clear >= SCOOP_FLOOR_MIN - 1e-6
    return _finding(
        check, ok,
        f"scoop bottom sits {clear:.1f} above the floor "
        f"({'≥' if ok else '<'} {SCOOP_FLOOR_MIN:g})",
        measured=clear, limit=SCOOP_FLOOR_MIN)


def check_stacking_lip_nests(form: PartForm) -> Finding:
    """The floor plug must fit inside a sibling's lip opening with the
    declared clearance on every side, the rebate must be at least lip
    deep, and the lip must stay printable."""
    check = "form.stacking_lip_nests"
    f = form.frame
    if "lip_h" not in f:
        return _finding(check, True, "n/a — no stacking lip on this part",
                        critical=False)
    c = f["lip_clearance"]
    problems: list[str] = []
    if f["lip_wall"] < MIN_LIP_WALL - 1e-6:
        problems.append(f"lip wall {f['lip_wall']:g} < {MIN_LIP_WALL:g}")
    for side, plug, lip, sign in (
        ("u0", f["plug_u0"], f["lip_inner_u0"], 1.0),
        ("v0", f["plug_v0"], f["lip_inner_v0"], 1.0),
        ("u1", f["plug_u1"], f["lip_inner_u1"], -1.0),
        ("v1", f["plug_v1"], f["lip_inner_v1"], -1.0),
    ):
        gap = sign * (plug - lip)
        if gap < c - 1e-6:
            problems.append(f"{side}: plug clears the lip by {gap:.2f} < {c:g}")
    if f["recess_depth"] < f["lip_h"] + c - 1e-6:
        problems.append(
            f"rebate {f['recess_depth']:g} shallower than lip "
            f"{f['lip_h']:g} + clearance")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"floor plug nests inside the {f['lip_h']:g} x {f['lip_wall']:g} "
        f"lip with {c:g} clearance on all sides")


register_probe("form.dividers_span_cavity")(
    lambda form, ctx: check_dividers_span_cavity(form))
register_probe("form.divider_cells_min_size")(
    lambda form, ctx: check_divider_cells_min_size(form))
register_probe("form.scoop_clears_floor")(
    lambda form, ctx: check_scoop_clears_floor(form))
register_probe("form.stacking_lip_nests")(
    lambda form, ctx: check_stacking_lip_nests(form))
