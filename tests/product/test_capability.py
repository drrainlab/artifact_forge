"""Capability honesty: supported derives from archetype+modifiers; built is
validator-gated; the schema itself rejects unsupported-marked-built."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.core.findings import Finding, Level, Status, ValidationReport
from artifact_forge_ng.product.capability import (
    CapabilityReport,
    mark_built,
    resolve_capability,
)

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture(scope="module")
def setup():
    catalog = load_catalog()
    instance = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
    archetype = catalog.archetypes[instance.archetype_id]
    return catalog, instance, archetype


def test_supported_includes_modifier_features(setup):
    catalog, instance, archetype = setup
    report = resolve_capability(
        instance, archetype, catalog.modifiers_for(instance), catalog.features
    )
    assert "countersunk_screw_holes" in report.supported_features
    assert "hex_perforation" in report.supported_features
    assert report.buildable
    assert report.unsupported_features == []


def test_unsupported_requested_feature_is_gap_not_crash(setup):
    catalog, instance, archetype = setup
    inst = instance.model_copy(
        update={"requested_features": ["asymmetric_side_hook", "living_hinge"]}
    )
    report = resolve_capability(
        inst, archetype, catalog.modifiers_for(inst), catalog.features
    )
    assert report.unsupported_features == ["living_hinge"]
    assert not report.buildable
    assert any(g.feature_or_check == "living_hinge" for g in report.engine_gaps)


def test_schema_rejects_unsupported_marked_built():
    with pytest.raises(ValidationError, match="never be marked built"):
        CapabilityReport(
            supported_features=["a"],
            built_features=["a", "ghost_feature"],
        )


def test_schema_rejects_built_and_missing_overlap():
    with pytest.raises(ValidationError, match="both built and missing"):
        CapabilityReport(
            supported_features=["a"],
            built_features=["a"],
            missing_features=["a"],
        )


def _passing(check: str) -> Finding:
    return Finding(check=check, status=Status.PASS, level=Level.FORM, message="ok")


def test_mark_built_requires_all_verifiers(setup):
    catalog, instance, archetype = setup
    report = resolve_capability(
        instance, archetype, catalog.modifiers_for(instance), catalog.features
    )
    feature = catalog.features["retaining_lower_lip"]  # one verifier
    validation = ValidationReport(
        findings=[_passing(check) for check in feature.verified_by]
    )
    marked = mark_built(report, validation, catalog.features)
    assert "retaining_lower_lip" in marked.built_features
    # Everything whose verifiers did NOT run is honestly missing.
    assert "asymmetric_side_hook" in marked.missing_features


def test_mark_built_fails_feature_on_one_failing_verifier(setup):
    catalog, instance, archetype = setup
    report = resolve_capability(
        instance, archetype, catalog.modifiers_for(instance), catalog.features
    )
    feature = catalog.features["asymmetric_side_hook"]
    findings = [_passing(c) for c in feature.verified_by[:-1]]
    findings.append(
        Finding(
            check=feature.verified_by[-1],
            status=Status.FAIL,
            level=Level.TOPOLOGY,
            message="broken",
        )
    )
    marked = mark_built(report, ValidationReport(findings=findings), catalog.features)
    assert "asymmetric_side_hook" in marked.missing_features
    assert "asymmetric_side_hook" not in marked.built_features
