"""The scalar value grammar of the YAML Product Grammar — one place, reused
everywhere a YAML document carries a dimensioned value.

Three spellings are legal in archetype/instance YAML:

    quantity   "20mm", "0.4 mm", "12deg"     -> canonical float (mm / deg)
    number     20, 0.55                       -> bare float (dimensionless)
    expr       expr(bundle_d * 0.55)          -> formula, resolved later

and one more in repair patches ONLY:

    delta      "+3mm", "-1.5mm"               -> relative to current value

Formulas are evaluated by the sandboxed AST evaluator in ``core.expr`` (no
eval, whitelist-only). That evaluator forbids attribute access, so dotted
environment names the spec-level YAML uses (``printer.min_wall``) are
normalized to flat underscore names (``printer_min_wall``) here, before
evaluation; the resolver injects the manufacturing environment under those
flat names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from . import units
from .expr import evaluate

#: Parameter type -> physical dimension its quantities must carry.
TYPE_DIMENSIONS: dict[str, units.Dimension] = {
    "length": units.Dimension.LENGTH,
    "angle": units.Dimension.ANGLE,
    "number": units.Dimension.DIMENSIONLESS,
    "count": units.Dimension.DIMENSIONLESS,
    "bool": units.Dimension.DIMENSIONLESS,
}

#: Canonical unit each dimension is stored in (matches the CAD kernel).
CANONICAL_UNIT: dict[units.Dimension, str] = {
    units.Dimension.LENGTH: "mm",
    units.Dimension.ANGLE: "deg",
    units.Dimension.DIMENSIONLESS: "",
}

_QUANTITY_RE = re.compile(
    r"^\s*(?P<num>[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(?P<unit>[^\s]*)\s*$"
)
_EXPR_RE = re.compile(r"^\s*expr\((?P<body>.*)\)\s*$", re.DOTALL)
_DOT_NAME_RE = re.compile(r"(?<=[a-zA-Z_])\.(?=[a-zA-Z_])")


class ValueError_(ValueError):
    """Raised for any malformed value string; message names the offender."""


def normalize_formula(formula: str) -> str:
    """``printer.min_wall`` -> ``printer_min_wall``; float literals untouched.
    An ``expr(...)`` wrapper, if present, is stripped — formula-position
    fields (derived, constraints, invariants) accept both spellings."""
    m = _EXPR_RE.match(formula)
    if m:
        formula = m.group("body").strip()
    return _DOT_NAME_RE.sub("_", formula)


def parse_quantity(text: str, param_type: str, *, where: str = "") -> float:
    """Parse ``"20mm"`` / ``"0.4 mm"`` / bare ``"12"`` to a canonical float.

    The unit's dimension must match the declared parameter type; a bare
    number is accepted for any type (assumed already canonical).
    """
    dim = _dimension_for(param_type, where)
    m = _QUANTITY_RE.match(text)
    if not m:
        raise ValueError_(f"{where}: malformed quantity {text!r}")
    value = float(m.group("num"))
    symbol = m.group("unit")
    if not symbol:
        return value
    if not units.is_known_unit(symbol):
        raise ValueError_(f"{where}: unknown unit {symbol!r} in {text!r}")
    unit_dim = units.dimension_of(symbol)
    if unit_dim is not dim:
        raise ValueError_(
            f"{where}: unit {symbol!r} is {unit_dim.value}, but parameter "
            f"type {param_type!r} needs {dim.value}"
        )
    return units.convert(value, symbol, CANONICAL_UNIT[dim])


def _dimension_for(param_type: str, where: str) -> units.Dimension:
    try:
        return TYPE_DIMENSIONS[param_type]
    except KeyError:
        raise ValueError_(
            f"{where}: unknown parameter type {param_type!r}; "
            f"use one of {sorted(TYPE_DIMENSIONS)}"
        ) from None


@dataclass(frozen=True)
class ValueSpec:
    """A literal canonical value or a deferred formula."""

    kind: str  # "literal" | "expr"
    literal: float | None = None
    formula: str | None = None
    #: The original YAML spelling, kept for diffable round-trips and errors.
    source: str = ""

    def resolve(self, ctx: dict[str, float]) -> float:
        if self.kind == "literal":
            assert self.literal is not None
            return self.literal
        assert self.formula is not None
        return evaluate(self.formula, ctx)

    def to_yaml(self) -> Any:
        return self.source or self.literal


def parse_value(raw: Any, param_type: str, *, where: str = "") -> ValueSpec:
    """Parse a YAML scalar into a :class:`ValueSpec`.

    Numbers are literals (already canonical); ``"expr(...)"`` strings are
    formulas; any other string must be a quantity with a matching unit.
    """
    if isinstance(raw, bool):
        if param_type != "bool":
            raise ValueError_(f"{where}: got boolean for type {param_type!r}")
        return ValueSpec("literal", literal=1.0 if raw else 0.0, source=str(raw))
    if isinstance(raw, (int, float)):
        _dimension_for(param_type, where)  # validates the type name
        return ValueSpec("literal", literal=float(raw), source=str(raw))
    if isinstance(raw, str):
        m = _EXPR_RE.match(raw)
        if m:
            body = m.group("body").strip()
            if not body:
                raise ValueError_(f"{where}: empty expr()")
            return ValueSpec("expr", formula=normalize_formula(body), source=raw)
        return ValueSpec(
            "literal", literal=parse_quantity(raw, param_type, where=where), source=raw
        )
    raise ValueError_(f"{where}: cannot parse value {raw!r} (type {type(raw).__name__})")


@dataclass(frozen=True)
class DeltaSpec:
    """A patch-only value: absolute set, relative delta, or formula."""

    kind: str  # "set" | "add" | "expr"
    amount: float | None = None
    formula: str | None = None
    source: str = ""

    def apply(self, current: float, ctx: dict[str, float]) -> float:
        if self.kind == "set":
            assert self.amount is not None
            return self.amount
        if self.kind == "add":
            assert self.amount is not None
            return current + self.amount
        assert self.formula is not None
        return evaluate(self.formula, ctx)


def parse_delta(raw: Any, param_type: str, *, where: str = "") -> DeltaSpec:
    """Parse a patch value: ``"+3mm"``/``"-1mm"`` are relative; the rest
    follows :func:`parse_value` semantics as an absolute set."""
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped[:1] in "+-" and not _EXPR_RE.match(stripped):
            magnitude = parse_quantity(stripped[1:], param_type, where=where)
            sign = 1.0 if stripped[0] == "+" else -1.0
            return DeltaSpec("add", amount=sign * magnitude, source=raw)
    spec = parse_value(raw, param_type, where=where)
    if spec.kind == "expr":
        return DeltaSpec("expr", formula=spec.formula, source=spec.source)
    return DeltaSpec("set", amount=spec.literal, source=spec.source)
