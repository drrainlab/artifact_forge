"""Battery cell holder form checks — measured from the frame keys
cell_pocket_grid publishes; parts without a cell grid are honestly n/a."""
from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .checks_common import make_finding
from .part import PartForm
from .recipe_ops_base import CELL_LIP_BITE_BAND, CELL_WEB_MIN

_finding = make_finding


def check_cell_lip_retains(form: PartForm) -> Finding:
    """The mouth must be measurably narrower than the cell — inside the
    bite band — and the lip band must be tall enough to survive a snap."""
    check = "form.cell_lip_retains"
    f = form.frame
    if "cell_lip_bite" not in f:
        return _finding(check, True, "n/a — no cell pockets on this part",
                        critical=False)
    lo, hi = CELL_LIP_BITE_BAND
    problems: list[str] = []
    bite = f["cell_lip_bite"]
    if not lo <= bite <= hi:
        problems.append(f"lip bite {bite:.2f} outside [{lo:g}, {hi:g}]")
    if f["cell_lip_h"] < 0.8:
        problems.append(f"lip band {f['cell_lip_h']:g} under 0.8")
    if problems:
        return _finding(check, False, "; ".join(problems),
                        measured=bite, limit=hi)
    return _finding(
        check, True,
        f"mouth bites the cell by {bite:.2f} inside [{lo:g}, {hi:g}], "
        f"lip band {f['cell_lip_h']:g}",
        measured=bite, limit=hi)


def check_cell_grid_webs_ok(form: PartForm) -> Finding:
    """Webs between pockets and to the block edge must stay real."""
    check = "form.cell_grid_webs_ok"
    f = form.frame
    if "cell_pitch" not in f:
        return _finding(check, True, "n/a — no cell pockets on this part",
                        critical=False)
    problems: list[str] = []
    web = f["cell_pitch"] - f["cell_pocket_d"]
    if web < CELL_WEB_MIN - 1e-6:
        problems.append(f"pocket-to-pocket web {web:.2f} < {CELL_WEB_MIN:g}")
    # edge web on the rect outline (grid extent + pocket radius)
    if "outline_u1" in f:
        nx, ny = f["cell_grid_nx"], f["cell_grid_ny"]
        pitch, r = f["cell_pitch"], f["cell_pocket_d"] / 2.0
        half_x = (nx - 1) * pitch / 2.0 + r
        half_y = (ny - 1) * pitch / 2.0 + r
        edge = min(f["outline_u1"] - half_x, f["outline_v1"] - half_y)
        if edge < CELL_WEB_MIN - 1e-6:
            problems.append(f"grid-to-edge web {edge:.2f} < {CELL_WEB_MIN:g}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    return _finding(
        check, True,
        f"webs {web:.2f} between pockets, grid clear of the edges",
        measured=web, limit=CELL_WEB_MIN)


register_probe("form.cell_lip_retains")(
    lambda form, ctx: check_cell_lip_retains(form))
register_probe("form.cell_grid_webs_ok")(
    lambda form, ctx: check_cell_grid_webs_ok(form))
