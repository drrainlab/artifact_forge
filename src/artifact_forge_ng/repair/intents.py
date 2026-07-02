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


#: Archetypes with a dedicated support-free sibling — the honest route: a
#: manufacturing goal big enough to change the part's construction is an
#: archetype MIGRATION, not a parameter tweak. Each entry pins the preserve
#: list explicitly (source and target must both carry every name), because
#: what "functionally the same" means across a migration is a design
#: decision, not something to infer.
SUPPORT_FREE_VARIANTS: dict[str, dict[str, object]] = {
    "underdesk_cable_clip_v2_molded": {
        "target": "underdesk_cable_clip_v3_sideprint",
        "preserve": [
            "bundle_d", "mouth_gap", "upper_lip_len", "lower_lip_len", "screw",
            "asymmetric_side_hook", "side_facing_mouth", "through_cavity",
            "retaining_lower_lip",
        ],
    },
}


def _make_support_free(instance: ProductInstance, archetype: ArchetypeSpec) -> Patch:
    variant = SUPPORT_FREE_VARIANTS.get(archetype.id)
    if variant is not None:
        return Patch(
            schema="patch/v1",
            type="manufacturing",
            reason=(
                "migrate to the side-print variant: the mounting tongue "
                "lives inside the extruded profile, so the part prints "
                "profile-on-bed with zero overhangs by construction"
            ),
            archetype=str(variant["target"]),
            preserve=list(variant["preserve"]),  # type: ignore[arg-type]
            manufacturing={"support_policy": "none"},
        )
    # Fallback for archetypes without a sideprint sibling: a self-supporting
    # teardrop cavity roof. Honest scope: it fixes the CAVITY overhang;
    # other overhangs (lip cantilevers) may still want supports — the
    # overhang validator reports what remains.
    _require_param(archetype, "cavity_roof", "make_support_free")
    return Patch(
        schema="patch/v1",
        type="manufacturing",
        reason="self-supporting teardrop cavity roof; remaining overhangs reported honestly",
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
