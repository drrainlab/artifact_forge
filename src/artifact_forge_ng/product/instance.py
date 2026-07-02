"""Typed YAML product instance — the user's concrete product.

Shape-level validation lives here; cross-validation against the catalog
(archetype exists, modifier allowed, region roles legal, params in range)
lives in ``catalog.loader.validate_instance`` because it needs the registry.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from ..core.values import parse_quantity
from .schema_base import VersionedModel

_REF_RE = re.compile(r"^(?P<id>[a-z0-9_]+)(?:@(?P<version>\d+))?$")


class ManufacturingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process: Literal["fdm"] = "fdm"
    material: str = "PETG"
    nozzle: float = 0.4
    layer_height: float = 0.2
    support_policy: Literal["avoid", "none", "allow"] = "avoid"

    @field_validator("nozzle", "layer_height", mode="before")
    @classmethod
    def _parse_length(cls, v: Any) -> float:
        if isinstance(v, str):
            return parse_quantity(v, "length", where="manufacturing")
        return float(v)

    def env_context(self) -> dict[str, float]:
        """The flat-name environment injected into every formula context.

        Dotted spec names (``printer.min_wall``) are normalized to these
        underscore names by the value grammar before evaluation.
        """
        return {
            "nozzle_d": self.nozzle,
            "layer_height": self.layer_height,
            # Printable-wall floor: two perimeters, never below 1.2 mm.
            "printer_min_wall": max(2.0 * self.nozzle, 1.2),
        }


class ModifierUse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    #: Target semantic region id — mandatory: modifiers only apply to regions.
    target: str
    params: dict[str, Any] = {}


class ProductInstance(VersionedModel):
    SCHEMA_KIND: ClassVar[str] = "product"

    id: str
    archetype: str
    strict: bool = True
    #: What the user asked for, in feature-vocabulary ids. Explicit for now;
    #: the phase-4 intent parser will fill it from prose.
    requested_features: list[str] = []
    #: Raw parameter values; parsed/clamped against the archetype at resolve.
    params: dict[str, Any] = {}
    style: dict[str, Any] = {}
    manufacturing: ManufacturingSpec = ManufacturingSpec()
    modifiers: list[ModifierUse] = []

    @field_validator("archetype")
    @classmethod
    def _check_ref(cls, v: str) -> str:
        if not _REF_RE.match(v):
            raise ValueError(
                f"malformed archetype ref {v!r}; expected 'id' or 'id@version'"
            )
        return v

    @property
    def archetype_id(self) -> str:
        m = _REF_RE.match(self.archetype)
        assert m is not None
        return m.group("id")

    @property
    def archetype_version(self) -> int | None:
        m = _REF_RE.match(self.archetype)
        assert m is not None
        return int(m.group("version")) if m.group("version") else None
