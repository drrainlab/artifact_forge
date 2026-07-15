# Manufacturing Aids / Jigs / Fixtures — domain plan

Statuses: ✅ implemented · 🔶 partial · ⬜ not started. Template canon —
[INDEX.md](../INDEX.md); commercial rules — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope and positioning

Small-batch production tooling: drilling jigs, stops,
assembly and soldering fixtures, tolerance-ladder gauges, go/no-go templates,
alignment blocks. Context: AM as a production resource — companies care about
repeatability, reports, labels, BOM, material and version; exactly what AF
does with validators. The strongest B2B direction: every workshop needs
tooling, each one is slightly different, parametrization pays off instantly.

What claims this domain does NOT make:

- A jig is tooling, NOT a precision-class measuring instrument: without
  on-site calibration there is no "guaranteed accuracy ±0.05".
- Does NOT promise service life under impact/milling loads — positioning
  and guidance, not absorbing cutting forces.
- Go/no-go gauges are shop-floor probes, not certified measuring
  instruments.

## 2. Mode / Environment / Tier

Domain = pack, NOT a new mode: the quality contract is assembled from
Engineering (tolerances, min_wall, frames) and Workshop (loads, fasteners).

```text
mode:        Engineering / Workshop
environment: workshop / desk
tier:        Business / Pro-centric (Free — single showcase stops)
```

## 3. What the engine already has — reuse map

| Domain block | How it is built today | Status |
|---|---|---|
| Base tooling plates | `adapter_plate_v1`, `fastener_plate_v1`, `rounded_plate` | ✅ |
| Holes/countersinks for workpiece fastening | hole/counterbore/countersunk patterns | ✅ |
| Nuts/inserts in the jig body | `nut_trap`, `heatset_insert_pocket` | ✅ |
| Jig guide bushings | `bearing_seat` (fit for a steel bushing/bearing 608/625) | ✅ |
| Positioning stops, swappable jaws | dovetail: `dovetail_adapter_body`, `dovetail_joint`, `dovetail_rail` port | ✅ |
| Registration of two fixture halves | `pin_pair`, `butt_pin` joint (split+registration), `press_fit_pin_pair` | ✅ |
| Lightening large tooling | `truss_web_cutouts`, `truss_beam_v1` | ✅ |
| Fastening interfaces | `screw_pattern`/`heatset_insert_pattern` ports + `dovetail_rail` (A1/A1.5) | ✅ |
| Completeness/report | BOM (`assembly/bom.py`), frame_report, swap harness (swappable jaws!) | ✅ |
| Marking (jig version/number) | text/label embossing op | ⬜ |
| Imperial parametrization UX | units-resolve exists; imperial presets | 🔶 (YAML convention, not engine) |
| DIN/euro pallet grid for tooling | unified system pitch | ⬜ (relative of A4 Wall System) |

## 4. Waves JF-1..3

### JF-1 — Positioning Core ⬜

Golden artifacts (both mandatory):

- **`drilling_jig_v1`** — a drilling jig: a plate (`rounded_plate` +
  hole pattern) with fits for steel guide bushings
  (`bearing_seat` press-fit band) and a side fence-ruler; workpiece
  fastening with a clamp (the plate provides a clamp edge).
- **`stop_block_v1`** — a parametric stop (imperial and metric
  presets from one YAML) with dovetail fixation on a rail
  (`dovetail_adapter_body` + `dovetail_joint`): repeatable cut/drill
  length.

Criterion: both goldens at grade A; bushing fit and dovetail fixation
covered by measuring validators (§6); the swap test "stop repositioned —
rail untouched" via the existing swap harness.

### JF-2 — Assembly / Soldering Fixtures + Gauge Family ⬜

- Assembly/soldering fixtures: plate + `standoff_pattern` for PCB/part
  + `pin_pair` registration of two halves + `nut_trap` for clamps;
  soldering-iron access windows — `rounded_rect_cutout`.
- **Gauge family**: tolerance ladders (stepped gap feelers),
  go/no-go probes for holes/shafts — parametric families
  (A4 extends/preset mechanism). A relative of the repair domain's
  fit-templates (RP-2) — shared ladder validator.
- Criterion: golden soldering_fixture + gauge_ladder; step monotonicity and
  pitch — via a validator, not a declaration.

### JF-3 — Versioning, Labels, B2B Report Bundle ⬜

- Jig marking: number, version, date — requires the **text embossing op
  ⬜** (the domain's main gap); until then — parametric notch marks.
- **B2B report bundle**: BOM (bushings, screws, inserts — derived from
  joints/ops, not a declaration) + material + version + print notes as one
  package — a direct client of A2 Build Package ⬜.
- Criterion: `drilling_jig_v1` emits the package; a test cross-checks the BOM
  fasteners against joints (desync is unrepresentable — A2 canon).

## 5. Domain interfaces and standards

**Fixture Interface Standard** (modeled on the Cassette Interface Standard):

1. **Shared parameters** (name contract): `datum_edge_offset`,
   `bushing_od`, `bushing_press_band` (0.05–0.15), `stop_travel`,
   `grid_pitch` (tooling mounting grid pitch), `jig_version`.
2. **Frame keys**: `datum_face_z`, `bushing_axis_*`, `stop_face_x`,
   `rail_u0/u1` — registration surfaces are published by the builder and
   measured in pose.
3. **Typed ports**: stop fixation — the existing `dovetail_rail`
   (male/female, slide axis in the frame); plate fastening — `screw_pattern`;
   registration of halves — the `butt_pin` joint. JF-1 introduces no new types
   — the entire A1 vocabulary already covers the domain.

## 6. Validator candidates

| Validator | What it measures |
|---|---|
| `form.bushing_fit_ok` | press-fit band of the bushing fit, depth ≥ k·bushing_od, surrounding wall ≥ min_wall |
| `form.registration_surfaces_ok` | datum faces coplanar/orthogonal within tolerance, pin registration without play beyond band |
| `form.gauge_tolerance_ok` | gauge steps monotonic, pitch constant, step edges no thinner than the nozzle |
| `form.stop_repeatability_ok` | dovetail stop: full engagement, play along the working axis within band |
| `manufacturing.jig_orientation_declared` | working surfaces not across layers; orientation in the report |
| `assembly.fixture_bom_complete` | every purchased item (bushing/screw/insert) derived from a joint/op (A2 client) |

## 7. Free / Pro boundary (Printables test)

| Free / Certified Free | Business / Pro |
|---|---|
| single stop_block, simple jig for one diameter | tooling families (grids, diameter series, imperial/metric) |
| one gauge probe | gauge families + tolerance fit-workflow |
| — | B2B bundle: BOM + material + version + print notes; private packs |

The B2B value is repeatability, reports and versioning, not the stop's STL
itself.

## 8. Risks and claims

- **Accuracy**: a plastic jig guides the drill but does not replace machine
  tooling; every report carries a "verify first article" note.
- **Wear**: the guiding function belongs to the steel bushing; drilling
  directly into plastic — WARN, not a supported mode.
- **Thermals**: soldering fixtures — a material note (PETG minimum, ASA
  better); PLA near the tip — a FAIL candidate after the environment carrier ⬜.
- **Gauges**: material shrinkage shifts the steps — go/no-go is honest
  only after print calibration (report note, shared RP/JF).

## 9. Connections

- **A1/A1.5 ✅**: dovetail ports — the mechanism for swappable jaws/stops;
  the swap harness is ready-made proof of tooling repositioning.
- **A2 BOM ⬜**: the JF-3 report bundle is one of the first Build
  Package clients (alongside esp32_box from the A2 criterion).
- **A4 Wall System ⬜**: the system's unified pitch/rail is a relative of
  grid_pitch; gauge/appliance families wait for extends/preset.
- **E stage**: E2 load paths will strengthen clamp claims; threads ✅ shipped — screw
  clamps for jigs.
- **Domains**: repair (shared ladder validator RP-2/JF-2), electronics
  (soldering fixtures for their same boards — shared standoff patterns).

The shared capability gaps of this domain (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the domain
is their CLIENT, not their owner.
