"""Product Contract IR — the promise layer that sits ABOVE geometry.

A contract names what the product must contain (feature ids), what forbidden
forms it must not degenerate into, and invariant formulas over resolved
parameters. Every entry compiles to an executable check: feature and form
names bind to probe validators at catalog load (unknown name = load error,
never a silent skip), invariants compile to closures over the sandboxed
expression evaluator and run against the fully resolved parameter context.

A critical contract violation forces overall FAIL regardless of score.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from ..core.values import normalize_formula


class ContractSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    must_have: list[str] = []
    must_not_have: list[str] = []
    #: Boolean formulas over the resolved parameter context; non-zero = PASS.
    invariants: list[str] = []

    @field_validator("invariants")
    @classmethod
    def _normalize(cls, v: list[str]) -> list[str]:
        return [normalize_formula(f) for f in v]
