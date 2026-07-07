"""Wall Tool Mounts Pack v1, tier-2: the grinder example compiles into one
valid solid — saddle void, mouth window open, anchors bored and recessed,
gussets welded, voronoi field cut without touching a keepout — and exports
upright (section on the bed)."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.probes import box_probe, channel_probe, solid_fraction  # noqa: E402
from artifact_forge_ng.compiler.pipeline import orient_for_print  # noqa: E402
from artifact_forge_ng.compiler.solids import compile_part  # noqa: E402
from artifact_forge_ng.core.findings import Status  # noqa: E402
from artifact_forge_ng.pipeline import run_pre_cad  # noqa: E402
from artifact_forge_ng.validators.runner import run_geometry_validators  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GRINDER = EXAMPLES / "wall_tool_mount_grinder_65.yaml"


@pytest.fixture(scope="module")
def built():
    state = run_pre_cad(GRINDER, None)
    assert state.form is not None
    geometry, log = compile_part(state.form)
    return state, geometry, log


def test_compiles_one_valid_solid(built):
    _, geometry, log = built
    assert geometry.solid_count() == 1
    assert geometry.is_valid()
    assert log.holes_bored == 2
    assert log.holes_countersunk == 2
    assert log.ribs_welded == 2
    assert log.field_cut


def test_geometry_validators_pass(built):
    state, geometry, _ = built
    findings = run_geometry_validators(state, geometry)
    fails = [f"{f.check}: {f.message}" for f in findings if f.status is Status.FAIL]
    assert not fails, fails
    passed = {f.check for f in findings if f.status is Status.PASS}
    assert {"topology.tool_void_open", "topology.screw_holes_open",
            "topology.countersinks_present", "topology.ribs_present",
            "topology.single_connected_solid", "topology.hex_field_present",
            "region.keepouts_preserved"} <= passed


def test_tool_cylinder_really_fits(built):
    """Direct probe, independent of the validator: a 65 mm cylinder along
    the tool axis must pass through the saddle."""
    state, geometry, _ = built
    f = state.form.frame
    probe = channel_probe(
        [(-2.0, 0.0, f["saddle_cz"]), (state.form.width + 2.0, 0.0, f["saddle_cz"])],
        d=65.0,
    )
    assert solid_fraction(geometry.workplane, probe) < 0.02


def test_saddle_flanks_are_solid(built):
    """The C-ring around the cavity is real material on both sides."""
    state, geometry, _ = built
    f = state.form.frame
    mid_r = (f["saddle_r"] + f["r_outer"]) / 2.0
    for side in (-1.0, 1.0):
        band = box_probe(
            2.0, side * mid_r - 1.5, f["saddle_cz"] - 2.0,
            state.form.width - 2.0, side * mid_r + 1.5, f["saddle_cz"] + 2.0,
        )
        assert solid_fraction(geometry.workplane, band) > 0.9


def test_export_orientation_stands_on_the_bed(built):
    state, geometry, _ = built
    oriented = orient_for_print(geometry, state.form)
    bb = oriented.bounding_box()
    assert abs(bb.zmin) < 1e-6
    # upright: the flange height (125) is the tallest dimension
    assert bb.zmax - bb.zmin == pytest.approx(125.0, abs=2.0)
