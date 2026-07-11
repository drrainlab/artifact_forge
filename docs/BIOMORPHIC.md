# Biomorphic Products — section canon

The "Biomorphic Products" section: the Biomechanical Product System library —
useful 3D-printable objects where an engineering function is combined with an
organic/bone/biomechanical form. Two parallel lines:

```
A. Functional Core Archetypes   — engineering cores (function)
B. Biomorphic Skin / Exoskeleton Modifiers — a form layer over allowed regions
```

## Laws of the section

1. **functional core owns function; biomorphic layer owns form.**
   A product is first of all an honest engineering object (load, mounts, fits,
   channels, wall thicknesses, print orientation). The bio layer is applied only
   to safe zones and only after the core passes validation.
2. **Bio package should not own generic mounting logic.**
   The Workshop Mounts Pack is the functional-core provider for all wall /
   under-desk / rail / pipe holders (wall_screw_mount, pegboard, french cleat,
   rail, pipe clamp, zip tie …). Bio versions of mounts are shaped as
   presets/extensions on top of workshop cores (`extends:` — the Bio-4A
   mechanism), NEVER as a new functional core if the function is already
   covered.
3. **A beautiful organic object with broken function is a FAIL.**
   A style claim without validator-backed geometry is a hallucination: the
   feature stays missing / an engine gap (see Honesty below).
4. **The biomorphic layer grows only where the region map allows it.**

## Mapping bio roles → RegionRole

A new enum role is justified only by a new CLASS OF BEHAVIOR (different
modifier targeting, different keepout semantics, a validator that reads it).
Flavor lives in the region's `id`/`label`/`aliases`.

| Role from the spec | RegionRole | Comment |
|---|---|---|
| decorative_outer_shell, exoskeleton_panel | `exoskeleton_panel` (NEW) | the surface where ribs grow AND windows are cut |
| rib_anchor | `rib_anchor` (NEW) | where rib roots are required to land |
| boss/channel/contact/interface keepout | `interface_keepout` (NEW) | behaves identically: vetoes cuts; in PROTECTED_ROLES |
| load_path_region, primary_load_path | `high_stress_region` | already protected; ribs grow TOWARD it |
| window_safe_zone | `aesthetic_lightening` | "material removal is allowed" |
| saddle_contact | `soft_contact_surface` | exact semantic match |
| rail_interface | `mounting_surface` | the role will be added together with the rail modifier |
| screw_zone | `fastener_keepout` | existing |
| snap_root | `high_stress_region` (+ region.snap_root_not_perforated) | existing check |
| secondary_load_surface | — (drop) | nothing reads it; secondary reinforcement is a property of the graph |
| vent_surface | later, together with add_gill_vents | the "a role arrives with its consumer" rule |
| grip_texture_zone | later, together with the handle_grip core | same |
| electronics/water keepout | `interface_keepout` (id flavor) | until dedicated validators appear |

`EXO_PROTECTED_ROLES` (form/exoskeleton/masks.py) is stricter than the global
`PROTECTED_ROLES`: it adds soft_contact/seal/retaining. The global set is NOT
extended with these roles — that would shift the golden fields of existing
archetypes; a sync test guarantees PROTECTED ⊆ EXO_PROTECTED.

## Targeting semantics of bio modifiers

- `apply_biomorphic_exoskeleton`: **primary target `exoskeleton_panel`**
  (the rib-growth surface); fallback `aesthetic_lightening` for plate cores —
  the applicator writes a note when it operates via the fallback.
- `add_bone_windows`: the main consumer of `aesthetic_lightening` (the
  perforation zone). Windows without a graph.
- The shared forbidden set of all bio modifiers: fastener_keepout,
  high_stress_region, soft_contact_surface, retaining_flexure, seal_surface,
  interface_keepout.

## Archetype lifecycle (`maturity`)

```
draft → metadata_only → recipe_valid → form_valid → sandbox_buildable → production_buildable
```

An informational `maturity:` field on ArchetypeSpec (Bio-0). The computed
status (recipe/buildable/metadata_only) remains the source of truth about
buildability. Bio-4A may extend maturity to presets/families/extensions — so
that `angle_grinder_holder_65mm_biomorphic` (a product preset) has its own
life stage.

## Rules for adding a modifier

Every new bio modifier must declare: target roles + forbidden roles (the
shared set above is the minimum), typed params with ranges, validators (what
MEASURES the promise), provides_features (only ones backed by verified_by),
and a golden archetype for the test. A modifier without an applicator is legal
and honest: apply yields an engine-gap WARN and the features are not built
(see organic_taper_outer_shell, biomech_surface_texture — the
"declared ahead of applicator" pattern).

## Load paths

Load-bearing biomorphic products declare force routes on the archetype:

```yaml
load_paths:
  - {from: wall_screw_bosses, to: tool_cradle, priority: primary}
  - {from: lower_flange_zone, to: cantilever_tip, priority: secondary}
```

`from`/`to` are region ids (bound fail-fast at load time). The Bio-2 substrate
uses them as growth seeds; checks: `form.load_paths_connected` (the route
exists in the rib graph), `form.no_load_path_through_keepout` (the polyline is
clean), `form.primary_load_path_has_ribs` (Bio-3: thickened ribs on the
primary path). `form.rib_roots_touch_substrate` covers
"rib_roots_touch_mounting_regions" from the spec. Without load_paths a
heuristic is used (HIGH_STRESS centers + datums), and the checks pass
vacuously.

## Honesty by phase

Bio-2 creates a **verifiable skeleton intent** (IR): rib graph, windows,
masks, debug JSON — form.* checks pass on validate. Materialization into CAD
is Bio-3: verified_by of the bio features includes
`topology.exoskeleton_ribs_materialized` / `topology.organic_windows_open`, so
until Bio-3 the features are honestly **supported-but-not-built** (mark_built
requires ALL verified_by). This is by design.

## Roadmap

The bio track is embedded in the overall project plan: the extends/preset
mechanism (Bio-4A) is built in a later wave, and multi-part bio assemblies
(Bio-6) come after the assembly ports.

- **Bio-0** vocabulary/roles/metadata; **Bio-1** branch clamp core;
  **Bio-2** exoskeleton IR — done in this iteration.
- **Bio-3** Exoskeleton CAD Materialization (the mandatory next step):
  rib graph → smooth ribs (rib_tube_sweep), node blends (metaball_params is
  already in the IR), organic window cuts, welded to substrate; at the same
  time — the organic_taper_outer_shell / biomech_surface_texture applicators.
- **Bio-4A** Workshop Mounts bridge: mapping workshop regions → bio roles,
  the extends/preset/family mechanism, maturity on presets.
- **Bio-4B** biomorphic presets on top of workshop mounts:
  angle_grinder_holder_65mm_biomorphic, heat_gun_holder_bone_windows,
  cable_hose_wall_hook_biomorphic, e27_wall_lamp_socket_holder_biomech,
  branch_tool_mount_adapter_bio.
- **Bio-5** Curved/Cylindrical/Swept surfaces (mapping over curved panels;
  for now the applicator honestly refuses on cylindrical).
- **Bio-6** Biomechanical Motifs & Assemblies: vertebra chains, tendon
  bridges, organic latches, bio dovetail covers, multi-part assemblies.

Future modifiers (roadmap; we do not spawn YAML stubs): add_tendon_ribs,
add_gill_vents, add_segmented_armor_plates, add_pore_field,
add_mycelium_network, add_vertebra_segments, add_load_path_ribs (structural,
shared with Workshop), add_blended_boss_cluster, add_organic_outer_shell,
add_muscle_fillet_transition.

## Quality criterion

A product succeeds when, all at once, it: works functionally; prints without
absurd supports; does not break fits/channels/interfaces; saves plastic where
possible; reinforces load paths where needed; and looks grown, not like a box
with decoration.

## Implicit Exoskeleton Skin (SDF, STL-first) — wave Bio-4M

Bio-4M is the visual/mesh successor to BRep Bio-3 for organic-looking
parts; BRep path remains useful for exact/simple mechanical geometry;
implicit path is required for Giger/bone/grown surfaces.

BRep path remains source of exact mechanical truth (STEP). Implicit mesh
path is source of organic printable appearance (STL).

### Enabling

```yaml
style:
  surface: biomechanical_exoskeleton   # mandatory precondition
  skin: implicit                       # enables the SDF engine
  skin_resolution: 0.4                 # voxel size, mm (0.2–1.0)
  # optional overrides (defaults are derived from organicity o):
  # skin_k_blend: 1.2+2.5o   skin_k_weld: 2.0+2.5o   skin_k_lip: 1.0+1.5o
  # base_inflation: 2.0      # 0 disables the entire organic_base_shell layer
```

`skin: implicit` on any other surface is a ValueError. If an implicit export
is impossible (a revolve/sweep body, pins/lofts, cylindrical fields, no
exoskeleton, scikit-image not installed) — the build fails with an honest
PipelineFailure; there is NO silent fallback to BRep STL.

### SDF assembly order is law (`compiler/implicit/recipe.py`)

```
body hard-union
→ organic_base_shell:            # "grown-ness", not decoration
    canvas_pad                   # a prism over the canvas (window minus masks),
                                 # base_inflation with falloff→0 toward masks —
                                 # interfaces do not swell
    boss_growth                  # spheres r = head_r+3 around bolt columns
    asymmetry_noise              # a few seeded low-freq blobs in the safe canvas
                                 # (small amplitude, clearance to keepouts, deterministic)
→ skin smooth-union (capsules+nodes, k_blend)
→ smin(body+shell, skin, k_weld) # muscle-like fusions
→ smax − window prisms (k_lip)   # lips of the organic windows
→ HARD CUTS LAST                 # bolts (hole_cut_dims — shared source with BRep),
                                 # countersink frustums, driver-access cylinders,
                                 # channels, box cuts, non-organic fields — EXACT
→ keep_in                        # clip by the mate/mounting plane
```

No blob may narrow a functional hole: hard cuts come last, and this is
verified by sampling the ANALYTICAL SDF
(`manufacturing.implicit_skin_fidelity`,
`manufacturing.boss_growth_preserves_fastener_access`,
`manufacturing.skin_assembly_clearance`), not just the mesh.

### Export honesty

- `part.stl` — the production output (marching cubes, watertight,
  byte-deterministic in-house STL writer);
- `part.step` — a simplified BRep reference; in the honesty report this is an
  explicit engine gap: "part.step is the simplified BRep reference; production
  output is part.stl (implicit skin)";
- `exports.stl_source: implicit|brep` + `exports.skin` (voxels, grid,
  triangles, k-parameters);
- **window recesses are explicit honesty**: `exports.skin.organic_windows =
  {mode, through_cuts, reason}`. On a plate the windows are through cuts
  (through_cuts: true — legal for a plate); on the clamp in Bio-4M stage 2 the
  windows will be RECESSES (protecting the saddle/channel) — the user must not
  expect the reference's through windows and get surprised;
- `quality.rectangularity_reduced` — a metric over OUR mesh arrays: the share
  of triangle area with a normal within ≤5° of the axis directions, over the
  skin canvas only (window minus masks, above the panel); threshold 0.55. On
  the pre-flight demo plate it is a checkpoint gate; on other products it is
  WARN-only until we accumulate experience;
- `quality.window_shadow_present` — IR-level: window depth ≥ 2.5 mm, otherwise
  an honest WARN "a shallow engraving instead of a window";
- guards: a 16M voxel budget (exceeding it → auto-coarsening with a WARN),
  resolution ≤ min(min_rib_d/2, min_ligament)/3 (coarser → auto-refinement);
- the `side_profile` orientation mirrors `orient_for_print`; drop-to-bed goes
  by the zmin of the MESH — it differs from BRep by the skin's "proud" height
  (a documented difference).

### Files

`compiler/implicit/{sdf,recipe,from_form,mesh,stl,skin}.py`; the shared
source of fastener dimensions is `core/fasteners.hole_cut_dims` (the BRep
cutter `cad/holes.py` was refactored onto it, behavior identical). Stage 1 is
a planar plate (`biomorphic_exoskeleton_demo_plate_implicit.yaml`);
integration with the clamp's profile_surface mapping is stage B
(`TODO(bio-4m-integration)` in `from_form._planar_skin_geometry`).
