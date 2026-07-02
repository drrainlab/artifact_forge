"""The proof the topology probes are not rubber stamps: hand-built wrong
geometries (the historical failure modes) must FAIL against the flagship's
own frame — and the whole build pipeline must FAIL a mutated builder."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.archetypes import builder_for  # noqa: E402
from artifact_forge_ng.cad.geometry import Geometry  # noqa: E402
from artifact_forge_ng.catalog.loader import load_catalog, load_instance  # noqa: E402
from artifact_forge_ng.core.findings import Status  # noqa: E402
from artifact_forge_ng.product.resolve import resolve_params  # noqa: E402
from artifact_forge_ng.validators.topology import (  # noqa: E402
    asymmetric_lips_geometry,
    cavity_open,
    mouth_opens_sideways,
)

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = EXAMPLES / "desk_cable_clip_20mm.yaml"


@pytest.fixture(scope="module")
def flagship_form():
    catalog = load_catalog()
    instance = load_instance(GOLDEN)
    archetype = catalog.archetypes[instance.archetype_id]
    resolved = resolve_params(archetype, instance)
    return builder_for(archetype)(resolved, archetype, instance)


def symmetric_ring_solid(form) -> Geometry:
    """An annular C-ring with EQUAL short lips + flange — the failure mode
    the whole project exists to kill."""
    f = form.frame
    vc, r_i, r_o = f["cavity_center_v"], f["r_cavity"], f["r_outer"]
    m = f["mouth_half"]
    ring = (
        cq.Workplane("YZ")
        .center(0, vc)
        .circle(r_o)
        .circle(r_i)
        .extrude(form.width)
    )
    # symmetric mouth slot toward +Y
    slot = (
        cq.Workplane("YZ")
        .center(r_o / 2 + r_i / 2, vc)
        .rect(r_o * 2, 2 * m)
        .extrude(form.width)
    )
    ring = ring.cut(slot)
    plate = form.plates[0]
    flange = (
        cq.Workplane(
            "XY", origin=((plate.x0 + plate.x1) / 2, (plate.y0 + plate.y1) / 2, plate.z_bottom)
        )
        .rect(plate.x1 - plate.x0, plate.y1 - plate.y0)
        .extrude(plate.thickness)
    )
    neck = (
        cq.Workplane("XY", origin=(form.width / 2, -r_i * 0.3, vc + r_i))
        .rect(form.width, 3 * form.params["wall"])
        .extrude(-(vc + r_i) + 1.0)
    )
    return Geometry(ring.union(flange).union(neck))


def test_symmetric_c_ring_fails_asymmetry_probe(flagship_form):
    geometry = symmetric_ring_solid(flagship_form)
    finding = asymmetric_lips_geometry(geometry, flagship_form)
    assert finding.status is Status.FAIL, finding.message


def test_solid_block_fails_cavity_and_mouth(flagship_form):
    lo, hi = flagship_form.section.outer.bbox()
    block = Geometry(
        cq.Workplane("YZ")
        .center((lo.u + hi.u) / 2, (lo.v + hi.v) / 2)
        .rect(hi.u - lo.u, hi.v - lo.v)
        .extrude(flagship_form.width)
    )
    assert cavity_open(block, flagship_form).status is Status.FAIL
    assert mouth_opens_sideways(block, flagship_form).status is Status.FAIL


def test_correct_flagship_passes_probes(flagship_form):
    from artifact_forge_ng.compiler.solids import compile_part

    geometry, _ = compile_part(flagship_form)
    assert asymmetric_lips_geometry(geometry, flagship_form).status is Status.PASS
    assert cavity_open(geometry, flagship_form).status is Status.PASS
    assert mouth_opens_sideways(geometry, flagship_form).status is Status.PASS


class TestMutationHonesty:
    """Swap the generator for a symmetric ring: the CLI must fail loudly
    with the forbidden form named — score cannot mask it."""

    def test_forge_build_fails_on_symmetric_generator(self, tmp_path, monkeypatch):
        from artifact_forge_ng.compiler import solids as solids_module
        from artifact_forge_ng.compiler.pipeline import run_build
        from artifact_forge_ng.pipeline import PipelineFailure

        real_compile = solids_module.compile_part

        def sabotaged_compile(form):
            geometry = symmetric_ring_solid(form)
            _, log = real_compile(form)
            return geometry, log

        monkeypatch.setattr(
            "artifact_forge_ng.compiler.pipeline.compile_part", sabotaged_compile
        )
        with pytest.raises(PipelineFailure) as exc_info:
            run_build(GOLDEN, tmp_path, strict_flag=None)
        message = str(exc_info.value)
        assert "asymmetric_lips_geometry" in message or "must_have" in message
