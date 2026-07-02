"""Catalog loading — YAML documents -> validated pydantic models, with
FAIL-FAST name binding: every check name, feature id, forbidden form,
modifier reference and region id is resolved at load time. An unknown name
is a :class:`CatalogError`, never a silent skip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..core.values import parse_value
from ..product.archetype import ArchetypeSpec
from ..product.capability import FeatureDef
from ..product.instance import ModifierUse, ProductInstance
from ..product.modifier import ModifierDef
from ..validators.probes import FORBIDDEN_FORM_DETECTORS, known_check

DATA_DIR = Path(__file__).parent / "data"


class CatalogError(ValueError):
    """A catalog document failed validation or name binding."""


def _load_yaml(path: Path) -> Any:
    try:
        with path.open() as fh:
            return yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise CatalogError(f"{path.name}: not valid YAML: {exc}") from exc


@dataclass
class Catalog:
    features: dict[str, FeatureDef] = field(default_factory=dict)
    modifiers: dict[str, ModifierDef] = field(default_factory=dict)
    archetypes: dict[str, ArchetypeSpec] = field(default_factory=dict)

    def archetype_for(self, instance: ProductInstance) -> ArchetypeSpec:
        spec = self.archetypes.get(instance.archetype_id)
        if spec is None:
            raise CatalogError(
                f"unknown archetype {instance.archetype_id!r}; "
                f"catalog has: {sorted(self.archetypes)}"
            )
        wanted = instance.archetype_version
        if wanted is not None and wanted != spec.version:
            raise CatalogError(
                f"archetype {instance.archetype_id!r} is at version "
                f"{spec.version}, instance pinned @{wanted}"
            )
        return spec

    def modifiers_for(self, instance: ProductInstance) -> dict[str, ModifierDef]:
        return {
            use.id: self.modifiers[use.id]
            for use in instance.modifiers
            if use.id in self.modifiers
        }


def _bind_checks(names: list[str], where: str) -> None:
    for name in names:
        if not known_check(name):
            raise CatalogError(f"{where}: unknown validator/check name {name!r}")


def _bind_features(names: list[str], vocabulary: dict[str, FeatureDef], where: str) -> None:
    for name in names:
        if name not in vocabulary:
            raise CatalogError(f"{where}: unknown feature id {name!r}")


def _bind_forbidden_forms(names: list[str], where: str) -> None:
    for name in names:
        if name not in FORBIDDEN_FORM_DETECTORS:
            raise CatalogError(
                f"{where}: unknown forbidden form {name!r}; "
                f"known: {sorted(FORBIDDEN_FORM_DETECTORS)}"
            )


def _load_features(path: Path) -> dict[str, FeatureDef]:
    doc = _load_yaml(path)
    if not isinstance(doc, dict) or doc.get("schema") != "features/v1":
        raise CatalogError(f"{path.name}: expected 'schema: features/v1'")
    vocabulary: dict[str, FeatureDef] = {}
    for raw in doc.get("features", []):
        try:
            feature = FeatureDef.model_validate(raw)
        except ValidationError as exc:
            raise CatalogError(f"{path.name}: {exc}") from exc
        if feature.id in vocabulary:
            raise CatalogError(f"{path.name}: duplicate feature id {feature.id!r}")
        _bind_checks(feature.verified_by, f"feature {feature.id!r}")
        vocabulary[feature.id] = feature
    return vocabulary


def _load_modifier(path: Path, vocabulary: dict[str, FeatureDef]) -> ModifierDef:
    try:
        mod = ModifierDef.model_validate(_load_yaml(path))
    except ValidationError as exc:
        raise CatalogError(f"{path.name}: {exc}") from exc
    _bind_checks(mod.validators, f"modifier {mod.id!r}")
    _bind_features(mod.provides_features, vocabulary, f"modifier {mod.id!r}")
    return mod


def _load_archetype(
    path: Path, vocabulary: dict[str, FeatureDef], modifiers: dict[str, ModifierDef]
) -> ArchetypeSpec:
    try:
        spec = ArchetypeSpec.model_validate(_load_yaml(path))
    except ValidationError as exc:
        raise CatalogError(f"{path.name}: {exc}") from exc
    where = f"archetype {spec.id!r}"
    _bind_checks(spec.validators, where)
    _bind_features(spec.provides_features, vocabulary, where)
    _bind_features(spec.contract.must_have, vocabulary, f"{where} contract.must_have")
    _bind_forbidden_forms(spec.forbidden_forms, where)
    _bind_forbidden_forms(spec.contract.must_not_have, f"{where} contract.must_not_have")
    for mod_id in spec.allowed_modifiers:
        if mod_id not in modifiers:
            raise CatalogError(f"{where}: unknown modifier {mod_id!r} in allowed_modifiers")
    for region in spec.regions:
        for mod_id in region.forbidden_modifiers:
            if mod_id not in modifiers:
                raise CatalogError(
                    f"{where} region {region.id!r}: unknown modifier {mod_id!r}"
                )
    return spec


def load_catalog(data_dir: Path | None = None) -> Catalog:
    root = data_dir or DATA_DIR
    vocabulary = _load_features(root / "features.yaml")
    modifiers: dict[str, ModifierDef] = {}
    for path in sorted((root / "modifiers").glob("*.yaml")):
        mod = _load_modifier(path, vocabulary)
        if mod.id in modifiers:
            raise CatalogError(f"duplicate modifier id {mod.id!r}")
        modifiers[mod.id] = mod
    archetypes: dict[str, ArchetypeSpec] = {}
    for path in sorted((root / "archetypes").glob("*.yaml")):
        spec = _load_archetype(path, vocabulary, modifiers)
        if spec.id in archetypes:
            raise CatalogError(f"duplicate archetype id {spec.id!r}")
        archetypes[spec.id] = spec
    return Catalog(features=vocabulary, modifiers=modifiers, archetypes=archetypes)


def load_instance(path: Path) -> ProductInstance:
    try:
        return ProductInstance.model_validate(_load_yaml(path))
    except ValidationError as exc:
        raise CatalogError(f"{path.name}: {exc}") from exc


def _check_modifier_use(
    use: ModifierUse, archetype: ArchetypeSpec, catalog: Catalog
) -> list[str]:
    problems: list[str] = []
    where = f"modifier {use.id!r} on region {use.target!r}"
    if use.id not in catalog.modifiers:
        return [f"{where}: unknown modifier"]
    if use.id not in archetype.allowed_modifiers:
        problems.append(f"{where}: not allowed by archetype {archetype.id!r}")
    mod = catalog.modifiers[use.id]
    region = archetype.region(use.target)
    if region is None:
        problems.append(f"{where}: region does not exist on {archetype.id!r}")
        return problems
    if region.role in mod.forbidden_targets:
        problems.append(f"{where}: role {region.role} is a forbidden target")
    elif region.role not in mod.applies_to:
        problems.append(f"{where}: role {region.role} not in applies_to")
    if not region.editable:
        problems.append(f"{where}: region is not editable")
    if use.id in region.forbidden_modifiers:
        problems.append(f"{where}: region forbids this modifier")
    for pname, raw in use.params.items():
        pspec = mod.params.get(pname)
        if pspec is None:
            problems.append(f"{where}: unknown param {pname!r}")
            continue
        if pspec.type == "choice":
            if raw not in pspec.choices:
                problems.append(
                    f"{where}: {pname}={raw!r} not in {pspec.choices}"
                )
            continue
        try:
            value = parse_value(raw, pspec.type, where=f"{use.id}.{pname}")
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if value.kind == "literal" and value.literal is not None:
            lo = pspec.min.literal if pspec.min and pspec.min.kind == "literal" else None
            hi = pspec.max.literal if pspec.max and pspec.max.kind == "literal" else None
            if lo is not None and value.literal < lo:
                problems.append(f"{where}: {pname}={value.literal:g} below min {lo:g}")
            if hi is not None and value.literal > hi:
                problems.append(f"{where}: {pname}={value.literal:g} above max {hi:g}")
    return problems


def validate_instance(instance: ProductInstance, catalog: Catalog) -> ArchetypeSpec:
    """Cross-validate an instance against the catalog; returns the archetype.
    Raises :class:`CatalogError` listing every problem at once."""
    archetype = catalog.archetype_for(instance)
    problems: list[str] = []
    # Requested features outside the vocabulary are NOT errors here: the
    # capability resolver reports them as engine gaps (strict mode decides
    # whether a gap fails the run). Crashing would punish honest asking.
    for use in instance.modifiers:
        problems.extend(_check_modifier_use(use, archetype, catalog))
    if problems:
        raise CatalogError(
            f"instance {instance.id!r} failed catalog validation:\n  - "
            + "\n  - ".join(problems)
        )
    return archetype
