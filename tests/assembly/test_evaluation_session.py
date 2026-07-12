"""AssemblyEvaluationSession — content-addressed per-job memoization.

The invariants that matter: identical work is never redone inside one
session; a change invalidates exactly its own node and the dependents;
cached and uncached reports are structurally identical; a different
catalog object is a full miss.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from artifact_forge_ng.assembly.evaluation import (
    AssemblyEvaluationSession,
    EvaluationCache,
)
from artifact_forge_ng.assembly.pipeline import load_assembly
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.product.assembly import AssemblyInstance

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
ESP32 = EXAMPLES / "esp32_box_with_lid.yaml"


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture()
def asm():
    return load_assembly(ESP32)


@pytest.fixture()
def counting(monkeypatch):
    """Count real pre-CAD builds behind the session."""
    import artifact_forge_ng.assembly.evaluation as evaluation
    real = evaluation.pre_cad_from_instance
    calls = {"n": 0}

    def counted(instance, catalog, strict):
        calls["n"] += 1
        return real(instance, catalog, strict)

    monkeypatch.setattr(evaluation, "pre_cad_from_instance", counted)
    return calls


def _mutated(asm: AssemblyInstance, mutate) -> AssemblyInstance:
    doc = asm.model_dump(by_alias=True, mode="json")
    mutate(doc)
    return AssemblyInstance.model_validate(doc)


def test_identical_revalidation_is_fully_cached(catalog, asm, counting):
    session = AssemblyEvaluationSession(catalog)
    first = session.validate(asm, strict_flag=False)
    built = counting["n"]
    assert built == len(asm.parts)
    again = session.validate(asm, strict_flag=False)
    assert counting["n"] == built, "identical revalidation rebuilt a part"
    assert session.last_stats["parts_built"] == 0
    assert session.last_stats["joints_checked"] == 0
    assert again == first


def test_joint_change_does_not_rebuild_part_forms(catalog, asm, counting):
    session = AssemblyEvaluationSession(catalog)
    session.validate(asm, strict_flag=False)
    built = counting["n"]
    changed = _mutated(
        asm, lambda d: d["joints"][1]["params"].update({"count": 4}))
    session.validate(changed, strict_flag=False)
    assert counting["n"] == built, "a joint edit must not rebuild Form IR"
    assert session.last_stats["parts_built"] == 0
    # only the edited joint re-ran; the others came from cache
    assert session.last_stats["joints_checked"] == 1


def test_param_change_invalidates_only_that_part(catalog, asm, counting):
    session = AssemblyEvaluationSession(catalog)
    session.validate(asm, strict_flag=False)
    built = counting["n"]

    def bump_lid(doc):
        doc["parts"][1]["product"]["params"]["lid_t"] = "3.2mm"

    session.validate(_mutated(asm, bump_lid), strict_flag=False)
    assert counting["n"] == built + 1, "exactly one part rebuilds"
    assert session.last_stats["parts_built"] == 1
    assert session.last_stats["parts_cached"] == len(asm.parts) - 1
    # every joint touching the lid re-runs (its form fingerprint changed)
    assert session.last_stats["joints_checked"] >= 1


def test_modifier_change_invalidates_only_that_part(catalog, asm, counting):
    session = AssemblyEvaluationSession(catalog)
    session.validate(asm, strict_flag=False)
    built = counting["n"]

    def add_modifier(doc):
        doc["parts"][0]["product"]["modifiers"] = [
            {"id": "add_hex_perforation", "target": "floor"}]

    changed = _mutated(asm, add_modifier)
    session.validate(changed, strict_flag=False)
    assert counting["n"] == built + 1
    assert session.last_stats["parts_built"] == 1


def test_broken_chain_order_fails_even_on_cached_joints(catalog, asm):
    """Ordering guards are graph logic, recomputed every pass — a cached
    joint result must not smuggle a mis-ordered chain through."""
    session = AssemblyEvaluationSession(catalog)
    session.validate(asm, strict_flag=False)

    def reorder(doc):
        # first joint now hangs off a part that is not posed yet
        doc["joints"] = [
            {"type": "screw_joint", "a": "lid.seat", "b": "box.rim",
             "rotate": [180, 0, 0], "params": {"screw": "M3", "count": 2}},
        ] + doc["joints"]

    out = session.validate(_mutated(asm, reorder), strict_flag=False)
    assert out["status"] == "fail"
    assert any("not posed yet" in j["message"] for j in out["joints"])


def test_different_catalog_object_is_a_full_miss(asm, counting):
    shared = EvaluationCache()
    cat1 = load_catalog()
    AssemblyEvaluationSession(cat1, cache=shared).validate(
        asm, strict_flag=False)
    built = counting["n"]
    cat2 = load_catalog()
    assert cat2 is not cat1
    session2 = AssemblyEvaluationSession(cat2, cache=shared)
    session2.validate(asm, strict_flag=False)
    assert counting["n"] == built + len(asm.parts), \
        "a different catalog object must not reuse cached forms"


def test_cached_report_equals_uncached_report(catalog, asm):
    from artifact_forge_ng.assembly.pipeline import validate_assembly_doc
    session = AssemblyEvaluationSession(catalog)
    session.validate(asm, strict_flag=False)          # warm
    cached = session.validate(asm, strict_flag=False)  # fully cached
    fresh = validate_assembly_doc(asm, catalog, False)
    assert cached == fresh


def test_repair_style_attempts_report_stats(catalog, asm, counting):
    session = AssemblyEvaluationSession(catalog)
    session.validate(asm, strict_flag=False)
    line1 = session.stats_line(1)
    assert "parts 0 cached" in line1

    changed = _mutated(
        asm, lambda d: d["parts"][1]["product"]["params"].update(
            {"lid_t": "3.2mm"}))
    session.validate(changed, strict_flag=False)
    line2 = session.stats_line(2)
    assert f"parts {len(asm.parts) - 1} cached / 1 rebuilt" in line2

    session.validate(changed, strict_flag=False)
    line3 = session.stats_line(3)
    assert "0 rebuilt" in line3 and "0 rechecked" in line3
