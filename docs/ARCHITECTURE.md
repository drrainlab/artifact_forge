# Architecture

Artifact Forge is a deterministic-first YAML Product Grammar engine for
3D-printable parts. A product is YAML bound against a typed catalog
(archetypes, features, modifiers, interfaces); the engine builds a CAD-free
Form IR, measures it with registered checks, and only then compiles solids.
Two rules run through every layer:

- **Honesty** — a feature is only claimed as built after its validators
  PASS; an unknown op / check / joint name is a load error, never a silent
  skip. See [VALIDATION.md](VALIDATION.md).
- **The CAD boundary** — `import artifact_forge_ng` never loads the CAD
  kernel. cadquery is an optional extra (`[cad]`) imported lazily by the
  compile step only; everything up to and including form validation is
  stdlib + pydantic + PyYAML.

## Layer map

```
core ──► product ──► catalog ──► form ──► validators ──► compiler ──► assembly
                                  (IR)                  (CAD boundary)
                                                              │
                                              repair / review ┴─► web cockpit
```

| Layer | Package | Responsibility |
|---|---|---|
| core | `core/` | Primitives shared by everything: the `Finding`/`Status`/`Level` result shape, the scalar value grammar (`"20mm"`, bare numbers, `expr(...)` formulas), units, fastener tables. |
| product | `product/` | Typed pydantic models of the grammar: `ArchetypeSpec`, `ProductInstance`, modifiers, interfaces, the contract IR, parameter resolution (one parameter at a time, in declaration order — default, then clamp), and the capability resolver (requested vs supported vs built). |
| catalog | `catalog/` | YAML → validated models with fail-fast name binding (see below). Merges built-in data, pack data dirs, and the repo-level local catalog. |
| form | `form/` | The Form IR: exact 2D section profiles (line/arc segments — no mesh, no tolerance fuzz), typed 3D features, semantic regions, and the `form.*` check implementations. Recipe ops live here. CAD-free by architectural rule, enforced by a test. |
| validators | `validators/` | The check-name registry (`KNOWN_CHECKS`, importable without cadquery) plus the geometry probe implementations (topology / region / manufacturing), which do import cadquery and are loaded lazily by the compiler. |
| compiler | `compiler/`, `cad/` | **The CAD boundary.** `compile_part` turns a `PartForm` into a cadquery solid — it never invents positions; every hole, cut, and field comes from the IR. Runs geometry validators, bakes the print orientation into exports, writes STL/STEP. |
| assembly | `assembly/` | Multi-part products: the joint registry, deterministic pose math (quarter-turn rotations, no solver), IR-level joint checks without CAD, and cross-part fit probes in the assembled pose at build time. |
| repair / review | `repair/`, `review/` | Deterministic semantic repair (findings → YAML patches through an ordered rule table; edit = rebuild from semantic source, never mesh surgery) and the review layer (honesty report, shape quality, score with the critical-FAIL gate). |
| web cockpit | `web/` | Local FastAPI UI. One rule: the UI shows what the pipeline produced. `/api/validate` is fast, CAD-free, and returns structured findings, never a traceback. An LLM is only an optional translator of intent into YAML — everything works without one. |

The pre-CAD pipeline (`pipeline.py`) is shared by `forge validate` and
`forge build`: catalog load → instance cross-validation → parameter
resolution → capability report → form builder → modifiers → form
validators. The assembly pipeline runs each inline part through exactly
this same code path.

## The registry pattern

Three registries decouple catalog YAML from engine code. All follow the
same convention: **declarations are importable without cadquery,
implementations self-register at import time, and every name a YAML
document uses is bound fail-fast at catalog load.**

| Registry | Module | Bound by |
|---|---|---|
| `KNOWN_CHECKS` | `validators/probes.py` | Every `validators:`, `forbidden_forms:`, `contract:` and `verified_by:` entry in catalog YAML. Unknown name = `CatalogError`. |
| `RECIPE_OPS` | `form/recipe_ops_core.py` | Every op invocation in a `form.type: recipe` archetype. An op present in YAML but absent from the registry is a `CatalogError`. |
| `JOINT_TYPES` | `assembly/joints_core.py` | Every joint in an assembly YAML. Unknown joint type = `CatalogError` listing the known types. |

Self-registration: check implementations attach to their declaration via
`register_probe(name)` when their module imports (registering an
*undeclared* name raises immediately); recipe ops and joints call a
module-local `_register()` on import. Form builders follow the same idea
via `FORM_BUILDERS` in `archetypes/__init__.py` — a section name with no
registered builder is an honest capability gap, not a crash.

Recipe ops bind fail-fast twice over: the op name must exist in
`RECIPE_OPS`, **and** every validator the op declares must appear in the
archetype's own `validators:` list — a builder can never ship geometry its
checks won't measure. This is the honesty rule applied to composition.

## Domain packs

`packs.py` is the extension point. A *pack* is an installed distribution
that plugs archetypes, recipe ops, checks, and joints into the registries
through one entry point in the `artifact_forge_ng.packs` group:

```toml
[project.entry-points."artifact_forge_ng.packs"]
mypack = "my_pack:register"
```

`register(ctx)` receives a `PackContext` and:

- self-registers ops / checks / joints by importing its own modules (the
  same import-time `_register` convention the core families use);
- contributes catalog data dirs via `ctx.add_data_dir(...)` — each dir
  mirrors core's layout (optional `features.yaml`, `archetypes/`,
  `modifiers/`);
- may add pipeline hooks: extra assembly-level findings, extra assembly
  report sections, extra single-part report sections.

Guarantees:

- **Deterministic order** — entry points load sorted by name.
- **Idempotent** — discovery runs once per process.
- **Fail-fast on collisions** — a pack that overwrites an existing
  `RECIPE_OPS` / `JOINT_TYPES` entry, an existing check declaration, or an
  already-attached check implementation raises `PackError`, unless it
  first opted in explicitly via `ctx.declare_override(name)`. A broken
  pack is loud, never skipped. Duplicate feature / modifier / archetype
  ids across packs and core are `CatalogError`s.
- **Opt-out** — `ARTIFACT_FORGE_DISABLE_PACKS=1` skips discovery entirely
  (core-only mode, used by the core-only release gate).

The single call site is `catalog.loader.load_catalog` — every pipeline
(CLI validate/build, web, tests) loads the catalog first, so packs are
registered before any YAML binds against the registries.

## The Form IR

`PartForm` (`form/part.py`) is the complete intermediate representation of
one part: everything the CAD compiler consumes and everything the
validators measure, in one serializable-shaped object.

- **Section profile** — a closed loop of tagged line/arc segments in exact
  2D coordinates. Mouth gaps and lip lengths are read from segment
  parameters, not from a mesh, so form validation needs no CAD kernel.
- **Typed features** — `HoleFeature`, `BoreFeature`, `CutBoxFeature`,
  `ChannelCutFeature`, `FunnelCutFeature`, `RibFeature`, `PinFeature`,
  `LoftFeature`, `PlateFeature`, `FieldFeature` (perforation fields
  already filtered against every keepout — countable, checkable, no
  guessing). Each carries its own construction invariants (e.g. a loft
  must taper so the printed arm is self-supporting) and, where relevant, a
  probe polyline the geometry validators reuse.
- **Semantic regions and windows** — named regions the archetype declares;
  `FaceWindow` is an oriented modifier canvas for non-horizontal faces.
- **Frame keys and datums — the inter-part contract.** `frame` is the
  per-family measurement vocabulary (key numbers the builder publishes,
  surfaced in reports); `datums` are named anchor frames that ops publish
  at build time. Joints pose part B by landing its datum on part A's
  datum; declared interfaces are verified to have their datum published
  with the frame keys their type requires (`interface.frame_exists`).
  The compatibility matrix (`forge compat`) is *derived* from declared
  interfaces — there is no hand-written matrix by design.
- **`print_orientation`** — how the part sits on the print bed
  (`as_modeled`, `side_profile`, `saddle_up`). Validators always measure
  in the part frame; only the exported STL/STEP are rotated, so a
  constant-section extrusion printed on its side has zero overhangs by
  construction.

Modifiers (`modifiers/`) are the typed transformation kernel over this IR:
an applicator never free-cuts — it reads its target semantic region,
derives keepouts from the protected regions around it, emits IR features,
and its promises are only marked built after its validators PASS.

## Source tree

```
src/artifact_forge_ng/
├── __init__.py        public API: run_pre_cad, load_catalog, PartForm, Finding, packs
├── pipeline.py        the shared pre-CAD pipeline (YAML → validated Form IR)
├── cli.py             forge validate / build / edit / ui / compat
├── packs.py           entry-point pack discovery, PackContext, collision guards
├── core/              findings, value grammar, units, fastener tables
├── product/           pydantic grammar models, param resolve, capability, contract IR
├── catalog/           loader (fail-fast name binding), built-in YAML data, compat matrix
├── form/              Form IR: section profiles, part features, recipe ops, form checks
├── archetypes/        Python form builders + the FORM_BUILDERS registry
├── modifiers/         region-bound IR transformations (fields, structural, interface)
├── validators/        KNOWN_CHECKS registry + topology/region/manufacturing probes (cad)
├── compiler/          compile_part, field cutters, implicit skin, build pipeline (cad)
├── cad/               cadquery wrappers: geometry, booleans, holes, probes (cad)
├── assembly/          joint registry, pose math, assembly validate/build, BOM, swap
├── repair/            deterministic semantic repair: intents, patches, rule table
├── review/            honesty report, quality metrics, score with the critical gate
└── web/               local cockpit: FastAPI app, job runner, optional LLM intent
```

Related repo directories: `catalog/examples/` (product YAML to try),
`catalog/local/` (user catalog merged at load), `packs/` (in-repo pack
workspace members), `tests/` (fast IR tier runs with `-m "not cad"`).
