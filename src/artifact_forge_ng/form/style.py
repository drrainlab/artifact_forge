"""Surface styles — the named radius vocabulary of a form family.

``molded_utility_part`` is the flagship's family: large root blends,
rounded contact edges, softened externals, no random organic blobs. The
molded pass (:mod:`.molded`) picks a corner radius by the tags of the
segments meeting at each joint; first match wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SurfaceStyle:
    name: str
    external_edge_r: float = 1.8
    root_blend_r: float = 5.5
    contact_r: float = 2.0
    lip_tip_r: float = 1.5
    #: Ordered (tag, radius-attr) rules for corner rounding.
    corner_rules: tuple[tuple[str, str], ...] = field(
        default=(
            ("lip_tip", "lip_tip_r"),
            ("mouth_corner", "contact_r"),
            ("root", "root_blend_r"),
            ("external", "external_edge_r"),
        )
    )
    # -- biomorphic knobs (all zero on the plain molded style) ---------------
    #: Outward bow of long external profile segments, as a fraction of their
    #: length (organicity-derived; capped in mm by the molded pass).
    bow_amplitude: float = 0.0
    #: Seeded per-segment variation of the bow (asymmetry-derived, 0..1).
    bow_jitter: float = 0.0
    bow_seed: int = 42
    #: Rhythm of biomech vein ridges on archetype-designated back faces.
    vein_rhythm: float = 0.0
    #: How proud a vein ridge stands (mm).
    vein_relief: float = 0.0

    def corner_radius(self, tags: frozenset[str]) -> float:
        for tag, attr in self.corner_rules:
            if tag in tags:
                return float(getattr(self, attr))
        return self.external_edge_r


MOLDED_UTILITY_PART = SurfaceStyle(name="molded_utility_part")

STYLES: dict[str, SurfaceStyle] = {s.name: s for s in (MOLDED_UTILITY_PART,)}

#: Names an instance's ``style.surface`` may select.
STYLE_FAMILIES = ("molded_utility_part", "biomorphic_utility_part")


def resolve_style(instance, archetype) -> SurfaceStyle:
    """Compile the instance's ``style:`` block into a SurfaceStyle.

    ``biomorphic_utility_part`` is NOT a freeform 'make it organic' switch:
    its sliders derive controlled numbers — softness scales the decorative
    radii (contact radii stay engineering-owned), organicity bows external
    non-contact segments outward (adding material, never thinning walls),
    asymmetry jitters the bows deterministically, vein_rhythm drives ridge
    placement on faces the ARCHETYPE designates. Critical topology
    (mouths, slots, screw holes, flat print faces) is untouchable by
    construction — those segments carry contact/intentional tags the
    biomorphic passes exclude.
    """
    from dataclasses import replace

    base = STYLES.get(archetype.surface_style, MOLDED_UTILITY_PART)
    style_block = getattr(instance, "style", None) or {}
    surface = style_block.get("surface", base.name)
    if surface not in STYLE_FAMILIES:
        raise ValueError(
            f"unknown style.surface {surface!r}; known: {STYLE_FAMILIES}"
        )
    if surface != "biomorphic_utility_part":
        return base

    def slider(name: str, default: float) -> float:
        v = float(style_block.get(name, default))
        return max(0.0, min(1.0, v))

    organicity = slider("organicity", 0.4)
    softness = slider("softness", 0.6)
    asymmetry = slider("asymmetry", 0.15)
    vein_rhythm = slider("vein_rhythm", 0.0)
    seed = int(style_block.get("seed", 42))

    soften = 1.0 + 1.2 * softness
    return replace(
        base,
        name="biomorphic_utility_part",
        external_edge_r=base.external_edge_r * soften,
        root_blend_r=base.root_blend_r * soften,
        lip_tip_r=base.lip_tip_r * (1.0 + 0.6 * softness),
        # contact_r deliberately untouched — contact surfaces are
        # engineering parameters, not style.
        bow_amplitude=0.035 * organicity,
        bow_jitter=asymmetry,
        bow_seed=seed,
        vein_rhythm=vein_rhythm,
        vein_relief=1.0 + 1.2 * organicity,
    )
