"""Bio-1 split branch clamp, tier-2 (CAD): both halves compile into one
valid solid each — saddle void open, channel bored end to end, pockets
blind, cord slots cut, rail really present — and the assembled pair keeps
the compression gap with no interference. Support-free: overhang is at
worst a WARN in the side-profile orientation."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.assembly.pipeline import run_assembly_build  # noqa: E402
from artifact_forge_ng.cad.probes import channel_probe, solid_fraction  # noqa: E402
from artifact_forge_ng.catalog.loader import load_catalog  # noqa: E402
from artifact_forge_ng.compiler.solids import compile_part  # noqa: E402
from artifact_forge_ng.core.findings import Status  # noqa: E402
from artifact_forge_ng.pipeline import pre_cad_from_instance  # noqa: E402
from artifact_forge_ng.product.instance import ProductInstance  # noqa: E402
from artifact_forge_ng.validators.runner import run_geometry_validators  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
CLAMP = EXAMPLES / "branch_lamp_clamp_60.yaml"

SHARED = {"nominal_branch_d": "60mm", "clamp_w": "40mm",
          "compression_gap": "3mm", "screw": "M4"}


def _built_half(archetype: str):
    catalog = load_catalog()
    instance = ProductInstance.model_validate({
        "schema": "product/v1", "id": f"cad_{archetype}",
        "archetype": f"{archetype}@1", "params": dict(SHARED),
        "manufacturing": {"material": "PETG", "support_policy": "none"},
    })
    state = pre_cad_from_instance(instance, catalog, True)
    assert state.form is not None
    geometry, _ = compile_part(state.form)
    return state, geometry


@pytest.fixture(scope="module")
def lower():
    return _built_half("branch_clamp_lower_v1")


@pytest.fixture(scope="module")
def upper():
    return _built_half("branch_clamp_upper_v1")


@pytest.fixture(scope="module")
def assembly(tmp_path_factory):
    out = tmp_path_factory.mktemp("clamp")
    return run_assembly_build(CLAMP, out, None), out


def _geometry_fails(state, geometry):
    findings = run_geometry_validators(state, geometry)
    return findings, [f"{f.check}: {f.message}" for f in findings
                      if f.status is Status.FAIL]


def test_lower_half_geometry_validators(lower):
    state, geometry = lower
    findings, fails = _geometry_fails(state, geometry)
    assert not fails, fails
    passed = {f.check for f in findings if f.status is Status.PASS}
    assert {"topology.cavity_open", "topology.single_connected_solid",
            "topology.pockets_present", "topology.cutout_present",
            "region.keepouts_preserved"} <= passed
    # support-free by construction: overhang never worse than WARN
    overhang = [f for f in findings if f.check == "manufacturing.overhang"]
    assert overhang and all(f.status is not Status.FAIL for f in overhang)


def test_upper_half_geometry_validators(upper):
    state, geometry = upper
    findings, fails = _geometry_fails(state, geometry)
    assert not fails, fails
    passed = {f.check for f in findings if f.status is Status.PASS}
    assert {"topology.cavity_open", "topology.single_connected_solid",
            "topology.rail_present", "topology.bores_open",
            "topology.screw_holes_open", "topology.countersinks_present",
            "topology.pockets_present", "region.keepouts_preserved"} <= passed
    overhang = [f for f in findings if f.check == "manufacturing.overhang"]
    assert overhang and all(f.status is not Status.FAIL for f in overhang)


def test_branch_cylinder_really_fits_each_saddle(lower, upper):
    """Direct probe, independent of the validators: a 58 mm cylinder along
    the branch axis passes through each half's open saddle."""
    for state, geometry in (lower, upper):
        f = state.form.frame
        probe = channel_probe(
            [(-2.0, 0.0, f["saddle_cz"]),
             (state.form.width + 2.0, 0.0, f["saddle_cz"])],
            d=58.0,
        )
        assert solid_fraction(geometry.workplane, probe) < 0.02


def test_cable_channel_is_a_real_void(upper):
    state, geometry = upper
    f = state.form.frame
    probe = channel_probe(
        [(-2.0, 0.0, f["channel_z"]),
         (state.form.width + 2.0, 0.0, f["channel_z"])],
        d=0.8 * f["channel_d"],
    )
    assert solid_fraction(geometry.workplane, probe) < 0.02


def test_assembly_definition_of_done(assembly):
    report, out = assembly
    assert report["status"] == "pass"
    checks = {j["check"]: j["status"] for j in report["joints"]}
    assert checks["assembly.screw_joint_ir"] == "pass"
    assert checks["assembly.clamp_gap_ir"] == "pass"
    assert checks["assembly.no_interference"] == "pass"
    assert checks["assembly.screw_axes_clear"] == "pass"
    assert set(report["built_features"]) == {
        "bolted_interface", "compression_clamp_interface"}
    base = out / "branch_lamp_clamp_60"
    assert (base / "lower" / "part.stl").exists()
    assert (base / "upper" / "part.stl").exists()
    assert (base / "assembled.step").exists()
    for part in report["parts"].values():
        assert part["status"] == "pass"
