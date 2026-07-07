"""Wave P2 forearm cuff, tier-2 (CAD): the golden example compiles into
one valid solid — arm cavity void, payload cylinder void with its upward
mouth window pierced, all four strap slots really cut — and the sideprint
orientation keeps the build support-free (overhang never FAILs)."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.catalog.loader import load_catalog, load_instance  # noqa: E402
from artifact_forge_ng.compiler.solids import compile_part  # noqa: E402
from artifact_forge_ng.core.findings import Status  # noqa: E402
from artifact_forge_ng.pipeline import pre_cad_from_instance  # noqa: E402
from artifact_forge_ng.validators.runner import run_geometry_validators  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = EXAMPLES / "forearm_flashlight_cuff.yaml"


@pytest.fixture(scope="module")
def built():
    catalog = load_catalog()
    instance = load_instance(GOLDEN)
    state = pre_cad_from_instance(instance, catalog, True)
    assert state.form is not None
    geometry, log = compile_part(state.form)
    findings = run_geometry_validators(state, geometry)
    return state, geometry, log, {f.check: f for f in findings}


def test_single_valid_solid(built):
    _, _, _, checks = built
    assert checks["topology.single_connected_solid"].status is Status.PASS


def test_arm_cavity_and_payload_voids(built):
    _, _, _, checks = built
    assert checks["topology.cavity_open"].status is Status.PASS
    assert checks["topology.payload_void_open"].status is Status.PASS


def test_strap_slots_really_cut(built):
    state, _, log, checks = built
    slots = [c for c in state.form.cutboxes if c.name.startswith("strap_slot")]
    assert len(slots) == 4
    assert checks["topology.cutout_present"].status is Status.PASS


def test_sideprint_stays_support_free(built):
    _, _, _, checks = built
    overhang = checks.get("manufacturing.overhang")
    assert overhang is not None
    assert overhang.status is not Status.FAIL


def test_keepouts_survive_the_build(built):
    _, _, _, checks = built
    assert checks["region.keepouts_preserved"].status is Status.PASS
