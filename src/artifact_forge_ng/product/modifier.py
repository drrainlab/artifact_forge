"""Typed YAML modifier schema — a controlled transformation.

A modifier never free-cuts geometry: it applies only to a semantic region
whose role is in ``applies_to`` and not in ``forbidden_targets``, with typed
params inside declared ranges. What it promises (``provides_features``) is
only ever confirmed by its ``validators`` passing.
"""

from __future__ import annotations

from typing import ClassVar

from .archetype import ParamSpec, RegionRole
from .schema_base import VersionedModel


class ModifierDef(VersionedModel):
    SCHEMA_KIND: ClassVar[str] = "modifier"

    id: str
    version: int = 1
    category: str
    description: str = ""
    applies_to: list[RegionRole]
    forbidden_targets: list[RegionRole] = []
    params: dict[str, ParamSpec] = {}
    requires: list[str] = []
    provides_features: list[str] = []
    validators: list[str] = []

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"
