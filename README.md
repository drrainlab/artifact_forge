# Artifact Forge — YAML Product Grammar Engine

A deterministic-first generator of 3D-printable functional parts. The
source of truth is a typed YAML Product Grammar (a catalog of archetypes +
a product instance), not a free-form LLM spec. The geometry brain is the
catalog, the CAD-free Form IR and the validator registry; an LLM is only
ever a translator of intent into YAML — and everything works without one.

The engine's rule is **honesty**: a feature is only claimed as built after
its validators PASS on the measured geometry; an unknown op / check /
joint name is a load error, never a silent skip; a critical failure is a
failing exit code, never a prettified report.

## Pipeline

```
product.yaml
  → catalog load (fail-fast binding of every name)
  → parameter resolve (units, expr, clamps, declaration order)
  → capability report (requested / supported / built / missing)
  → Form IR (exact line/arc profiles, semantic regions — NO CadQuery)
  → form validators (golden gate: CAD is not touched until these pass)
  → compile_part (CadQuery: profile extrusion, weld, blends, holes, fields)
  → geometry validators (topology / region / manufacturing probes)
  → contract + score (critical FAIL → grade F; the score can't mask it)
  → honesty report + STL/STEP
```

More detail: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (layers,
registries, the pack extension point) and
[docs/VALIDATION.md](docs/VALIDATION.md) (check levels and the honesty
model).

## Quickstart

```bash
uv sync --extra cad                 # environment (the form layer also works without cad)
uv run forge validate catalog/examples/desk_cable_clip_20mm.yaml   # no CAD needed
uv run forge build    catalog/examples/desk_cable_clip_20mm.yaml -o out
uv run forge ui                     # local web cockpit (extra [web])
uv run pytest -m "not cad"          # fast IR tier (~2 minutes, no cadquery)
uv run pytest                       # full suite including CAD-tier probes
```

`import artifact_forge_ng` never loads the CAD kernel; cadquery is only
needed by `forge build`. No API keys are required for the core, the CLI
or the tests — an Anthropic key only enables the optional LLM intent
translator in the web cockpit (see `.env.example`).

## Key guarantees

- **built ⊆ supported** at the pydantic-schema level: an unsupported
  feature physically cannot serialize as built; a feature is built ⟺ all
  of its `verified_by` validators PASS.
- **A symmetric C-ring is unrepresentable by accident**: mouth, lips and
  wall are one closed 2D contour; clamps (`lower ≥ 1.6×upper`,
  `mouth_gap ≤ 0.7×bundle_d`) live in the archetype YAML; topology probes
  measure the real solid.
- **strict mode**: unknown validator = load error; unsupported requested
  feature = fail; critical topology fail = non-zero exit; no fallbacks.
- **Repair is YAML patches only** (`+3mm` / absolute / expr) re-validated
  through the same schemas; rules are deterministic, surviving findings
  become engine_gaps.

## Source tree

```
src/artifact_forge_ng/
  core/        units, sandboxed-AST expr, value grammar, findings
  product/     pydantic schemas (archetype/instance/modifier/contract), resolver, capability
  catalog/     loader + data/ (features.yaml, modifiers/, archetypes/)
  form/        Form IR: sections (line/arc), profiles, regions, fields,
               recipe-op registry (recipe_ops_core + op family modules),
               checks_* validators — never imports cadquery (tested)
  archetypes/  Python form builders bound to catalog sections
  modifiers/   typed, region-bound IR transformations
  validators/  check registry (probes.py) + topology/region/manufacturing probes
  cad/         Geometry seam, booleans (weld), fillets, holes, probes
  compiler/    wires → solids (compile_part) → build pipeline; implicit/ SDF skin
  assembly/    assembly/v1: joints registry, poses, BOM, reports
  review/      score (hard gate), honesty report
  repair/      YAML patches + deterministic rules (forge edit)
  web/         Product Cockpit — local engineering debugger
  packs.py     the extension point: domain packs plug in via entry points
```

## Catalog

| Archetype | What it is | Key checks |
|---|---|---|
| `underdesk_cable_clip_v2_molded` | flagship: asymmetric side-entry desk clip | not_symmetric_c_ring, mouth/lips, screw_access |
| `adapter_plate_v1` | adapter plate: 2 hole patterns + rim | min_web, holes_within_outline |
| `cable_comb_v1` | cable comb: cavity+throat per cable | slots_open, throat_retention |
| `zip_tie_anchor_v1` | zip-tie anchor (omega tunnel) | tunnel_fits_tie, tunnel_open |
| `wall_hook_v1` | J-hook on screws | tip_lip_present, bay_open |
| `lamp_socket_cup_v1` | E27/GU10 socket cup (revolve) | revolve_axis_clear, cavity_open |
| `lamp_bracket_v1` | lamp bracket with a wiring channel | channel_continuous along the L-path |
| `phone_stand_v1` | phone stand | slot=f(tilt) exact, stability_footprint (COM) |
| `enclosure_base_v1` + lids | electronics box family (YAML-only recipe) | shell_walls_ok, snap/lid joints |
| `bearing_turntable_base_v1` | 608 bearing seat + phyllotaxis spiral | bearing lip measured |

Examples: [catalog/examples](catalog/examples) — every one builds with
`forge build` at grade pass/A. The bracket+cup pair mates: datum
`arm_tip` ↔ bolt circle `mount_bc`.

## Modifiers (Modifier Kernel v1)

Typed, region-bound transformations over the Form IR — a modifier may
never break product topology. The archetype owns the function; the
modifier owns the adaptation. Each one: reads its target region → derives
keepouts (protected regions + holes + cuts of earlier modifiers) → emits
IR features → the compiler cuts/welds exactly those → validators confirm →
only after PASS is the feature counted as built.

| Modifier | Kind | Guarantee |
|---|---|---|
| `add_hex_perforation` | field | web between cells ≥ wall_gap (measured!) |
| `add_grid_slot_field` | field | slots entirely outside keepouts |
| `add_voronoi_field` | field | stable seed (same YAML → same object), Lloyd relaxation, ligament ≥ min_ligament |
| `add_magnet_pockets` | interface | blind pockets, the skin behind the floor verified intact |
| `add_zip_tie_slots` | interface | a through slot pair, fails if a keepout interferes |
| `add_ribs` | structural (additive) | ribs welded (weld rule) and probe-confirmed |

All fields take `cut_mode: through | recess`. Functional tweaks
(mouth_gap etc.) are repair-layer YAML patches, NOT modifiers.

## Bio-organic SurfaceStyle

`style: {surface: biomorphic_utility_part, organicity, softness,
asymmetry, vein_rhythm, seed}` is not "make it organic" — it compiles
sliders into controlled form passes: softness scales decorative radii
(contact_r is engineering, untouched); organicity bows long outer profile
edges outward (material is only added, walls never thin); asymmetry is a
deterministic, seeded jitter; vein_rhythm lays ridge veins across the
spine. Untouchable by construction: contact surfaces, mouths/slots, the
flat print base, fasteners, the silhouette family. See
[docs/BIOMORPHIC.md](docs/BIOMORPHIC.md) and `phone_stand_bio.yaml`.

## Product Cockpit (forge ui)

`uv run forge ui` (extra `[web]`) starts a local cockpit — a **visual
debugger of engineering truth**, not a "chat + 3D viewer". Every panel is
a view model over the same pipeline (CLI ↔ Cockpit parity is pinned by a
test). The heart is the CAD-free `/api/validate` (live sliders, wizard,
patch preview). Five lenses: 3D (STL + assembly poses), Section (exact
SVG from IR segments), Region, Honesty (requested/supported/built/
verified), Manufacturing. The LLM (Anthropic) is strictly an
intent/patch translator; without a key the cockpit honestly shows
LLM: OFF and works deterministically (bilingual keyword intents + intent
buttons). Errors are always structured findings, never a traceback.

## Verified Assemblies (assembly/v1)

An assembly is a typed object, not a textual agreement between parts.
`forge validate|build` accept `assembly/v1` with the same commands: the
root part is the single frame of reference, parts are inline
(self-contained), `shared:` injects mating dimensions ONCE (a desynced
bolt circle is unrepresentable), joints come from a fail-fast registry.
Checks run in two echelons: joint IR BEFORE any CAD (bolt circles
coincide in the pose, clear↔tap diameters compatible) and fit probes in
the assembled pose after per-part builds: `assembly.no_interference`,
`assembly.screw_axes_clear`, and `assembly.channel_continuous_across` —
the cable passes through EVERY part (per-segment worst case). Each part
prints in its own orientation; `assembled.step` is a posed compound,
`assembly_report.yaml` carries poses/joints/grade. Demos:
`desk_lamp_e27.yaml` (bracket + E27 cup, 4×M4, through wiring) and
`esp32_box_with_lid.yaml` (lid_seat dimension chain + screw_joint +
press_fit_pin_pair with measured interference).

## Geometry Builders & Recipes

The canonical builder registry — [docs/BUILDERS.md](docs/BUILDERS.md):
`archetype = what we make · builder = by which technique · modifier = how
we adapt it`. The builder contract: geometry + semantic regions + frame
keys + validators — all four, or it's a hallucination. Recipe archetypes
(`form: {type: recipe, ops: [...]}`) compose registered ops directly in
YAML with no new Python; ops bind fail-fast at catalog load, and the
catalog REFUSES a recipe that isn't subscribed to its ops' validators.

## Semantic Edit (forge edit)

An edit is a **rebuild from the semantic source**, never mesh surgery:

```bash
uv run forge edit catalog/examples/desk_cable_clip_20mm.yaml \
    --intent make_support_free -o out
```

Patches are typed (functional / manufacturing / structural / style) and
carry a **preserve contract**: the listed parameters must come out of the
rebuild numerically identical, and features validator-built. A violation
fails the edit (checked, not promised). Intents v1: `make_support_free`,
`make_biomorphic`, `remove_perforation`, `make_stronger`. A patch can even
migrate between archetypes of one object_class — `make_support_free`
moves the clip to a side-print variant whose print orientation has zero
overhangs by construction (verified by `form.constant_section` and an
honest `manufacturing.overhang`).

## Domain packs

The engine is open-core. Domain packs plug in through the
`artifact_forge_ng.packs` entry-point group: a pack registers its recipe
ops, checks and joints into the same fail-fast registries, contributes
catalog data and pipeline report hooks (see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)). Commercial packs may define
additional terms for outputs produced from those packs.

The **official showcase pack**
([packs/official/artifact-forge-showcase](packs/official/artifact-forge-showcase),
free, Apache-2.0) ships parts across four domains — an under-desk audio
interface mount, barbed hose adapters (vacuum / drain / garden), an
edge-registered drilling jig with steel bushings, and a tolerance
ladder — every one validator-backed with honest non-claims. The path for
your own: download → run the showcase → copy a
[community template](community/) → build your pack → send a PR.

## Licensing

The core engine is **Apache-2.0** ([LICENSE](LICENSE)). Models you
generate from the open-core archetypes are **yours to use** — print them,
sell the prints, remix the YAML. Vendored third-party code is listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Known limitations

- The CAD tier needs `cadquery` (heavy install); CI runs the fast IR tier,
  the CAD tier is expected to run locally.
- The web cockpit is a local engineering tool, not a hosted product.
- Geometry checks measure what they declare — parts outside the archetype
  vocabulary need a new archetype or a pack, not a prompt.
