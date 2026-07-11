"""Catalog loading — YAML documents -> validated pydantic models, with
FAIL-FAST name binding: every check name, feature id, forbidden form,
modifier reference and region id is resolved at load time. An unknown name
is a :class:`CatalogError`, never a silent skip.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..core.values import parse_value
from ..product.archetype import ArchetypeSpec, RegionSpec
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
    #: archetype id -> "builtin" | "local" (Studio-promoted user catalog).
    origins: dict[str, str] = field(default_factory=dict)

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
    region_ids = {r.id for r in spec.regions}
    for lp in spec.load_paths:
        for name in (lp.from_, lp.to):
            if name not in region_ids:
                raise CatalogError(
                    f"{where} load_path {lp.from_!r} -> {lp.to!r}: "
                    f"{name!r} is not a declared region"
                )
    _bind_interfaces(spec, region_ids, where)
    _bind_recipe_ops(spec, where)
    return spec


def _bind_interfaces(
    spec: ArchetypeSpec, region_ids: set[str], where: str
) -> None:
    """Wave A1 fail-fast: interface ids unique, gender legal for the type,
    region/keepout ids declared. The datum anchor is runtime truth (ops
    publish datums at build) — interface.frame_exists measures it on the
    real form, the loader cannot."""
    seen: set[str] = set()
    for spec_i in spec.interfaces:
        w = f"{where} interface {spec_i.id!r}"
        if spec_i.id in seen:
            raise CatalogError(f"{w}: duplicate interface id")
        seen.add(spec_i.id)
        decl = spec_i.decl()
        if spec_i.gender not in decl.genders:
            raise CatalogError(
                f"{w}: gender {spec_i.gender!r} illegal for type "
                f"{spec_i.type!r} (allowed: {list(decl.genders)})"
            )
        if spec_i.region is not None and spec_i.region not in region_ids:
            raise CatalogError(
                f"{w}: region {spec_i.region!r} is not a declared region")
        for k in spec_i.keepouts:
            if k not in region_ids:
                raise CatalogError(
                    f"{w}: keepout {k!r} is not a declared region")
        lo, hi = decl.clearance_band
        if spec_i.clearance is not None and not lo <= spec_i.clearance <= hi:
            raise CatalogError(
                f"{w}: clearance {spec_i.clearance:g} outside the "
                f"{spec_i.type} band [{lo:g}, {hi:g}]"
            )


def _bind_recipe_ops(spec: ArchetypeSpec, where: str) -> None:
    """Recipe forms bind fail-fast twice over: every op name must exist in
    the op registry, and every validator an op declares must appear in the
    archetype's own ``validators:`` list — a builder cannot ship geometry
    its checks won't measure."""
    if spec.form.type != "recipe":
        return
    from ..form.recipe_ops import RECIPE_OPS

    subscribed = set(spec.validators)
    for use in spec.form.ops:
        decl = RECIPE_OPS.get(use.op)
        if decl is None:
            raise CatalogError(
                f"{where}: unknown recipe op {use.op!r}; known: {sorted(RECIPE_OPS)}"
            )
        missing = [v for v in decl.validators if v not in subscribed]
        if missing:
            raise CatalogError(
                f"{where}: op {use.op!r} requires validators {missing} in the "
                "archetype's validators list"
            )


#: Repo-level user catalog: full-status archetypes outside the package
#: (the Archetype Studio's promote target). Merged by load_catalog.
#: Overridable via ARTIFACT_FORGE_LOCAL_CATALOG (tests, alternate roots).
_DEFAULT_LOCAL_DIR = Path(__file__).resolve().parents[3] / "catalog" / "local"


def _local_dir() -> Path:
    import os

    override = os.environ.get("ARTIFACT_FORGE_LOCAL_CATALOG")
    return Path(override) if override else _DEFAULT_LOCAL_DIR


def load_catalog(data_dir: Path | None = None) -> Catalog:
    # Packs register their ops/checks/joints and contribute catalog data
    # dirs before any YAML binds against the registries (idempotent;
    # disabled by ARTIFACT_FORGE_DISABLE_PACKS=1). An explicit data_dir is
    # an isolated catalog (tests) — pack data is not merged there.
    from ..packs import load_packs, pack_data_dirs
    load_packs()
    root = data_dir or DATA_DIR
    vocabulary = _load_features(root / "features.yaml")
    pack_dirs = pack_data_dirs() if data_dir is None else []
    for pack_id, pack_dir in pack_dirs:
        feats = pack_dir / "features.yaml"
        if feats.exists():
            for fid, feat in _load_features(feats).items():
                if fid in vocabulary:
                    raise CatalogError(
                        f"pack {pack_id!r}: duplicate feature id {fid!r}")
                vocabulary[fid] = feat
    modifiers: dict[str, ModifierDef] = {}
    modifier_files = list(sorted((root / "modifiers").glob("*.yaml")))
    for _pack_id, pack_dir in pack_dirs:
        modifier_files += sorted((pack_dir / "modifiers").glob("*.yaml"))
    for path in modifier_files:
        mod = _load_modifier(path, vocabulary)
        if mod.id in modifiers:
            raise CatalogError(f"duplicate modifier id {mod.id!r}")
        modifiers[mod.id] = mod
    archetypes: dict[str, ArchetypeSpec] = {}
    origins: dict[str, str] = {}
    archetype_files = [
        (path, "builtin") for path in sorted((root / "archetypes").glob("*.yaml"))
    ]
    for pack_id, pack_dir in pack_dirs:
        archetype_files += [
            (path, f"pack:{pack_id}")
            for path in sorted((pack_dir / "archetypes").glob("*.yaml"))
        ]
    local_dir = _local_dir()
    if data_dir is None and local_dir.exists():
        archetype_files += [
            (path, "local") for path in sorted(local_dir.glob("*.yaml"))
        ]
    for path, origin in archetype_files:
        spec = _load_archetype(path, vocabulary, modifiers)
        if spec.id in archetypes:
            raise CatalogError(f"duplicate archetype id {spec.id!r}")
        archetypes[spec.id] = spec
        origins[spec.id] = origin
    return Catalog(features=vocabulary, modifiers=modifiers,
                   archetypes=archetypes, origins=origins)


def load_instance(path: Path) -> ProductInstance:
    try:
        return ProductInstance.model_validate(_load_yaml(path))
    except ValidationError as exc:
        raise CatalogError(f"{path.name}: {exc}") from exc


def compatible_regions(archetype: ArchetypeSpec, mod: ModifierDef) -> list["RegionSpec"]:
    """Editable regions where this modifier may legally land — the exact
    rules :func:`_check_modifier_use` enforces, computed BEFORE a patch
    exists, so UIs and LLM grounding can offer only legal targets."""
    return [
        r for r in archetype.regions
        if r.editable
        and r.role in mod.applies_to
        and r.role not in mod.forbidden_targets
        and mod.id not in r.forbidden_modifiers
    ]


def _normalize_region_name(name: str) -> str:
    return re.sub(r"[\s\-]+", "_", str(name).strip().lower())


def resolve_region_name(archetype: ArchetypeSpec, name: str) -> "RegionSpec | None":
    """Map a human/LLM region name onto the canonical RegionSpec: exact id
    first, then label and aliases (case/space/underscore-insensitive).
    Returns None when nothing matches — the caller decides between a
    did-you-mean suggestion and an honest failure."""
    wanted = _normalize_region_name(name)
    if not wanted:
        return None
    for r in archetype.regions:
        if _normalize_region_name(r.id) == wanted:
            return r
    for r in archetype.regions:
        if any(_normalize_region_name(n) == wanted
               for n in (r.label, *r.aliases) if n):
            return r
    return None


def suggest_region(archetype: ArchetypeSpec, name: str) -> "RegionSpec | None":
    """Closest existing region for an unknown name (did-you-mean). Exact
    alias resolution wins; otherwise fuzzy-match over ids, labels and
    aliases."""
    hit = resolve_region_name(archetype, name)
    if hit is not None:
        return hit
    lookup: dict[str, RegionSpec] = {}
    for r in archetype.regions:
        for n in (r.id, r.label, *r.aliases):
            if n:
                lookup.setdefault(_normalize_region_name(n), r)
    close = difflib.get_close_matches(
        _normalize_region_name(name), list(lookup), n=1, cutoff=0.5
    )
    return lookup[close[0]] if close else None


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
