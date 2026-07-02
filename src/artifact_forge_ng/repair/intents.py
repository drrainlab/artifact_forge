"""Goal-oriented edit intents — the deterministic dictionary between "what
the user wants" and a typed YAML patch. The phase-4 LLM will translate
free text INTO one of these (or a raw patch); the intents themselves never
guess: an intent that does not apply to an archetype refuses loudly.

Every intent ships its own ``preserve`` list — the contract of "functionally
the same" — which the edit pipeline verifies after the rebuild.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..product.archetype import ArchetypeSpec
from ..product.instance import ProductInstance
from .patch import ModifierOps, Patch

FIELD_MODIFIER_IDS = (
    "add_hex_perforation",
    "add_grid_slot_field",
    "add_voronoi_field",
)


class IntentNotApplicable(ValueError):
    pass


@dataclass(frozen=True)
class IntentSpec:
    name: str
    patch_type: str
    description: str
    build_patch: Callable[[ProductInstance, ArchetypeSpec], Patch]


def _functional_preserve(archetype: ArchetypeSpec) -> list[str]:
    """Everything the user can see and feel: exposed functional parameters
    plus the contract's must-have features."""
    names = [
        name
        for name, spec in archetype.parameters.items()
        if spec.exposed and spec.role == "functional"
    ]
    names.extend(f for f in archetype.contract.must_have if f not in names)
    return names


def _require_param(archetype: ArchetypeSpec, param: str, intent: str) -> None:
    if param not in archetype.parameters:
        raise IntentNotApplicable(
            f"intent {intent!r} needs parameter {param!r}, which archetype "
            f"{archetype.id!r} does not have"
        )


def _make_support_free(instance: ProductInstance, archetype: ArchetypeSpec) -> Patch:
    _require_param(archetype, "cavity_roof", "make_support_free")
    return Patch(
        schema="patch/v1",
        type="manufacturing",
        reason="print without supports, functionally identical",
        preserve=_functional_preserve(archetype)
        + [n for n in ("screw_spacing", "screw") if n in archetype.parameters],
        params={"cavity_roof": "teardrop"},
        manufacturing={"support_policy": "none"},
    )


def _make_biomorphic(instance: ProductInstance, archetype: ArchetypeSpec) -> Patch:
    return Patch(
        schema="patch/v1",
        type="style",
        reason="biomorphic skin, engineering untouched",
        preserve=_functional_preserve(archetype),
        style={
            "surface": "biomorphic_utility_part",
            "organicity": 0.5,
            "softness": 0.7,
            "asymmetry": 0.15,
            "vein_rhythm": 0.35,
        },
    )


def _remove_perforation(instance: ProductInstance, archetype: ArchetypeSpec) -> Patch:
    present = [m.id for m in instance.modifiers if m.id in FIELD_MODIFIER_IDS]
    if not present:
        raise IntentNotApplicable(
            "intent 'remove_perforation': the instance has no field modifiers"
        )
    return Patch(
        schema="patch/v1",
        type="style",
        reason="remove lightening/perforation fields",
        preserve=_functional_preserve(archetype),
        modifiers=ModifierOps(remove=present),
    )


def _make_stronger(instance: ProductInstance, archetype: ArchetypeSpec) -> Patch:
    bumps = {
        name: delta
        for name, delta in (("wall", "+0.8mm"), ("flange_t", "+1mm"),
                            ("plate_t", "+1mm"), ("base_t", "+1mm"),
                            ("rest_t", "+1mm"), ("thickness", "+1mm"))
        if name in archetype.parameters
    }
    if not bumps:
        raise IntentNotApplicable(
            f"intent 'make_stronger': no thickness-like parameters on "
            f"{archetype.id!r}"
        )
    return Patch(
        schema="patch/v1",
        type="structural",
        reason="thicken load-bearing walls",
        preserve=_functional_preserve(archetype),
        params=bumps,
    )


INTENTS: dict[str, IntentSpec] = {
    spec.name: spec
    for spec in (
        IntentSpec(
            "make_support_free", "manufacturing",
            "self-supporting geometry, same function — no printed supports",
            _make_support_free,
        ),
        IntentSpec(
            "make_biomorphic", "style",
            "organic skin (bows, softened radii, veins) over the same engineering",
            _make_biomorphic,
        ),
        IntentSpec(
            "remove_perforation", "style",
            "strip lightening fields back to a solid part",
            _remove_perforation,
        ),
        IntentSpec(
            "make_stronger", "structural",
            "thicken walls/plates while keeping every functional dimension",
            _make_stronger,
        ),
    )
}
