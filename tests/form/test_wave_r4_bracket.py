"""Wave R4 (strength/assembly), tier-1: the loft taper is a hard IR rule,
gussets are welded ribs, screws land beyond the gussets."""

from pathlib import Path

import pytest

from artifact_forge_ng.form.part import LoftFeature
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture(scope="module")
def state():
    return run_pre_cad(EXAMPLES / "shelf_bracket_150.yaml", None)


def test_bracket_ir_green(state):
    fails = [f for f in state.report.findings if f.status.value == "fail"]
    assert fails == []
    form = state.form
    assert len(form.lofts) == 1
    assert {r.name for r in form.ribs} == {"gusset_pos", "gusset_neg"}


def test_taper_is_enforced_by_construction():
    with pytest.raises(ValueError, match="must taper"):
        LoftFeature(
            name="mushroom", base_center=(0, 0), z0=5.0, length=100.0,
            root=(20.0, 20.0), tip=(30.0, 20.0),
        )


def test_screws_clear_the_gussets(state):
    form = state.form
    g_extent = max(abs(r.box.y0) for r in form.ribs) if form.ribs else 0.0
    g_extent = max(g_extent, max(abs(r.box.y1) for r in form.ribs))
    for hole in form.holes:
        head_r = form.frame["screw_head_r"]
        assert abs(hole.at[1]) - head_r > g_extent, (
            "screw head overlaps a gusset — a driver cannot seat it"
        )


def test_arm_root_welds_into_plate(state):
    loft = state.form.lofts[0]
    plate_t = state.form.width
    assert loft.z0 < plate_t  # weld overlap, the v1 lip-overlap lesson
    assert state.form.frame["arm_tip_z"] == pytest.approx(
        loft.z0 + loft.length
    )
