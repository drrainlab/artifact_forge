"""Sideprint variant, geometry level: the exported solid stands profile-on-
bed with the extrusion axis vertical, sections really are constant, and the
support-free feature is validator-built."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.probes import box_probe, solid_fraction  # noqa: E402
from artifact_forge_ng.compiler.pipeline import orient_for_print, run_build  # noqa: E402
from artifact_forge_ng.compiler.solids import compile_part  # noqa: E402
from artifact_forge_ng.pipeline import run_pre_cad  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
SIDEPRINT = EXAMPLES / "desk_cable_clip_20mm_sideprint.yaml"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("sideprint")
    return run_build(SIDEPRINT, out, None)


def test_build_passes_with_support_free_feature(built):
    assert built["score"]["status"] == "pass"
    assert "support_free_by_construction" in built["honesty_report"]["built_features"]
    assert "rear_mounting_tongue" in built["honesty_report"]["built_features"]
    assert built["exports"]["print_orientation"] == "side_profile"


def test_export_is_rotated_onto_the_bed():
    """The exported orientation: profile on the bed (footprint = section
    bbox), extrusion axis up (height = width), floor at z = 0. Validators
    keep measuring the UNROTATED part frame."""
    state = run_pre_cad(SIDEPRINT, False)
    form = state.form
    geometry, _ = compile_part(form)
    part_bb = geometry.bounding_box()
    oriented = orient_for_print(geometry, form)
    bb = oriented.bounding_box()
    assert bb.height == pytest.approx(form.width, abs=0.2)
    assert bb.zmin == pytest.approx(0.0, abs=1e-6)
    # the section's (y, z) extents become the bed footprint
    assert sorted((round(bb.width), round(bb.depth))) == sorted(
        (round(part_bb.depth), round(part_bb.height))
    )


def test_sections_identical_along_print_axis():
    """No overhangs by construction MEANS every layer is the same shape:
    material fractions of full-footprint slabs at different heights match
    (away from the transverse screw-hole band)."""
    state = run_pre_cad(SIDEPRINT, False)
    form = state.form
    geometry, _ = compile_part(form)
    oriented = orient_for_print(geometry, form)
    bb = oriented.bounding_box()

    def slab(z0: float, z1: float) -> float:
        probe = box_probe(bb.xmin, bb.ymin, z0, bb.xmax, bb.ymax, z1)
        return solid_fraction(oriented.workplane, probe)

    # screw holes sit at z = width/2; sample clear of them
    a = slab(2.0, 5.0)
    b = slab(form.width - 5.0, form.width - 2.0)
    assert a == pytest.approx(b, rel=0.03)
    assert a > 0.05  # sanity: the slabs actually contain material
