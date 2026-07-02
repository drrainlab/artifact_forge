"""The modifier kernel — typed, region-bound transformations over the Form
IR. An applicator never free-cuts: it reads its target semantic region,
derives keepouts from the protected regions around it, emits IR features
(field cells, pockets, slots, ribs), and every promise is only marked built
after its validators PASS.

The catalog loader already enforced the schema half (modifier allowed by
the archetype, region exists, role in applies_to, params in range); this
package is the geometry half. A modifier declared in the catalog with no
registered applicator is an ENGINE-GAP warning — never a silent no-op that
still claims its features.
"""

from __future__ import annotations

from typing import Any, Callable

from ..core.findings import Finding, Level, Status
from ..core.values import parse_value
from ..form.part import PartForm
from ..product.archetype import ArchetypeSpec
from ..product.instance import ModifierUse
from ..product.modifier import ModifierDef

#: (form, use, resolved_params, archetype) -> findings. The applicator
#: MUTATES form (adds fields/bores/cutboxes/ribs) and reports what it did.
Applicator = Callable[
    [PartForm, ModifierUse, dict[str, Any], ArchetypeSpec], list[Finding]
]

APPLICATORS: dict[str, Applicator] = {}


def register_applicator(modifier_id: str) -> Callable[[Applicator], Applicator]:
    def wrap(fn: Applicator) -> Applicator:
        APPLICATORS[modifier_id] = fn
        return fn

    return wrap


def resolve_modifier_params(
    mod: ModifierDef, use: ModifierUse, ctx: dict[str, float]
) -> dict[str, Any]:
    """Defaults + instance overrides, parsed and CLAMPED against the
    modifier's own ParamSpecs; expr values resolve against the product's
    resolved context (so ``cell_d: expr(wall * 2)`` is legal)."""
    out: dict[str, Any] = {}
    for name, spec in mod.params.items():
        raw = use.params.get(name, None)
        if spec.type == "choice":
            value = raw if raw is not None else spec.default
            out[name] = value
            continue
        if raw is None:
            if spec.default is None:
                continue
            value_spec = spec.default
        else:
            value_spec = parse_value(raw, spec.type, where=f"{mod.id}.{name}")
        v = value_spec.resolve(ctx)
        lo = spec.min.resolve(ctx) if spec.min is not None else None
        hi = spec.max.resolve(ctx) if spec.max is not None else None
        if lo is not None:
            v = max(v, lo)
        if hi is not None:
            v = min(v, hi)
        out[name] = v
    return out


def apply_modifiers(
    form: PartForm,
    uses: list[ModifierUse],
    modifier_defs: dict[str, ModifierDef],
    archetype: ArchetypeSpec,
) -> list[Finding]:
    findings: list[Finding] = []
    for use in uses:
        mod = modifier_defs.get(use.id)
        if mod is None:
            continue  # loader already failed unknown ids; belt only
        applicator = APPLICATORS.get(use.id)
        if applicator is None:
            findings.append(
                Finding(
                    check=f"modifier:{use.id}",
                    status=Status.WARN,
                    level=Level.FORM,
                    message=(
                        f"modifier {use.id!r} has no applicator — engine gap; "
                        "its features stay unbuilt"
                    ),
                    suggestion=f"implement an applicator for {use.id!r}",
                )
            )
            continue
        params = resolve_modifier_params(mod, use, form.params)
        findings.extend(applicator(form, use, params, archetype))
    return findings


# Import applicator modules so their registrations run.
from . import fields, interface, structural  # noqa: E402,F401
