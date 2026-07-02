"""Repair patches — the ONLY way anything (rule, agent, user) modifies a
product. A patch edits the YAML instance (absolute values, ``+3mm`` deltas
against the RESOLVED value, or expr), never raw geometry; the result is
re-validated through the same schemas that accepted the original, so an
illegal patch raises before anything downstream sees it.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from ..catalog.loader import Catalog, CatalogError, validate_instance
from ..core.values import CANONICAL_UNIT, TYPE_DIMENSIONS, parse_delta
from ..product.archetype import ArchetypeSpec
from ..product.instance import ProductInstance
from ..product.resolve import resolve_params
from ..product.schema_base import VersionedModel

#: Roles a patch may never assign directly (v1 reject_locked_patch).
LOCKED_ROLES = frozenset({"safety_locked"})


class ModifierAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    target: str
    params: dict[str, Any] = {}


class ModifierOps(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add: list[ModifierAdd] = []
    remove: list[str] = []


class Patch(VersionedModel):
    SCHEMA_KIND: ClassVar[str] = "patch"

    #: What KIND of edit this is — functional changes the product's job,
    #: manufacturing its printability, structural its strength, style its
    #: skin. Classification feeds the edit report, not different code paths.
    type: str = "functional"  # functional | manufacturing | structural | style
    reason: str = ""
    #: Names that MUST come out of the rebuild unchanged: parameter names
    #: (resolved values compared numerically) and/or feature ids (must
    #: still be BUILT after). Verified by the edit pipeline — a violated
    #: preserve fails the edit, it is a guarantee, not a hope.
    preserve: list[str] = []
    params: dict[str, Any] = {}
    #: Merged over instance.manufacturing (e.g. support_policy: none).
    manufacturing: dict[str, Any] = {}
    #: Merged over instance.style (e.g. surface: biomorphic_utility_part).
    style: dict[str, Any] = {}
    modifiers: ModifierOps = ModifierOps()


class PatchError(ValueError):
    pass


def _canonical_yaml_value(value: float, param_type: str) -> Any:
    unit = CANONICAL_UNIT[TYPE_DIMENSIONS[param_type]]
    if param_type == "count":
        return int(round(value))
    return f"{value:g}{unit}" if unit else round(value, 6)


def apply_patch(
    instance: ProductInstance,
    patch: Patch,
    archetype: ArchetypeSpec,
    catalog: Catalog,
) -> ProductInstance:
    """Pure: returns a NEW validated instance; the input is untouched."""
    for name in patch.preserve:
        if name not in archetype.parameters and name not in catalog.features:
            raise PatchError(
                f"preserve entry {name!r} is neither a parameter of "
                f"{archetype.id!r} nor a feature in the vocabulary"
            )
    current = resolve_params(archetype, instance)
    data = instance.model_dump(by_alias=True, exclude_none=False)
    params: dict[str, Any] = dict(data.get("params", {}))

    for name, raw in patch.params.items():
        spec = archetype.parameters.get(name)
        if spec is None:
            raise PatchError(f"patch targets unknown parameter {name!r}")
        if spec.role in LOCKED_ROLES:
            raise PatchError(f"patch may not assign locked parameter {name!r}")
        if spec.type == "choice":
            if raw not in spec.choices:
                raise PatchError(f"{name}={raw!r} not in {spec.choices}")
            params[name] = raw
            continue
        delta = parse_delta(raw, spec.type, where=f"patch.{name}")
        if delta.kind == "expr":
            # Keep the formula in the YAML — it stays parametric.
            params[name] = delta.source if str(delta.source).startswith("expr(") else f"expr({delta.formula})"
            continue
        base = current.context.get(name)
        if delta.kind == "add" and base is None:
            raise PatchError(
                f"cannot apply relative delta to unresolved parameter {name!r}"
            )
        new_value = delta.apply(base if base is not None else 0.0, current.context)
        params[name] = _canonical_yaml_value(new_value, spec.type)

    data["params"] = params

    if patch.manufacturing:
        data["manufacturing"] = {
            **data.get("manufacturing", {}),
            **patch.manufacturing,
        }
    if patch.style:
        data["style"] = {**data.get("style", {}), **patch.style}

    modifiers = [dict(m) for m in data.get("modifiers", [])]
    if patch.modifiers.remove:
        modifiers = [m for m in modifiers if m["id"] not in set(patch.modifiers.remove)]
    for add in patch.modifiers.add:
        if any(m["id"] == add.id and m["target"] == add.target for m in modifiers):
            continue
        modifiers.append({"id": add.id, "target": add.target, "params": add.params})
    data["modifiers"] = modifiers

    patched = ProductInstance.model_validate(data)
    try:
        validate_instance(patched, catalog)
    except CatalogError as exc:
        raise PatchError(f"patch produced an illegal instance: {exc}") from exc
    return patched
