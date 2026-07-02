"""Capability resolver — requested vs supported vs BUILT, honestly.

The anti-hallucination layer. ``supported`` derives from the archetype and
the instance's modifiers; ``built`` can only be written by
:func:`mark_built`, which requires every validator in the feature's
``verified_by`` list to have PASSed. The schema itself enforces
``built ⊆ supported`` (with ``validate_assignment`` on), so an unsupported
feature literally cannot be serialized as built — even by a hand-built
report.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from ..core.findings import ValidationReport
from .archetype import ArchetypeSpec
from .instance import ProductInstance
from .modifier import ModifierDef


class FeatureDef(BaseModel):
    """One entry of the feature vocabulary (catalog/data/features.yaml)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str = ""
    #: Validator checks that must ALL pass for the feature to count as built.
    verified_by: list[str] = []


class EngineGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_or_check: str
    suggestion: str = ""
    survived_repairs: int = 0


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    requested_features: list[str] = []
    supported_features: list[str] = []
    unsupported_features: list[str] = []
    built_features: list[str] = []
    missing_features: list[str] = []
    buildable: bool = True
    engine_gaps: list[EngineGap] = []

    @model_validator(mode="after")
    def _honesty_invariants(self) -> "CapabilityReport":
        supported = set(self.supported_features)
        illegal = [f for f in self.built_features if f not in supported]
        if illegal:
            raise ValueError(
                f"built_features not in supported_features: {illegal} — "
                "an unsupported feature can never be marked built"
            )
        overlap = set(self.built_features) & set(self.missing_features)
        if overlap:
            raise ValueError(f"features both built and missing: {sorted(overlap)}")
        return self


def resolve_capability(
    instance: ProductInstance,
    archetype: ArchetypeSpec,
    modifiers: dict[str, ModifierDef],
    vocabulary: dict[str, FeatureDef],
) -> CapabilityReport:
    """Pre-build capability: what is requested, what the engine supports.

    ``modifiers`` maps modifier id -> definition for the instance's (already
    catalog-validated) modifier uses. Unknown requested feature ids are
    treated as unsupported engine gaps, not errors — the honest answer to
    "I want a living hinge" is a gap, not a crash.
    """
    supported: list[str] = list(archetype.provides_features)
    for use in instance.modifiers:
        mod = modifiers.get(use.id)
        if mod is not None:
            supported.extend(f for f in mod.provides_features if f not in supported)

    requested = list(instance.requested_features)
    unsupported = [f for f in requested if f not in supported]
    gaps = [
        EngineGap(
            feature_or_check=f,
            suggestion=(
                f"no generator/modifier provides {f!r}"
                if f in vocabulary
                else f"{f!r} is not in the feature vocabulary"
            ),
        )
        for f in unsupported
    ]
    return CapabilityReport(
        requested_features=requested,
        supported_features=supported,
        unsupported_features=unsupported,
        buildable=not unsupported,
        engine_gaps=gaps,
    )


def mark_built(
    report: CapabilityReport,
    validation: ValidationReport,
    vocabulary: dict[str, FeatureDef],
) -> CapabilityReport:
    """Post-build honesty: a feature is built iff ALL of its ``verified_by``
    validators PASSed. Nothing else writes ``built_features``."""
    built: list[str] = []
    missing: list[str] = []
    for feature_id in report.supported_features:
        feature = vocabulary.get(feature_id)
        if feature is None or not feature.verified_by:
            # No verification defined: never claim it silently.
            missing.append(feature_id)
            continue
        if all(validation.passed(check) for check in feature.verified_by):
            built.append(feature_id)
        else:
            missing.append(feature_id)
    # model_copy(update=...) skips validation in pydantic v2 — go through
    # model_validate so the built ⊆ supported invariant actually re-runs.
    return CapabilityReport.model_validate(
        {**report.model_dump(), "built_features": built, "missing_features": missing}
    )
