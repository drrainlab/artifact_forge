# Repair / Spare Parts / Right-to-Repair — domain plan

Statuses: ✅ implemented · 🔶 partial · ⬜ not started. Template canon —
[INDEX.md](../INDEX.md); commercial rules — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope and positioning

Printable replacements for worn/broken parts of household appliances and
housewares: knobs, feet, bushings, washers, hose adapters, latches,
lids, guides. Context: EU right-to-repair enshrines the right to
demand repair; the Philips Fixables precedent (replacement parts via
Printables with emphasis on material, print orientation, and safety) is the
model AF reproduces parametrically: not "an STL of a similar knob", but a
generic spare derived from measurements of the assembly and verified by
validators.

Which claims the domain does NOT make:

- Does NOT promise OEM equivalence of strength/service life — a replacement
  from measurements, not a certified spare part.
- Does NOT claim food contact (kitchen appliance parts — a separate
  caveat about material/coating, outside the domain's guarantees).
- Does NOT cover parts under pressure, heat above the material's limit, or
  carrying a safety function (brakes, child-seat locks, etc.).

## 2. Mode / Environment / Tier

The domain = pack, NOT a new mode (the rule of five axes: no unique
validator contract — the existing ones suffice).

```text
mode:        Engineering / Utility / Workshop (per product)
environment: household / appliance / high-heat / wet
tier:        Free + Certified + B2B/OEM
```

## 3. What the engine already has — the reuse map

| Domain block | What builds it today | Status |
|---|---|---|
| Mushroom knobs, feet, bushings, washers | `revolve_band`, `recipe_revolve` | ✅ |
| Plates/covers/small lids | `rounded_plate`, `rounded_rect_cutout`, hole/counterbore/countersunk patterns | ✅ |
| Bosses, screw standoffs | `boss_pattern`, `standoff_pattern`, `nut_trap`, `heatset_insert_pocket` | ✅ |
| Enclosure latches | `snap_hook_pair`, `snap_window_pair` (snap strain physics) | ✅ |
| Enclosure fragments | enclosure ops (`rounded_box_shell` + base `enclosure_base_v1`/`_snap_v1`) | ✅ |
| Fastener tables | fasteners M2–M5, heatset, nuts (`core/fasteners.py`) | ✅ |
| Fastening interfaces | ports `screw_pattern`, `heatset_insert_pattern` (A1/A1.5, frame + mate) | ✅ |
| Clamp/pipe replacements | `clamp_half_lower/upper`, `pipe_clip_v1_sideprint`, `axial_channel` | ✅ |
| Threaded replacements (jar lids, glands) | threads | ✅ shipped (`threaded_plug_body`, `thread_internal_clearance`) |
| Part marking (part number/version) | text/label embossing op | ⬜ |
| Hinges (appliance lids) | hinge_leaf / living_hinge_groove | ✅ shipped |
| Environment profile on the instance (high-heat gate) | environment carrier | ⬜ (PK line) |

## 4. Waves RP-1..3

### RP-1 — Measurement-Driven Generic Spares ⬜

The domain's core: the part is derived from caliper measurements, not from a
photo. Golden artifacts (both are mandatory to close the wave):

- **`hose_adapter_v1`** — a parametric two-step cone
  Ø-in/Ø-out with hose-barb ribs (`recipe_revolve` + `revolve_band`
  for the ribs): drain hoses, vacuum cleaners, garden irrigation.
- **`replacement_knob_v1`** — a knob with a D-shaft/square seat
  (`recipe_revolve` body + shaft profile recess): stoves, washing
  machines, timers.

Plus cheap side-goldens on existing ops: appliance_foot (a foot with a
threaded/smooth bushing — press-fit until threads exist), washer/spacer.
Criterion: both goldens at grade A, every fit parameter covered by a
measuring validator (see §6), S/M variants from a single YAML.

### RP-2 — Fit Templates + Appliance Families ⬜

- **Fit templates**: printable try-on "ladders" for measuring the assembly —
  stepped probes of shaft/hole/slot diameters (0.2 mm steps); the
  user tries them on, enters the step number, and gets a part with a
  guaranteed fit. Built on `recipe_revolve` +
  hole patterns; this is a workflow, not a product — the heart of Pro.
- **Appliance families**: family/extends/preset (the A4 mechanism) —
  "refrigerator feet", "oven knobs" as parametric series
  with maturity on presets.
- Criterion: a golden fit_ladder + one family with ≥3 presets; the test
  "ladder step N → the part seats within the band" is pinned by a validator.

### RP-3 — OEM / B2B profiles ⬜

Branded replacement catalogs on the Fixables model: a private pack
(the PK-1/PK-3 mechanism) with material/orientation/notes from the vendor,
print confirmation as the condition for Certified. Dependencies: PK-1 ⬜,
text embossing ⬜ (part number on the part), A2 BOM ⬜ (kit completeness).

## 5. Domain interfaces and standards

**Spare Fit Standard** (modeled on the Cassette Interface Standard):

1. **Shared parameters** (the names are the contract): `shaft_d`, `shaft_flat_h`
   (D-shaft) / `shaft_sq` (square), `fit_clearance` (band 0.1–0.4),
   `hose_d_in`, `hose_d_out`, `barb_count`, `grip_d`, `grip_h`.
2. **Frame keys**: `shaft_axis_z`, `bore_floor_z`, `barb_od_k`,
   `grip_top_z` — published by the builder, measured by validators.
3. **Typed ports**: the shaft seat is the existing type
   `cylindrical_payload_socket` (female, axis = shaft axis); fastening
   of covers — `screw_pattern`/`heatset_insert_pattern`. The new type
   `shaft_socket` (D/square profile) is a candidate for the A1 registry,
   introduced only together with its own mate validator ⬜.

## 6. Candidate validators

| Validator | What it measures |
|---|---|
| `form.shaft_fit_ok` | D-shaft/square clearance within the band (diameter + flat/face), seat depth ≥ k·shaft_d |
| `form.knob_torque_wall_ok` | the wall around the shaft holds hand torque (thickness from shaft_d, a min_wall generalization) |
| `form.barb_retention_ok` | barb rib height/pitch vs hose_d (retention), rib slope angle printable |
| `form.fit_template_ladder_ok` | ladder steps are monotonic, the pitch is constant, the step marking is readable (by geometry for now — notches; text ⬜) |
| `manufacturing.spare_orientation_declared` | print_orientation is set and consistent with the seat load (layers NOT across the shaft) |

## 7. Free / Pro boundary (the Printables test)

| Free / Certified Free | Pro / B2B |
|---|---|
| single feet, washers, knobs, hose adapters from entered Ø | appliance families (preset series with maturity) |
| one fit-ladder probe | the whole fit workflow (ladder → step number → part in band) |
| — | OEM/branded catalogs, print notes, reports, B2B profiles |

A single knob is easy to find on Printables — it's Free by test; AF's value
is the parametric fit and the workflow, and those are paid.

## 8. Risks and claims

- **Strength**: a printed part ≠ molded OEM; every report carries a note
  on material/orientation; load-bearing/heated assemblies are out of scope.
- **High-heat**: until the environment carrier ⬜ appears, high-heat parts
  (oven knobs) ship with a material WARN note (PETG/ASA), not a gate.
- **Food contact**: an explicit "not food-safe by default" caveat in
  all reports for kitchen parts.
- **OEM legal**: RP-3 only by agreement with the vendor; reverse-engineering
  other brands' parts into a public catalog is not included.
- **The photo-reverse temptation**: the domain is measurement-driven by
  principle; "generate from a photo" = a hallucination without measurements.

## 9. Connections

- **A1/A1.5 ✅**: fits as typed ports (`cylindrical_payload_socket`,
  screw/heatset); `shaft_socket` is a registry candidate.
- **A2 BOM ⬜**: the "part + screws + inserts" kit for RP-3.
- **A4 families ⬜**: appliance families in RP-2 wait on the
  extends/preset mechanism.
- **E-stage**: threads ✅ and hinge ✅ have shipped (lids/glands/appliance lids unblocked) —
  they expand the RP catalog, they do not block RP-1.
- **PK line ⬜**: RP-3 requires the pack mechanism and the commercial layer.
- **Neighboring domains**: jigs (fit ladders = kin of the JF-2 gauge family),
  electronics (enclosure latches/lids — shared ops).

This domain's shared capability gaps (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the
domain is their CLIENT, not their owner.
