"""Typed YAML archetype schema — one entry in the product-grammar catalog.

An archetype is a full buildable package: typed parameters with units and
expression defaults, constraints, a form recipe (which section profile, which
plane), semantic regions, the validator/forbidden-form names it must be
checked against, the modifiers it allows, and its product contract.

Parameter declaration order in YAML is resolution order (the v1 linear
resolution contract): a later parameter's ``default``/``min``/``max``
formulas may reference any earlier parameter's final clamped value.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.values import ValueSpec, normalize_formula, parse_value
from .contract import ContractSpec
from .schema_base import VersionedModel

PARAM_ROLES = (
    "functional",
    "manufacturing",
    "structural",
    "aesthetic",
    "assembly",
    "safety_locked",
)

PARAM_TYPES = ("length", "angle", "number", "count", "bool", "choice")


class RegionRole(StrEnum):
    MOUNTING_SURFACE = "mounting_surface"
    FASTENER_KEEPOUT = "fastener_keepout"
    SOFT_CONTACT_SURFACE = "soft_contact_surface"
    HIGH_STRESS_REGION = "high_stress_region"
    RETAINING_FLEXURE = "retaining_flexure"
    AESTHETIC_LIGHTENING = "aesthetic_lightening"
    SEAL_SURFACE = "seal_surface"
    # -- biomorphic pack (docs/BIOMORPHIC.md) ------------------------------
    #: Large shell face that may receive additive ribs AND subtractive
    #: windows — the exoskeleton's primary canvas.
    EXOSKELETON_PANEL = "exoskeleton_panel"
    #: Where rib roots are allowed/expected to land (flange rims, bosses).
    RIB_ANCHOR = "rib_anchor"
    #: Functional interface volume no modifier may cut into (boss columns,
    #: channel reservations, rail zones …) — flavor lives in the region id.
    INTERFACE_KEEPOUT = "interface_keepout"


class ParamSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    type: Literal["length", "angle", "number", "count", "bool", "choice"]
    default: ValueSpec | str | None = None
    min: ValueSpec | None = None
    max: ValueSpec | None = None
    role: Literal[
        "functional",
        "manufacturing",
        "structural",
        "aesthetic",
        "assembly",
        "safety_locked",
    ] = "functional"
    exposed: bool = False
    choices: list[str] = []
    description: str = ""

    @model_validator(mode="before")
    @classmethod
    def _parse_values(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        ptype = data.get("type")
        if ptype == "choice":
            if data.get("min") is not None or data.get("max") is not None:
                raise ValueError("choice parameters cannot have min/max")
            if not data.get("choices"):
                raise ValueError("choice parameters must declare choices")
            default = data.get("default")
            if default is not None and default not in data["choices"]:
                raise ValueError(
                    f"default {default!r} not in choices {data['choices']}"
                )
            return data
        if ptype in PARAM_TYPES:
            for key in ("default", "min", "max"):
                raw = data.get(key)
                if raw is not None and not isinstance(raw, ValueSpec):
                    data[key] = parse_value(raw, ptype, where=key)
        return data

    @model_validator(mode="after")
    def _check_bounds(self) -> "ParamSpec":
        if (
            isinstance(self.min, ValueSpec)
            and isinstance(self.max, ValueSpec)
            and self.min.kind == "literal"
            and self.max.kind == "literal"
            and self.min.literal is not None
            and self.max.literal is not None
            and self.min.literal > self.max.literal
        ):
            raise ValueError(
                f"min {self.min.literal} > max {self.max.literal}"
            )
        return self


#: Informational archetype lifecycle (docs/BIOMORPHIC.md). The COMPUTED
#: status (recipe/buildable/metadata_only) stays the source of truth about
#: buildability; maturity records where the archetype sits in its life.
#: Bio-0 adds maturity to ArchetypeSpec only; Bio-4A may extend it to
#: presets/families/extensions.
MATURITY_LEVELS = (
    "draft", "metadata_only", "recipe_valid", "form_valid",
    "sandbox_buildable", "production_buildable",
)


class LoadPathSpec(BaseModel):
    """A declared force route (docs/BIOMORPHIC.md): from a source region to
    an anchor region. The exoskeleton substrate seeds rib growth along it;
    ``form.load_paths_connected`` then verifies the built graph honors it."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    priority: Literal["primary", "secondary"] = "primary"


class RegionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: RegionRole
    editable: bool = True
    forbidden_modifiers: list[str] = []
    #: Human name shown in the UI ("outer ring band"); ``id`` stays canonical.
    label: str = ""
    #: Alternative human names — LLM grounding and did-you-mean matching.
    #: Patches must still name the canonical ``id``.
    aliases: list[str] = []
    description: str = ""


class RecipeOpUse(BaseModel):
    """One builder invocation inside a recipe form. ``params`` values speak
    the same value grammar as everything else ("70mm", "expr(plate_l/2)");
    a bare string naming an archetype parameter substitutes its resolved
    value (numbers and choices alike)."""

    model_config = ConfigDict(extra="forbid")

    op: str
    id: str = ""
    params: dict[str, Any] = {}


class FormSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal[
        "section_extrude", "section_sweep", "plate", "profile_revolve", "recipe"
    ]
    section: str
    plane: Literal["YZ", "XZ", "XY"] = "YZ"
    width_axis: Literal["X", "Y", "Z"] = "X"
    #: Recipe forms only: ordered builder invocations (first op is the base
    #: solid, the rest attach features). Empty for classic Python builders.
    ops: list[RecipeOpUse] = []

    @model_validator(mode="after")
    def _axis_off_plane(self) -> "FormSpec":
        if self.width_axis in self.plane:
            raise ValueError(
                f"width_axis {self.width_axis!r} must be normal to plane {self.plane!r}"
            )
        if self.type == "recipe" and not self.ops:
            raise ValueError("recipe form needs at least one op")
        if self.type != "recipe" and self.ops:
            raise ValueError("ops are only legal on recipe forms")
        return self


class ArchetypeSpec(VersionedModel):
    SCHEMA_KIND: ClassVar[str] = "archetype"

    id: str
    version: int = 1
    object_class: str
    description: str = ""
    provides_features: list[str] = []
    parameters: dict[str, ParamSpec] = {}
    derived: dict[str, str] = {}
    constraints: list[str] = []
    form: FormSpec
    regions: list[RegionSpec] = []
    #: Declared force routes between regions — see LoadPathSpec.
    load_paths: list[LoadPathSpec] = []
    #: Informational lifecycle stage; buildability truth stays computed.
    maturity: Literal[
        "draft", "metadata_only", "recipe_valid", "form_valid",
        "sandbox_buildable", "production_buildable",
    ] | None = None
    surface_style: str = "molded_utility_part"
    validators: list[str] = []
    forbidden_forms: list[str] = []
    allowed_modifiers: list[str] = []
    contract: ContractSpec = Field(default_factory=ContractSpec)

    @field_validator("derived")
    @classmethod
    def _normalize_derived(cls, v: dict[str, str]) -> dict[str, str]:
        return {k: normalize_formula(f) for k, f in v.items()}

    @field_validator("constraints")
    @classmethod
    def _normalize_constraints(cls, v: list[str]) -> list[str]:
        return [normalize_formula(f) for f in v]

    @model_validator(mode="after")
    def _cross_checks(self) -> "ArchetypeSpec":
        region_ids = [r.id for r in self.regions]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError(f"duplicate region ids in {self.id!r}")
        return self

    @property
    def ref(self) -> str:
        return f"{self.id}@{self.version}"

    def region(self, region_id: str) -> RegionSpec | None:
        for r in self.regions:
            if r.id == region_id:
                return r
        return None
