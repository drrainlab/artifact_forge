"""The generic recipe builder — ONE Python entry point for every
``form.type: recipe`` archetype. New archetypes composed from registered
ops need YAML only; this module just evaluates op params against the
resolved context and runs the ops in order.

Param value rules (per op param, typed by the op's declaration):
  * a number or "20mm"/"expr(plate_l/2)" string — the standard value grammar;
  * a bare string naming an archetype parameter — substitutes its resolved
    value (works for choices: ``screw: screw``);
  * choice-typed params take strings verbatim otherwise.
"""

from __future__ import annotations

from typing import Any

from ..core.values import parse_value
from ..form.part import PartForm
from ..form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "recipe"


def _eval_param(
    raw: Any, value_type: str, resolved: ResolvedParams, where: str
) -> Any:
    if isinstance(raw, str):
        if raw in resolved.choices:
            return resolved.choices[raw]
        if raw in resolved.context:
            return resolved.context[raw]
    if value_type in ("choice", "string"):
        if not isinstance(raw, str):
            raise RecipeError(f"{where}: {value_type} param must be a string, got {raw!r}")
        return raw
    if value_type == "count":
        if isinstance(raw, str):
            return parse_value(raw, "count", where=where).resolve(resolved.context)
        return float(raw)
    return parse_value(raw, value_type, where=where).resolve(resolved.context)


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    style = resolve_style(instance, archetype)
    state = RecipeState()

    for use in archetype.form.ops:
        decl = RECIPE_OPS[use.op]  # bound fail-fast at catalog load
        where = f"{archetype.id}.{use.op}"
        params: dict[str, Any] = {}
        for name, (value_type, default) in decl.params.items():
            if name in use.params:
                params[name] = _eval_param(
                    use.params[name], value_type, resolved, f"{where}.{name}"
                )
            elif default is not None:
                params[name] = default
            else:
                raise RecipeError(f"{where}: required op param {name!r} missing")
        unknown = set(use.params) - set(decl.params)
        if unknown:
            raise RecipeError(f"{where}: unknown op params {sorted(unknown)}")
        decl.apply(state, params, use.id)

    if state.section is None:
        raise RecipeError(f"{archetype.id}: recipe produced no base solid")

    declared = instance.manufacturing.print_orientation
    if declared is not None:
        # the contract half of print orientation — checked against the
        # builder's decision by manufacturing.print_orientation_declared
        state.frame["declared_print_orientation"] = declared

    return PartForm(
        name=instance.id,
        params=dict(resolved.context),
        frame=state.frame,
        section=state.section,
        width=state.width,
        style=style,
        kind=state.kind,
        print_orientation=state.print_orientation,
        holes=state.holes,
        cutboxes=state.cutboxes,
        channels=state.channels,
        funnel_cuts=state.funnel_cuts,
        bores=state.bores,
        ribs=state.ribs,
        plates=state.plates,
        pins=state.pins,
        fields=state.fields,
        text_reliefs=state.text_reliefs,
        regions=state.regions,
        windows=state.windows,
        datums=state.datums,
    )
