"""Typed YAML product instance — the user's concrete product.

Shape-level validation lives here; cross-validation against the catalog
(archetype exists, modifier allowed, region roles legal, params in range)
lives in ``catalog.loader.validate_instance`` because it needs the registry.
"""

from __future__ import annotations

import math
import re
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..core.values import parse_quantity
from .modes import MODE_PROFILES
from .schema_base import VersionedModel

_REF_RE = re.compile(r"^(?P<id>[a-z0-9_]+)(?:@(?P<version>\d+))?$")


class ManufacturingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process: Literal["fdm"] = "fdm"
    material: str = "PETG"
    nozzle: float = 0.4
    layer_height: float = 0.2
    support_policy: Literal["avoid", "none", "allow"] = "avoid"
    #: Print bed (x, y, z). The default mirrors manufacturing.BED; a larger
    #: declared machine (e.g. 250-class for the vertical farm modules) is an
    #: explicit instance-level claim, checked by manufacturing.bed_fit.
    bed: list[float] = [220.0, 220.0, 250.0]

    @field_validator("nozzle", "layer_height", mode="before")
    @classmethod
    def _parse_length(cls, v: Any) -> float:
        if isinstance(v, str):
            return parse_quantity(v, "length", where="manufacturing")
        return float(v)

    @field_validator("bed", mode="before")
    @classmethod
    def _parse_bed(cls, v: Any) -> list[float]:
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            raise ValueError("manufacturing.bed must be [x, y, z]")
        return [
            parse_quantity(e, "length", where="manufacturing.bed")
            if isinstance(e, str) else float(e)
            for e in v
        ]

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
            "bed_x": self.bed[0],
            "bed_y": self.bed[1],
            "bed_z": self.bed[2],
        }


#: Body regions the fit layer knows how to measure. Extend together with
#: the archetypes that consume them (wrist, thigh, … in later P-waves).
WEARABLE_REGIONS = ("forearm",)

#: Sane human ranges per field (mm) — a typo like 27mm instead of 270mm
#: must die at the schema, not as an unprintable cuff.
_BODY_FIT_RANGES = {
    "circumference": (150.0, 450.0),
    "length": (80.0, 400.0),
    "clearance": (0.0, 15.0),
    "strap_width": (15.0, 40.0),
}


class BodyFitSpec(BaseModel):
    """Measured body input for wearable artifacts — the same contract as
    ManufacturingSpec: a typed block whose ``env_context`` feeds flat names
    into every parameter formula."""

    model_config = ConfigDict(extra="forbid")

    region: Literal["forearm"] = "forearm"
    circumference: float
    length: float
    clearance: float = 6.0
    strap_width: float = 25.0

    @field_validator(
        "circumference", "length", "clearance", "strap_width", mode="before"
    )
    @classmethod
    def _parse_length(cls, v: Any) -> float:
        if isinstance(v, str):
            return parse_quantity(v, "length", where="body_fit")
        return float(v)

    @model_validator(mode="after")
    def _human_ranges(self) -> "BodyFitSpec":
        for name, (lo, hi) in _BODY_FIT_RANGES.items():
            v = getattr(self, name)
            if not lo <= v <= hi:
                raise ValueError(
                    f"body_fit.{name} = {v:g}mm outside the human range "
                    f"[{lo:g}, {hi:g}] for region {self.region!r}"
                )
        return self

    def env_context(self) -> dict[str, float]:
        return {
            "body_circumference": self.circumference,
            "body_length": self.length,
            "body_clearance": self.clearance,
            "body_strap_width": self.strap_width,
            #: Effective limb diameter — the number saddle math wants.
            "body_d_eff": self.circumference / math.pi,
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
    #: Mode scaffold (wave P2): validated against the MODE_PROFILES
    #: registry — the registry IS the enum. Behavior, not decoration: a
    #: mode's required_context blocks must be present on the instance.
    mode: str = "engineering"
    body_fit: BodyFitSpec | None = None

    @field_validator("archetype")
    @classmethod
    def _check_ref(cls, v: str) -> str:
        if not _REF_RE.match(v):
            raise ValueError(
                f"malformed archetype ref {v!r}; expected 'id' or 'id@version'"
            )
        return v

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v not in MODE_PROFILES:
            raise ValueError(
                f"unknown mode {v!r}; known modes: {sorted(MODE_PROFILES)}"
            )
        return v

    @model_validator(mode="after")
    def _mode_context(self) -> "ProductInstance":
        missing = [
            block
            for block in MODE_PROFILES[self.mode].required_context
            if getattr(self, block, None) is None
        ]
        if missing:
            raise ValueError(
                f"mode {self.mode!r} requires context: {', '.join(missing)}"
            )
        return self

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
