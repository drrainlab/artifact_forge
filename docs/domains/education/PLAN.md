# Education / FabLab — domain plan (ED)

Expansion of the domain from [ECOSYSTEM.md](../../ECOSYSTEM.md) ("Future Domains
to Watch → Education / FabLab"). Template canon — [INDEX.md](../INDEX.md).

## 1. Scope and positioning

Teaching kits for classrooms, FabLabs, and clubs: objects on which
engineering concepts are felt WITH THE HANDS — fits and clearances, bridges
and overhangs, truss statics, bearings, trigonometry. The key idea: **the
ENGINE itself is the teaching material**. AF's honesty validators are the
subject of the lesson: the student prints an object, the validator predicts
the behavior, the print confirms or refutes it — and the discrepancy is a
lesson too. No STL platform provides the pair "prediction → measurement".

**Which claims the domain does NOT make:**

- NOT toy-safety certification: we do not claim EN71; "classroom-safe" =
  caveats about sharp edges and small parts in the report, not a certificate;
- NOT laboratory metrology equipment (the gauges are educational);
- NOT a promise of educational outcomes — only measurable properties
  of the objects themselves.

## 2. Mode / Environment / Tier

The domain = pack, NOT a new mode: a classroom has no validator
contract of its own — lessons live in the existing modes.

```text
mode:        Utility / Engineering / Cinema (cutaway and demo models)
environment: household / desk
tier:        Free / Edu — fills the existing Education/FabLab
             license from ECOSYSTEM with product content
```

## 3. What the engine already has — the reuse map

| Building block | Status | Reuse as a lesson |
|---|---|---|
| `manufacturing.overhang` / `min_wall` / `supportless` / `bed_fit` | ✅ | demonstrations of FDM constraints: print a series, compare against the validator's verdict |
| Clearance-band interface mechanics (A1 mate validation) | ✅ | the "fits" lesson: the band is the very concept the tolerance ladder lets you feel |
| `truss_beam_v1`, `truss_web_cutouts` | ✅ | statics: a truss versus a solid beam at the same weight |
| `bearing_turntable_base_v1` (608 seat) | ✅ | the "bearing" lesson: press-fit seat for a real 608 |
| `phone_stand_v1` (device_slot = f(tilt)) | ✅ | trigonometry: the slot is derived from the angle — the formula is visible in the YAML |
| `grab_handle_v1` (sweep), `shelf_bracket_v1` (loft) | ✅ | CAD operations made tangible: sweep/loft as objects |
| `pin_pair`, `snap_hook_pair`, `dovetail_adapter_body`, `tongue_groove_edges` | ✅ | tolerance ladder steps and the "joint zoo" |
| `adapter_plate_v1` + `standoff_pattern` + `aluminum_profile_ref_v1` (2020) | ✅ | classroom robotics chassis ED-3 |
| `frame_report` (explode/sections) | ✅ | "cutaway" models: sections are generated, not drawn |
| Hinge | ✅ | shipped: `hinge_leaf` + `living_hinge_groove` — the "hinge" lesson is unblocked |
| Threads (R5) | ⬜ | the "thread" lesson — after the corresponding wave |
| Text embossing op | ⬜ | ladder step labels right on the part; until then — a table in the report |

## 4. Waves ED-1..3

### ED-1 — Fit & Print Physics ⬜

Golden artifact: **`tolerance_ladder_v1`** — a ladder of fits: pin/socket
pairs (reuse of `pin_pair` + clearance-band mechanics) with clearance steps
of 0.05–0.6 mm; you print it — you feel the clearance band with your hands:
where it's press-fit, where it slides, where it rattles. **The validator
measures every step** (`form.ladder_steps_ok`: step monotonicity, nominal of
each pair), the report is printed next to the ladder as a "prediction sheet".
Alongside in the wave: bridge/overhang test objects — an echo of
`manufacturing.overhang`: the object deliberately crosses the verdict
boundary, the student sees where the validator said WARN and where the print
actually sagged.

Criterion: the golden builds, each step has a measured nominal in the
report; a test checks the ladder step against the declaration (desync is
unrepresentable); print confirmation per Certified criteria.

### ED-2 — Mechanisms ⬜

The "bearing" lesson on `bearing_turntable_base_v1` (608 — the world's
cheapest bearing) + the "tilt" lesson on phone_stand (slot = f(tilt), change
the angle — watch the recomputation and the COM gate). The hinge lesson —
**now that the hinge ops have shipped (`hinge_leaf`)**; previously the wave was
honestly without a hinge rather than with a drawn one.

### ED-3 — Kits & Chassis ⬜

Parametric lesson kits (teacher guide + YAML: one parameter — one concept);
classroom robotics chassis (`adapter_plate_v1` + `standoff_pattern` +
2020 profile as the frame — reuse of `process: reference` from VF); "cutaway"
models — **reuse of sections from `frame_report`**: a cross-section of the
product as a teaching poster, generated from the same YAML.

## 5. Domain interfaces and standards

**Lesson Kit Standard** (modeled on the Cassette Interface Standard):

- shared parameters: `step_count`, `clearance_start/step` (ladder),
  `label_scheme`; for the chassis — `deck_w/l`, `standoff_grid`;
- frame keys: `probe_axis` (pair insertion axis), `deck_top_n` (chassis);
- typed ports: the chassis declares `screw_pattern` (sensor modules) and
  `cable_pass` — school modules are compatible via `forge compat`, and
  the compatibility matrix itself is a teaching exhibit.

## 6. Candidate validators

| Validator | Basis | Status |
|---|---|---|
| `form.ladder_steps_ok` | clearance-band + pair nominals | ⬜ (assembled from existing parts) |
| `form.bridge_test_declared` | linking the test object to the `manufacturing.overhang` threshold | ⬜ |
| `manufacturing.*` (all) | exist | ✅ reuse as the SUBJECT of the lesson |
| `form.stability_footprint` | exists | ✅ (stands, chassis) |
| `assembly.no_orphan_ports` | exists | ✅ (chassis with modules) |

The domain's peculiarity: validators don't only gate — their verdicts become
part of the teaching material (the prediction sheet for the print).

## 7. Free / Pro boundary (the Printables test)

| Free / Edu | Paid (Edu license / Pro) |
|---|---|
| tolerance_ladder, bridge/overhang tests, single lesson objects | **lesson kit workflow**: a YAML series + teacher guide + prediction sheets + classroom batch (30 ladders with names) |
| chassis in the base configuration | chassis families for classroom sensor kits, a school's private catalog (PK B2B mechanics) |

Test cubes and ladders exist on Printables — they are Free by rule.
What's paid is the classroom infrastructure: workflow, batch, guides, reports.

## 8. Risks and claims

1. Children: only "classroom-safe" caveats (edges, part size
   ≥ threshold, report warnings without suppression) — NOT EN71, NOT "child-safe"
   (ECOSYSTEM: child-visible, but NOT child-safe unless tested).
2. Divergence between the prediction and the print on someone else's printer
   is not a domain bug but lesson material; yet the thresholds must honestly
   state the material and orientation they were calibrated on.
3. Do not promise pedagogical outcomes — AF ships measurable
   objects, not pedagogy.
4. The robotics chassis is not a "robot": electronics/motors are out of scope,
   the chassis claims only mounting and dimensions.

## 9. Connections

- **Role in the ecosystem**: a funnel into community packs (CP) — "a person
  with a YAML → pack author" starts with a lesson; a demo for OS-6 "good first
  packs"; content for the Education/FabLab license (ECOSYSTEM Studio
  licenses).
- **A1/A1.5 ✅** — the clearance band and the compat matrix = teaching
  exhibits; chassis ports. **A2 BOM ⬜** — classroom kit provisioning (screws,
  608, profile) — the BOM as a handout sheet.
- **E-stage** — hinge/thread ops have shipped and unlock ED-2+ lessons as they
  land (the domain consumes, it does not force).
- **PK/CP lines** — the Edu tier road-tests PK-2's free mechanics; classrooms
  are a natural source of CP packs.
- Neighboring domains: studio (a stand as a lesson), jigs (gauges mature into
  B2B), repair (the "fix the handle" lesson — a bridge between domains).

This domain's shared capability gaps (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the
domain is their CLIENT, not their owner.
