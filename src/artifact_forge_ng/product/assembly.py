"""Typed YAML assembly — several parts plus VERIFIED joints. An assembly
is not a folder of products: it names one root part (the only frame of
reference), inlines each part as a full self-contained product/v1 body,
injects ``shared`` parameters so mating dimensions are declared ONCE, and
lists joints from a typed registry. "These parts fit together" is a set of
measured checks (IR before any CAD, fit probes in the assembled pose), not
a comment.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .instance import ProductInstance
from .schema_base import VersionedModel

#: Poses are deterministic: only quarter-turn rotations are legal in v1 —
#: an assembly must SAY its pose, never have it inferred.
_LEGAL_ANGLES = {-270.0, -180.0, -90.0, 0.0, 90.0, 180.0, 270.0}


class AssemblyPart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str
    #: Full inline product body — the assembly file is self-contained,
    #: the same discipline as edited YAML artifacts.
    product: ProductInstance


class JointUse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    a: str  # "ref.datum" on the root-side part
    b: str  # "ref.datum" on the mounted part
    rotate: list[float] = [0.0, 0.0, 0.0]
    params: dict[str, Any] = {}

    @field_validator("a", "b")
    @classmethod
    def _check_ref_datum(cls, v: str) -> str:
        if v.count(".") != 1 or not all(v.split(".")):
            raise ValueError(f"joint anchor {v!r} must be 'ref.datum'")
        return v

    @field_validator("rotate")
    @classmethod
    def _check_rotate(cls, v: list[float]) -> list[float]:
        if len(v) != 3:
            raise ValueError("rotate must be [rx, ry, rz]")
        bad = [a for a in v if float(a) not in _LEGAL_ANGLES]
        if bad:
            raise ValueError(
                f"rotate angles {bad} not in 90-degree steps — v1 poses are "
                "explicit quarter turns, never inferred"
            )
        return [float(a) for a in v]

    @property
    def a_ref(self) -> str:
        return self.a.split(".")[0]

    @property
    def a_datum(self) -> str:
        return self.a.split(".")[1]

    @property
    def b_ref(self) -> str:
        return self.b.split(".")[0]

    @property
    def b_datum(self) -> str:
        return self.b.split(".")[1]


class WiringSpec(BaseModel):
    """Cross-part cable continuity declaration: the killer check — the
    cable must pass THROUGH every named part in the assembled pose."""

    model_config = ConfigDict(extra="forbid")

    from_part: str
    to_part: str
    d: Any = "6mm"  # parsed by the value grammar at check time


class AssemblyContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_have: list[str] = []


class AssemblyInstance(VersionedModel):
    SCHEMA_KIND: ClassVar[str] = "assembly"

    id: str
    strict: bool = True
    #: The single frame of reference: every pose is relative to this part.
    root: str
    parts: list[AssemblyPart]
    #: Injected into every part whose archetype has the parameter — mating
    #: dimensions (mount_bc) are declared ONCE, desync is unrepresentable.
    shared: dict[str, Any] = {}
    joints: list[JointUse]
    wiring: WiringSpec | None = None
    contract: AssemblyContract = AssemblyContract()

    @model_validator(mode="after")
    def _cross_checks(self) -> "AssemblyInstance":
        refs = [p.ref for p in self.parts]
        if len(refs) != len(set(refs)):
            raise ValueError("duplicate part refs")
        if len(refs) < 2:
            raise ValueError("an assembly needs at least two parts")
        if self.root not in refs:
            raise ValueError(f"root {self.root!r} is not one of {refs}")
        if not self.joints:
            raise ValueError("an assembly needs at least one joint")
        for j in self.joints:
            for ref in (j.a_ref, j.b_ref):
                if ref not in refs:
                    raise ValueError(f"joint anchors unknown part {ref!r}")
            if j.a_ref == j.b_ref:
                raise ValueError("a joint must connect two DIFFERENT parts")
        if self.wiring is not None:
            for ref in (self.wiring.from_part, self.wiring.to_part):
                if ref not in refs:
                    raise ValueError(f"wiring names unknown part {ref!r}")
        return self

    def part(self, ref: str) -> AssemblyPart:
        for p in self.parts:
            if p.ref == ref:
                return p
        raise KeyError(ref)
