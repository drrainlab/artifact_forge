"""Parameter resolution — raw instance params + archetype spec -> final
numeric context, then constraint findings.

Ported from v1 ``parametric.py::resolve_model`` with the NG value grammar:
defaults/bounds are :class:`~..core.values.ValueSpec` (literal or formula)
instead of split ``value``/``*_expr`` fields. The battle-tested contract is
kept verbatim: parameters resolve ONE AT A TIME, fully, in declaration order
— default, then clamp — so a later parameter's formulas always see an
earlier one's FINAL (already-clamped) value. Derived values are outputs,
computed last; constraints run against the fully-resolved context.

Choice parameters (e.g. a screw size ``M4``) never enter the numeric
context; they resolve into a separate string map the archetype builder
translates itself (the v1 numeric-flags lesson).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.expr import evaluate
from ..core.findings import Finding, Level, Status
from ..core.values import ValueSpec, parse_value
from .archetype import ArchetypeSpec
from .instance import ProductInstance


@dataclass
class ResolvedParams:
    """The fully-resolved parameter surface of one product instance."""

    context: dict[str, float] = field(default_factory=dict)
    choices: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(f.status is not Status.FAIL for f in self.findings)


def _safe_resolve(spec: ValueSpec, ctx: dict[str, float]) -> float | None:
    """A formula referencing a name missing from ``ctx`` degrades to "not
    resolvable" instead of raising — one malformed param must never abort
    the whole model (v1 ``_safe_evaluate`` discipline)."""
    try:
        return spec.resolve(ctx)
    except Exception:
        return None


def _seed_context(
    archetype: ArchetypeSpec, raw: dict[str, Any], findings: list[Finding]
) -> tuple[dict[str, float], dict[str, str], dict[str, ValueSpec]]:
    ctx: dict[str, float] = {}
    choices: dict[str, str] = {}
    deferred: dict[str, ValueSpec] = {}
    for name, raw_value in raw.items():
        spec = archetype.parameters.get(name)
        if spec is None:
            findings.append(
                Finding(
                    check=f"param:{name}",
                    status=Status.FAIL,
                    level=Level.SCHEMA,
                    message=f"unknown parameter {name!r} for archetype {archetype.id!r}",
                )
            )
            continue
        if spec.type == "choice":
            if not isinstance(raw_value, str) or raw_value not in spec.choices:
                findings.append(
                    Finding(
                        check=f"param:{name}",
                        status=Status.FAIL,
                        level=Level.SCHEMA,
                        message=(
                            f"{name!r} must be one of {spec.choices}, got {raw_value!r}"
                        ),
                    )
                )
                continue
            choices[name] = raw_value
            continue
        try:
            value = parse_value(raw_value, spec.type, where=name)
        except ValueError as exc:
            findings.append(
                Finding(
                    check=f"param:{name}",
                    status=Status.FAIL,
                    level=Level.SCHEMA,
                    message=str(exc),
                )
            )
            continue
        if value.kind == "literal":
            assert value.literal is not None
            ctx[name] = value.literal
        else:
            # Instance-level expr params are resolved in the main loop, in
            # declaration order, once the parameters they reference landed.
            deferred[name] = value
    return ctx, choices, deferred


def resolve_params(
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> ResolvedParams:
    findings: list[Finding] = []
    ctx, choices, deferred = _seed_context(archetype, instance.params, findings)
    ctx.update(instance.manufacturing.env_context())

    for name, spec in archetype.parameters.items():
        if spec.type == "choice":
            if name not in choices and isinstance(spec.default, str):
                choices[name] = spec.default
            continue
        if name in deferred:
            v = _safe_resolve(deferred[name], ctx)
            if v is not None:
                ctx[name] = v
            else:
                findings.append(
                    Finding(
                        check=f"param:{name}",
                        status=Status.FAIL,
                        level=Level.SCHEMA,
                        message=(
                            f"expression for {name!r} references unknown names: "
                            f"{deferred[name].source}"
                        ),
                    )
                )
        if name not in ctx and isinstance(spec.default, ValueSpec):
            v = _safe_resolve(spec.default, ctx)
            if v is not None:
                ctx[name] = v
        if name not in ctx:
            if spec.default is None:
                findings.append(
                    Finding(
                        check=f"param:{name}",
                        status=Status.FAIL,
                        level=Level.SCHEMA,
                        message=f"required parameter {name!r} not given and has no default",
                    )
                )
            continue
        lo = _safe_resolve(spec.min, ctx) if spec.min is not None else None
        hi = _safe_resolve(spec.max, ctx) if spec.max is not None else None
        v = ctx[name]
        clamped = v
        if lo is not None:
            clamped = max(clamped, lo)
        if hi is not None:
            clamped = min(clamped, hi)
        if clamped != v:
            findings.append(
                Finding(
                    check=f"param:{name}",
                    status=Status.WARN,
                    level=Level.SCHEMA,
                    message=f"{name} clamped from {v:g} to {clamped:g}",
                    measured=v,
                    limit=lo if clamped == lo else hi,
                )
            )
        ctx[name] = clamped

    for name, formula in archetype.derived.items():
        try:
            ctx[name] = evaluate(formula, ctx)
        except Exception as exc:
            findings.append(
                Finding(
                    check=f"derived:{name}",
                    status=Status.FAIL,
                    level=Level.SCHEMA,
                    message=f"derived {name!r} could not be evaluated: {exc}",
                )
            )

    for formula in archetype.constraints:
        try:
            ok = evaluate(formula, ctx) != 0.0
        except Exception as exc:
            findings.append(
                Finding(
                    check=f"constraint:{formula}",
                    status=Status.FAIL,
                    level=Level.SCHEMA,
                    message=f"constraint could not be evaluated: {exc}",
                )
            )
            continue
        findings.append(
            Finding(
                check=f"constraint:{formula}",
                status=Status.PASS if ok else Status.FAIL,
                level=Level.SCHEMA,
                message=formula if ok else f"violated: {formula}",
            )
        )

    return ResolvedParams(context=ctx, choices=choices, findings=findings)


def locked_params(archetype: ArchetypeSpec) -> list[str]:
    """Names an agent/user patch may never assign directly."""
    return [
        name
        for name, spec in archetype.parameters.items()
        if spec.role == "safety_locked"
    ]
