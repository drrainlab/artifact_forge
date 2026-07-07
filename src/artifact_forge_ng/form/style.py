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
    # -- implicit exoskeleton skin (Bio-4M; docs/BIOMORPHIC.md) ----------------
    #: True = production STL comes from the implicit SDF engine
    #: (compiler/implicit), not the BRep tessellation. Legal only on the
    #: biomechanical_exoskeleton surface — resolve_style enforces it.
    implicit_skin: bool = False
    #: Marching-cubes voxel size in mm (0.2 fine .. 1.0 coarse).
    skin_resolution: float = 0.4
    #: Smooth-union radius among skin capsules/spheres and shell parts (mm).
    skin_k_blend: float = 0.0
    #: Smooth-union radius welding shell+skin onto the body (mm).
    skin_k_weld: float = 0.0
    #: Smooth-subtract radius of organic window lips (mm).
    skin_k_lip: float = 0.0
    #: organic_base_shell canvas pad thickness (mm); 0 disables the whole
    #: shell layer (pad + boss growth + asymmetry noise).
    base_inflation: float = 0.0

    def corner_radius(self, tags: frozenset[str]) -> float:
        for tag, attr in self.corner_rules:
            if tag in tags:
                return float(getattr(self, attr))
        return self.external_edge_r


MOLDED_UTILITY_PART = SurfaceStyle(name="molded_utility_part")

#: The biomorphic pack's signature skin (docs/BIOMORPHIC.md): bone-like
#: softened radii + bows and veins ON by default. A real STYLES entry —
#: bio archetypes declare it as their ``surface_style`` — while structure
#: (rib density, window scale) stays in MODIFIER params, never in style.
BIOMECHANICAL_EXOSKELETON = SurfaceStyle(
    name="biomechanical_exoskeleton",
    external_edge_r=2.4,
    root_blend_r=7.0,
    lip_tip_r=1.8,
    # contact_r stays at the engineering default — untouchable by style.
    bow_amplitude=0.05 * 0.6,
    bow_jitter=0.2,
    bow_seed=42,
    vein_rhythm=0.5,
    vein_relief=1.6,
)

STYLES: dict[str, SurfaceStyle] = {
    s.name: s for s in (MOLDED_UTILITY_PART, BIOMECHANICAL_EXOSKELETON)
}

#: Names an instance's ``style.surface`` may select.
STYLE_FAMILIES = (
    "molded_utility_part", "biomorphic_utility_part",
    "biomechanical_exoskeleton",
)


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
    skin = style_block.get("skin")
    if skin not in (None, "implicit"):
        raise ValueError(
            f"unknown style.skin {skin!r}; the only implemented skin engine "
            "is 'implicit' (Bio-4M)"
        )
    if skin == "implicit" and surface != "biomechanical_exoskeleton":
        raise ValueError(
            "style.skin: implicit requires style.surface "
            f"biomechanical_exoskeleton; {surface!r} has no implicit skin "
            "engine (docs/BIOMORPHIC.md, Bio-4M)"
        )
    if surface not in ("biomorphic_utility_part", "biomechanical_exoskeleton"):
        return base

    def slider(name: str, default: float) -> float:
        v = float(style_block.get(name, default))
        return max(0.0, min(1.0, v))

    if surface == "biomorphic_utility_part":
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

    if surface == "biomechanical_exoskeleton":
        # same five sliders, biomech defaults — bows/veins on unless dialed
        organicity = slider("organicity", 0.6)
        softness = slider("softness", 0.5)
        asymmetry = slider("asymmetry", 0.2)
        vein_rhythm = slider("vein_rhythm", 0.6)
        seed = int(style_block.get("seed", 42))

        # Bio-4M implicit skin knobs: the smooth-blend radii derive from
        # organicity (more organic = fatter muscle transitions); every knob
        # accepts an explicit style override. base_inflation defaults to
        # ~2 mm of "grown shell" on biomech parts; 0 disables the shell.
        skin_knobs: dict[str, float | bool] = {}
        if skin == "implicit":
            resolution = float(style_block.get("skin_resolution", 0.4))
            skin_knobs = {
                "implicit_skin": True,
                "skin_resolution": max(0.2, min(1.0, resolution)),
                "skin_k_blend": float(
                    style_block.get("skin_k_blend", 1.2 + 2.5 * organicity)
                ),
                "skin_k_weld": float(
                    style_block.get("skin_k_weld", 2.0 + 2.5 * organicity)
                ),
                "skin_k_lip": float(
                    style_block.get("skin_k_lip", 1.0 + 1.5 * organicity)
                ),
                "base_inflation": max(
                    0.0, float(style_block.get("base_inflation", 2.0))
                ),
            }

        soften = 1.0 + 1.2 * softness
        return replace(
            BIOMECHANICAL_EXOSKELETON,
            external_edge_r=MOLDED_UTILITY_PART.external_edge_r * soften,
            root_blend_r=MOLDED_UTILITY_PART.root_blend_r * soften,
            lip_tip_r=MOLDED_UTILITY_PART.lip_tip_r * (1.0 + 0.6 * softness),
            bow_amplitude=0.05 * organicity,
            bow_jitter=asymmetry,
            bow_seed=seed,
            vein_rhythm=vein_rhythm,
            vein_relief=1.2 + 1.2 * organicity,
            **skin_knobs,
        )

    return base
