"""Assembly schema + joint IR, tier-1: fail-fast names, shared injection,
and the screw joint catching real desync BEFORE any CAD."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.joints import JOINT_TYPES, compute_pose
from artifact_forge_ng.assembly.pipeline import (
    load_assembly,
    run_assembly_validate,
    validate_assembly,
    _inject_shared,
)
from artifact_forge_ng.catalog.loader import CatalogError, load_catalog
from artifact_forge_ng.pipeline import PipelineFailure
from artifact_forge_ng.product.assembly import AssemblyInstance

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
LAMP = EXAMPLES / "desk_lamp_e27.yaml"


@pytest.fixture(scope="module")
def lamp_doc():
    return yaml.safe_load(LAMP.read_text())


def test_lamp_assembly_validates_without_cad():
    out = run_assembly_validate(LAMP, None)
    assert out["status"] == "pass"
    assert out["root"] == "bracket"
    joint_checks = {j["check"]: j["status"] for j in out["joints"]}
    assert joint_checks["assembly.screw_joint_ir"] == "pass"
    poses = {p["part"] for p in out["assembly_pose"]}
    assert poses == {"bracket", "cup"}
    cup_pose = next(p for p in out["assembly_pose"] if p["part"] == "cup")
    assert cup_pose["derived_from"] == "screw_joint_0"
    assert cup_pose["rotate"] == [180.0, 0.0, 0.0]


def test_shared_parameters_reach_both_parts(lamp_doc):
    catalog = load_catalog()
    asm = AssemblyInstance.model_validate(lamp_doc)
    instances = _inject_shared(asm, catalog)
    assert instances["bracket"].params["mount_bc"] == "24mm"
    assert instances["cup"].params["mount_bc"] == "24mm"


def test_unknown_joint_type_fails_fast(lamp_doc):
    doc = yaml.safe_load(LAMP.read_text())
    doc["joints"][0]["type"] = "quantum_entanglement"
    asm = AssemblyInstance.model_validate(doc)
    with pytest.raises(CatalogError, match="unknown joint type"):
        validate_assembly(asm, load_catalog())


def test_schema_guards(lamp_doc):
    for mutate, match in (
        (lambda d: d.update(root="nonexistent"), "root"),
        (lambda d: d.update(joints=[]), "at least one joint"),
        (lambda d: d["joints"][0].update(rotate=[45, 0, 0]), "90-degree"),
        (lambda d: d["joints"][0].update(a="cup.mount_face",
                                         b="cup.mount_face"), "DIFFERENT"),
    ):
        doc = yaml.safe_load(LAMP.read_text())
        mutate(doc)
        with pytest.raises(Exception, match=match):
            AssemblyInstance.model_validate(doc)


def test_desynced_mount_bc_dies_before_cad(tmp_path):
    """The whole point of shared: without it, a mismatched bolt circle is a
    real desync — the joint IR must kill it at validate time."""
    doc = yaml.safe_load(LAMP.read_text())
    del doc["shared"]["mount_bc"]
    # both values are individually legal — ONLY the joint can see the desync
    doc["parts"][0]["product"]["params"]["mount_bc"] = "20mm"
    doc["parts"][1]["product"]["params"]["mount_bc"] = "24mm"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(doc, sort_keys=False))
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_validate(bad, None)
    assert "joint" in str(exc_info.value)
    assert exc_info.value.code == 4


def test_missing_datum_is_honest(tmp_path):
    doc = yaml.safe_load(LAMP.read_text())
    doc["joints"][0]["a"] = "bracket.warp_nacelle"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(doc, sort_keys=False))
    with pytest.raises(PipelineFailure):
        run_assembly_validate(bad, None)


def test_count_mismatch_fails(tmp_path):
    doc = yaml.safe_load(LAMP.read_text())
    doc["parts"][1]["product"]["params"]["screw_count"] = 3
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(doc, sort_keys=False))
    with pytest.raises(PipelineFailure) as exc_info:
        run_assembly_validate(bad, None)
    assert exc_info.value.code == 4


def test_registry_declares_the_contract():
    for name, decl in JOINT_TYPES.items():
        assert decl.cad_checks, f"joint {name!r} declares no CAD probes"
        assert decl.ir_check is not None
