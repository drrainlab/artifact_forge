"""VF golden swap scenarios and mate findings (moved from core at the
R0.5 extraction — they exercise the pack's rail/cassette archetypes)."""

from pathlib import Path

import pytest

from artifact_forge_ng.assembly.pipeline import load_assembly
from artifact_forge_ng.assembly.swap import swap_part, verify_swap
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.core.findings import Status

EXAMPLES = Path(__file__).parents[1] / "examples"
VF_CELL = EXAMPLES / "vertical_farm" / "water_rail_cell_2020_petg.yaml"

PETG = {"material": "PETG", "support_policy": "none"}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


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

# -- driver 2: vertical farm cassette swap ----------------------------------

def test_vf_cassette_swaps_to_sprout(catalog):
    asm = load_assembly(VF_CELL)
    finding, summary = verify_swap(asm, "cassette", {
        "schema": "product/v1", "id": "sprout",
        "archetype": "sprout_cassette_v1@1", "params": {},
        "manufacturing": {**PETG, "bed": ["250mm", "250mm", "250mm"]},
    }, catalog=catalog)
    assert finding.status is Status.PASS, finding.message
    # the retainer frame carries an honest WARN (ring-centered port datum
    # — normal_points_outward cannot see material behind a void center)
    assert all(v in ("pass", "warn") for v in summary["parts"].values()), \
        summary["parts"]


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



def test_vf_assembly_mates_pass(catalog):
    checks = _findings_of(VF_CELL, catalog)
    assert checks["interface.mate_compatible"].status is Status.PASS
    assert checks["assembly.no_orphan_ports"].status is Status.PASS



# -- A1.5: frame opposition + auxiliary joints -------------------------------

def test_mate_frames_opposed_on_the_goldens(catalog):
    for path in (VF_CELL,):
        checks = _findings_of(path, catalog)
        f = checks.get("interface.mate_frames_opposed")
        assert f is not None and f.status is Status.PASS, path


def test_flipped_line_module_fails_frames(catalog, tmp_path):
    import yaml

    src = EXAMPLES / "vertical_farm" / "two_cell_line_petg.yaml"
    doc = yaml.safe_load(src.read_text())
    joint = next(j for j in doc["joints"] if j["type"] == "tongue_groove")
    joint["rotate"] = [0, 0, 180]
    p = tmp_path / "flipped.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    checks = _findings_of(p, catalog)
    f = checks["interface.mate_frames_opposed"]
    assert f.status is Status.FAIL
    assert "not opposed" in f.message or "up" in f.message

