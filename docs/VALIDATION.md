# Validation

Validation is not a stage of this engine; it is the engine's spine. Every
claim the pipeline makes — "this feature is built", "this forbidden form
is absent", "these parts fit" — is backed by a named check that actually
ran and PASSed on measured geometry.

## The honesty rule

Three commitments, enforced structurally rather than by convention:

1. **A feature is only claimed after its validators PASS.** The capability
   resolver (`product/capability.py`) tracks *requested* vs *supported* vs
   *built*. `built` can only be written by `mark_built`, which requires
   every check in the feature's `verified_by` list to have PASSed — and
   the pydantic schema itself enforces `built ⊆ supported`, so an
   unsupported feature literally cannot serialize as built.
2. **An unknown name is a load error, never a silent skip.** Every check
   name in YAML (`validators:`, `forbidden_forms:`, `contract:`,
   `verified_by:`) binds against the `KNOWN_CHECKS` registry at catalog
   load; every recipe op against `RECIPE_OPS`; every joint type against
   `JOINT_TYPES`. A typo is a `CatalogError` before any geometry exists.
3. **A check whose implementation is unavailable honestly does not run.**
   Declarations live in `validators/probes.py` (importable without
   cadquery); implementations attach via `register_probe` when their
   module imports. If the implementation is missing in this environment,
   the check is reported as an ENGINE GAP finding and any feature it
   verifies stays honestly un-built — never a silent no-op that still
   claims its features.

## Check levels

Check names follow `<level>.<check>`; the level tells you *where the
measurement happens*:

| Level | Measured on | Examples | Critical? |
|---|---|---|---|
| `form.*` | The Form IR — analytically, zero CAD. Exact line/arc profiles mean no tolerance fuzz. | `form.profile_closed`, `form.wall_thickness`, `form.min_web_between_holes` | Per-finding |
| `interface.*` | Split: form-time checks measure published datums and port frames on the IR (`interface.frame_exists`, `interface.normal_points_outward`); assembly-time checks measure mates in the pose (`interface.mate_compatible`, `interface.clearance_ok`). | | Per-finding |
| `topology.*` | The compiled cadquery solid, via geometry probes. | `topology.single_connected_solid`, `topology.bores_open`, `topology.ribs_present` | **Yes** |
| `region.*` | The compiled solid, restricted to declared semantic regions. | `region.keepouts_preserved`, `region.snap_root_not_perforated` | **Yes** |
| `manufacturing.*` | The compiled solid / exported mesh, against printer constraints. | `manufacturing.min_wall`, `manufacturing.bed_fit`, `manufacturing.overhang`, `manufacturing.mesh_manifold` | Caps the grade |
| `assembly.*` | Cross-part checks in the assembled pose. | `assembly.no_interference`, `assembly.screw_axes_clear`, `assembly.channel_continuous_across` | **Yes** |
| `quality.*` | Shape-quality scoring; WARN-oriented, never blocks a topologically correct build. | `quality.moldedness`, `quality.silhouette_match` | No |

The same physical property is often checked twice, once per side of the
CAD boundary: `form.mouth_opens_sideways` reads tagged profile segments on
the IR; `topology.mouth_opens_sideways` probes the actual void through the
wall of the compiled solid. The form check gates cheaply and early; the
topology probe verifies the compiler kept the promise.

Which checks run is archetype-driven: a handful of universal form checks
always run; the rest come from the archetype's own `validators:` list, so
one product family is never judged by another family's checks. Recipe ops
make this mandatory in the other direction too — the loader refuses an
archetype that uses an op without subscribing to the op's declared
validators.

## Two-tier flow: `forge validate` vs `forge build`

```
forge validate product.yaml        # pre-CAD golden gate — no cadquery
  catalog load (fail-fast binding)
  → instance cross-validation
  → parameter resolve (units, expr, clamps, declaration order)
  → capability report (requested / supported / unsupported)
  → Form IR build + modifiers
  → form + interface(form-time) validators
  → exit non-zero on critical failure (strict)

forge build product.yaml -o out    # all of the above, then CAD
  → compile_part (cadquery — the first import of the kernel)
  → geometry validators (topology / region / manufacturing probes)
  → contract + score (critical FAIL → grade F, regardless of numbers)
  → honesty report + STL/STEP (print orientation baked into exports)
```

`forge validate` writes nothing to disk and never imports cadquery — it
is the golden gate that runs in CI without the CAD stack (`pytest -m "not
cad"` is the matching fast test tier). `forge build` refuses to compile a
form that failed its own IR checks (`enforce_strict` runs *before*
`compile_part`), then measures the compiled solid and finalizes:

- the **honesty report** (`review/honesty.py`): requested / supported /
  PROVEN-built / missing features, which forbidden forms were checked and
  with what verdict (`absent` / `present` / `unchecked`), and which gaps
  the engine admits to. It is assembled only from the typed capability
  report and the validation evidence, so it cannot disagree with either.
- the **score** (`review/score.py`): a numeric grade with a hard gate — a
  critical FAIL at contract/topology/region level forces status FAIL and
  grade F no matter how good the numbers look. Score answers "how good is
  it?"; the gate answers "is it even the right product?" — the gate wins.

Both commands accept single products and assemblies; the CLI dispatches on
the document's `schema:` marker.

## The findings model

Every validator, reviewer, and repair rule speaks one result shape —
`Finding` in `core/findings.py`:

| Field | Meaning |
|---|---|
| `check` | The registered check name (`form.wall_thickness`, ...). |
| `status` | `pass` / `warn` / `fail`; a report's status is the worst finding. |
| `level` | Which validation level produced it. |
| `critical` | A critical FAIL forces overall FAIL regardless of score. FAILs at contract / topology / region / assembly level are critical by definition (`CRITICAL_LEVELS`). |
| `measured` / `limit` / `unit` | The actual number vs the threshold — findings carry evidence, not just verdicts. |
| `suggestion` | A actionable hint; also feeds the deterministic repair rules. |

`ValidationReport` aggregates findings per run; `report.passed(check)` is
true only if the check *ran* and its worst finding is PASS — absence of
evidence is never evidence of absence.

## Forbidden forms and contract binding

An archetype's contract names what the product **must** contain
(`must_have`: feature ids, each verified through its `verified_by`
checks) and what it **must not** degenerate into (`must_not_have` /
`forbidden_forms`). Forbidden form ids bind at load time against
`FORBIDDEN_FORM_DETECTORS` — a map from form id to the check whose
FAILURE means the form is PRESENT (e.g. `closed_ring` is detected by
`form.mouth_opens_sideways` failing). Contract invariants compile to
closures over the sandboxed expression evaluator and run against the
fully resolved parameter context. A detected forbidden form is a critical
contract FAIL; an unchecked one is reported as `unchecked` in the honesty
report, not assumed absent.

## How joints verify assemblies

The assembly pipeline mirrors the single-part discipline exactly
(`assembly/pipeline.py`): everything IR-checkable runs without CAD, and
the build step adds cross-part geometry probes.

**IR checks in the pose (no CAD).** Each joint type in `JOINT_TYPES`
declares an `ir_check(form_a, form_b, pose, joint)`. Poses are
deterministic — quarter-turn Euler rotations plus a translation that lands
part B's datum on part A's datum; exact integer arithmetic, no solver.
IR-level joint checks verify things like coincident bolt patterns with
compatible diameters, lid dimensions chaining to the shell interior minus
clearance, or pins landing on receiving bores with the declared
interference. Misordered joint chains, missing datums, and unposed parts
are critical failures at this stage. Interface mating rules
(complementary genders, matching fit within the type's clearance band,
opposed normals) run here too.

**Assembly-level CAD probes (build only).** Each joint also subscribes to
named `cad_checks`, run after every part compiles: `assembly.no_interference`
(parts touch but never overlap), `assembly.screw_axes_clear` (every screw
axis is void through the assembled stack), `assembly.pins_engage`,
`assembly.hooks_engage`, `assembly.channel_continuous_across` (a routed
path is void through *every* part in the pose), and so on. In strict mode
a critical joint IR failure aborts before any CAD — a mismatched bolt
pattern never reaches the compiler. The assembled STEP is exported as a
compound, never a boolean fuse: placement is for the eyes, intersection
happens only inside probes. Each part's STL still exports in its own
print orientation.

Domain packs extend this vocabulary — their checks, ops, and joints enter
the same registries under the same fail-fast and honesty rules as core.
