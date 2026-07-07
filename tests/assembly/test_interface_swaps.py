"""Wave A1 golden swap scenarios — the proof AF designs SYSTEMS of
compatible parts, not individual STLs.

1. Vertical farm cassette swap: the same water rail takes the coco
   cassette OR the sprout cassette; the rail is untouched.
2. Wearable adapter swap: the same cuff takes the flashlight clip OR the
   accessory plate adapter; the cuff is untouched.
Plus the mate/orphan findings the interface layer adds to validation.
"""

from pathlib import Path

import pytest

from artifact_forge_ng.assembly.pipeline import load_assembly
from artifact_forge_ng.assembly.swap import swap_part, verify_swap
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.core.findings import Status

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
VF_CELL = EXAMPLES / "vertical_farm" / "water_rail_cell_2020_petg.yaml"
CUFF_ASM = EXAMPLES / "wearables" / "cuff_flashlight_25.yaml"

PETG = {"material": "PETG", "support_policy": "none"}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


# -- driver 2: vertical farm cassette swap ----------------------------------

def test_vf_cassette_swaps_to_sprout(catalog):
    asm = load_assembly(VF_CELL)
    finding, summary = verify_swap(asm, "cassette", {
        "schema": "product/v1", "id": "sprout",
        "archetype": "sprout_cassette_v1@1", "params": {},
        "manufacturing": {**PETG, "bed": ["250mm", "250mm", "250mm"]},
    }, catalog=catalog)
    assert finding.status is Status.PASS, finding.message
    assert summary["parts"] == {"rail": "pass", "cassette": "pass",
                                "frame": "pass"}


def test_vf_swap_keeps_the_rail_untouched(catalog):
    asm = load_assembly(VF_CELL)
    swapped = swap_part(asm, "cassette", {
        "schema": "product/v1", "id": "sprout",
        "archetype": "sprout_cassette_v1@1", "params": {},
        "manufacturing": {**PETG, "bed": ["250mm", "250mm", "250mm"]},
    })
    assert swapped.part("rail").product == asm.part("rail").product
    assert swapped.part("frame").product == asm.part("frame").product


def test_vf_oversized_window_swap_fails_honestly(catalog):
    asm = load_assembly(VF_CELL)
    finding, _ = verify_swap(asm, "cassette", {
        "schema": "product/v1", "id": "wide",
        "archetype": "sprout_cassette_v1@1",
        "params": {"window_w": "20mm"},
        "manufacturing": {**PETG, "bed": ["250mm", "250mm", "250mm"]},
    }, catalog=catalog)
    assert finding.status is Status.FAIL
    assert "channel" in finding.message


# -- driver 1: wearable adapter swap ----------------------------------------

def test_cuff_adapter_swaps_to_plate(catalog):
    asm = load_assembly(CUFF_ASM)
    finding, summary = verify_swap(asm, "adapter", {
        "schema": "product/v1", "id": "plate",
        "archetype": "rail_plate_adapter_v1@1", "params": {},
        "manufacturing": PETG,
    }, catalog=catalog)
    assert finding.status is Status.PASS, finding.message
    assert summary["parts"]["cuff"] == "pass"


def test_cuff_swap_keeps_the_cuff_untouched(catalog):
    asm = load_assembly(CUFF_ASM)
    swapped = swap_part(asm, "adapter", {
        "schema": "product/v1", "id": "plate",
        "archetype": "rail_plate_adapter_v1@1", "params": {},
        "manufacturing": PETG,
    })
    assert swapped.part("cuff").product == asm.part("cuff").product


def test_desynced_groove_is_unrepresentable(catalog):
    """The shared block IS the standard: a swapped part carrying its own
    wrong groove numbers gets them overwritten by ``shared:`` — desync
    cannot even be expressed. (The genuinely local parameter, adapter
    length, CAN break the fit — and fails measurably.)"""
    asm = load_assembly(CUFF_ASM)
    finding, _ = verify_swap(asm, "adapter", {
        "schema": "product/v1", "id": "narrow",
        "archetype": "rail_plate_adapter_v1@1",
        "params": {"groove_top_w": "10mm", "groove_bottom_w": "14mm"},
        "manufacturing": PETG,
    }, catalog=catalog)
    assert finding.status is Status.PASS  # shared overwrote the desync

    finding, _ = verify_swap(asm, "adapter", {
        "schema": "product/v1", "id": "too_long",
        "archetype": "rail_plate_adapter_v1@1",
        "params": {"adapter_l": "120mm"},
        "manufacturing": PETG,
    }, catalog=catalog)
    assert finding.status is Status.FAIL
    assert "overhangs" in finding.message


# -- mate findings on the goldens -------------------------------------------

def _findings_of(path, catalog):
    from artifact_forge_ng.assembly.pipeline import (
        _inject_shared, _joint_findings)
    from artifact_forge_ng.pipeline import pre_cad_from_instance

    asm = load_assembly(path)
    instances = _inject_shared(asm, catalog)
    states = {r: pre_cad_from_instance(i, catalog, True)
              for r, i in instances.items()}
    findings, _, _ = _joint_findings(asm, states)
    return {f.check: f for f in findings}


def test_cuff_assembly_mates_via_port_ids(catalog):
    checks = _findings_of(CUFF_ASM, catalog)
    assert checks["interface.mate_compatible"].status is Status.PASS
    assert checks["interface.clearance_ok"].status is Status.PASS
    assert checks["assembly.no_orphan_ports"].status is Status.PASS
    assert checks["assembly.dovetail_ir"].status is Status.PASS


def test_vf_assembly_mates_pass(catalog):
    checks = _findings_of(VF_CELL, catalog)
    assert checks["interface.mate_compatible"].status is Status.PASS
    assert checks["assembly.no_orphan_ports"].status is Status.PASS


def test_wrong_port_is_incompatible_and_orphans_the_foot(catalog, tmp_path):
    import yaml

    doc = yaml.safe_load(CUFF_ASM.read_text())
    # aim the joint at the adapter's OTHER port: type mismatch + orphan foot
    doc["joints"][0]["b"] = "adapter.payload_seat"
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    checks = _findings_of(p, catalog)
    assert checks["interface.mate_compatible"].status is Status.FAIL
    assert "types differ" in checks["interface.mate_compatible"].message
    assert checks["assembly.no_orphan_ports"].status is Status.FAIL
    assert "mount_foot" in checks["assembly.no_orphan_ports"].message
