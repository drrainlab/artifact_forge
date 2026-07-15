# Artifact Forge — master plan: an engineering grammar of assembly

Positioning: **Artifact Forge is a platform for parametric creation of
functional artifacts**: engineering parts, mounts, fixtures, film props,
wearable structures and biomorphic objects. Not an "AI CAD generator" but a
parametric artifact atelier: one core, several modes
(see "Modes on top of one core").

Goal: AF is not a catalog of individual products but **a system for
assembling structures out of verified functional "organs"**. Archetypes and
modifiers are only the vocabulary. Product complexity is born not from part
count but from the system's ability to understand how parts connect, what
forces pass through them, how to print, assemble and maintain the result,
and how it will fail.

```text
Catalog
+ Interfaces (ports/mates)
+ Assembly Graph
+ Constraint Solver
+ Physics-lite
+ Manufacturing Planner
+ Failure Critic
+ Workshop Memory
+ Modes (Engineering | Workshop | Cinema | Fashion | Creature)
= a generator of functional artifacts
```

Development principle: **fewer archetypes — more interfaces, solvers and
validators**. Every wave obeys the honesty canon: a feature without
validator-backed geometry = a hallucination; a wave is closed only when
there is a golden example + tests + measurable checks.

This document is the main roadmap. [BUILDERS.md](BUILDERS.md) remains the
canon of the builder layer, [BIOMORPHIC.md](BIOMORPHIC.md) the canon of the
bio track; their "honest remainders" are absorbed into the waves below
(see "Absorbed tracks").
The commercial, licensing and pack model (open-core, the five axes
Modes/Packs/Environments/Styles/Tiers, Free/Certified/Pro, the PK line) is
the canon of [ECOSYSTEM.md](ECOSYSTEM.md).

---

## Modes on top of one core

Four audiences — engineers, makers, filmmakers, fashion designers — are NOT
four platforms. There is one core (archetypes + modifiers + ports/assembly +
materials/manufacturing + validation + export); **a mode = a profile of
priorities** on top of it: default requirements (wave A3), production
package composition (wave A2), the set of gate validators and style presets.
A mode has no right to weaken honesty — it changes WHAT matters, not WHAT
gets checked.

| Mode | Main priorities | Mode-specific entities (mode vocabulary) |
|---|---|---|
| Engineering | strength, fasteners, tolerances, loads, BOM, STEP | — (today's default) |
| Workshop | systematic mounting, compatibility, plastic economy | rail/dovetail interfaces, a shared pitch (wave A4) |
| Cinema / Props | silhouette, style, print speed, disassembly, painting, weight | hero/stunt/background_prop, paintable_surface, LED_channel, rigging_point, hidden_mount, quick_repair_joint |
| Fashion / Wearable | body, movement, comfort, weight, edge safety, size grid | body_anchor, strap_slot, fabric_stitch_hole, skin_clearance, flex_zone, quick_release, size_grading |
| Biomorphic / Creature | grown-looking form, organics on top of an honest core | the BIOMORPHIC.md canon + implicit skin Bio-4M — the bridge between all modes |

An architectural consequence **right now** (so schemas don't have to be
broken for cinema/fashion later): the core language is neutral —
"artifact", not "mechanical_part"; new region roles (body_contact_region,
fabric_interface, paint_surface) are added strictly by the law "a role
arrives with its consumer" (BIOMORPHIC.md) — the enum is not inflated ahead
of time, but engineering semantics is also not baked in where a neutral one
suffices.

---

## Where we are now (status as of 2026-07-05)

✅ = implemented · 🔶 = partial / in another layer · ⬜ = not started

| Concept layer | Status | Where it is today |
|---|---|---|
| Useful single-part products (AF v1) | ✅ | 26 archetypes, 14 modifiers, recipe kernel R1, honesty pipeline, 487 tests; the catalog has since grown to 59 recipe archetypes across 11 domains (expansion wave R2 complete) |
| Assembly Graph | 🔶 | `assembly/v1`: typed assemblies, root+joints, quarter-turn poses, fit probes in pose, wiring check (`product/assembly.py`, `assembly/joints.py`, `assembly/pipeline.py`). A flat joints list, not a hierarchical graph |
| Ports / Interfaces / Mates | ✅ | A1+A1.5: registry of 11 types, InterfaceSpec with frame (normal/up/axis), mate+frames validation, fluid_joint, `forge compat` v2, swap harness, legacy retrofitted |
| Functional Grammar (verbs) | 🔶 | `forge edit` intents — a seed; prompt→assembly composition is shipped (the LLM composes multi-part assemblies from the catalog, Assemble screen in the cockpit); a functional plan (clamp_around → support_payload → route_cable) does not exist yet |
| Constraint / Param Solver | ⬜ | `product/resolve.py` — a linear single-pass resolve (units/expr/clamp); no inverse problems or trade-offs |
| Load Path Analyzer | 🔶 | pointwise: snap strain 1.5·δ·t/L², `form.stability_footprint` (COM), min_web; `load_paths:` on bio archetypes (Dijkstra over the rib graph). No moment → fastener → wall → margin chains |
| Hardware / Fastener Ontology | 🔶 | `core/fasteners.py` (M2–M5, heatset, nuts, E27/GU10), PORT_SIZES, bearings 608/625/6001 — scattered tables without a unified schema |
| Assembly Planner / BOM | ⬜ | `assembly_report.yaml` exists (poses/joints/grade), but BOM, assembly steps and build package are not generated |
| Manufacturing Planner | 🔶 | bed_fit, min_wall, overhang (aware of `print_orientation`), max_opening_span, sideprint "zero overhangs by construction". No split strategy or material profiles |
| Failure Mode Critic | ⬜ | the findings machinery is ready; failure critique as a layer does not exist |
| Design Memory / Workshop Feedback | ⬜ | a repair ledger exists; `build_observation` from the workshop does not exist |
| Product System Templates | ⬜ | the bracket+cup pair mates via datums — a precedent, not a system |
| Design Intent / Requirements Model | 🔶 | `requested_features` + capability report (built ⊆ supported) — a flat feature list, not structured requirements |
| Region Editor + Visual Grounding | 🔶 | Cockpit: Region lens, patch preview; NL edit on a selected region not locked in |
| Compatibility Matrix | ✅ | `forge compat` — derived from port declarations; no hand-written matrix exists |
| Multi-Resolution Design (L0–L5) | 🔶 | prompt→assembly intent (Assemble screen) now provides a prompt-level entry; otherwise entry is directly at the product YAML level (L2) |
| Modes on top of the core | 🔶 | mode scaffold P2: `mode:` + MODE_PROFILES (product/modes.py), wearable requires body_fit; priorities/packages lie ahead |
| Body / Human Fit Layer | 🔶 | P2 core: body_fit (forearm) + forearm_cuff_v1 grade A; wrist/thigh and size grading lie ahead |
| Soft–hard interfaces | 🔶 | zip-tie slots, TPU recesses, magnet pockets + **add_strap_slots** (15–40 mm straps, P2); no sew/velcro/elastic/foam/LED |
| Style Grammar | 🔶 | biomorphic_utility_part + BIOMECHANICAL_EXOSKELETON + **Bio-4M implicit SDF skin** (STL-first, export honesty); one style genus, not a grammar of styles |
| Production Package per mode | ⬜ | basic package — wave A2; cinema/fashion variants — wave P4 |

Bottom line: **AF v1 is closed; assembly/v1 is already half of AF v2.**
Ahead are three macro-stages: A waves (composable system), E waves
(engineering reasoner), M waves (self-extending platform) — plus the
parallel lines Bio (BIOMORPHIC.md), P (Props & Wearables, below) and VF
(Vertical Farm, docs/VERTICAL_FARM_PACK.md).

### VF line — Vertical Farm Pack (status as of 2026-07-07)

**VF-1 (MVP-1 + MVP-1.5 + MVP-2) ✅**: transient water contract
(`ChannelCutFeature` — the kernel's first non-axial cut), water_rail_v1 /
coco_cassette_v1 / substrate_retainer_frame_v1, Cassette Interface Standard
(shared parameters + frame keys + joint `removable_insert`), joints
`removable_insert`/`tongue_groove`, water_report.yaml + views metadata,
golden examples water_rail_cell_2020_petg (3 parts) and two_cell_line_petg.
The assembly pipeline learned to compose joint chains through a
non-rotated parent (rail → cassette → frame).

**VF-3 Fluid Row ✅ (2026-07-07)**: the first real assembly-system
proof — a 3-cell fluid cascade row (`vertical_farm_row_3x1_petg`):
inlet cap (drip tower) → 3 rail cells with cassettes → collector endcap
(catch tray), all handovers are real `fluid_joint`s (first client;
downhill by datum-construction, verified), adapters on `saddle_hang`
(auxiliary verification joint), required fluid ports with no orphans,
row-level water_report (cells/handovers/total_drop) and **BOM-lite**
(derived-only — a seed of A2: printed parts, silicone tube from hose_port,
aluminum profile; no HardwareSpec until A2). Along the way VF-3.0 hardened
the interface core: fluid datums = water handover points, axis = flow
direction, an ordering guard for joint chains, pose composition through a
non-rotated parent, the width rule "receiver ≥ giver", the `hose_port`
type, `AssemblyInstance.meta`.
⚠️ the row is a cascade (each cell ~7.9 mm lower), NOT the final rack.

**VF-4 Profile-Carried Row Reference ✅ (2026-07-08)**: the cascade is
mechanically anchored to a REAL aluminum carrier —
`vertical_farm_row_3x1_carried`: 2 standard straight 2020 profiles under
the global row slope (a reference surrogate with a beveled top — poses are
90° only; honesty note everywhere), `process: reference` (external hardware
without FDM checks — profiles, tubes, glass, pumps in the future), joint
`profile_perch` + row checks in global poses (row_supported /
pitch_aligned / slope_feeds_downhill), **the carrier slope is DERIVED from
the physics of the water** (derived row_slope_deg — "a frame fighting the
water" is unrepresentable), frame_report.yaml, the profile in the BOM as
cut-to-length. Slot ports are optional — old goldens untouched; the
mandatory support = the `row_carried_by_profile` feature in the carried
assembly's must_have. Contact along the upstream edge (span gap 7.91
reported honestly) — a verification proof, not the final support.

**VF-Correction: Tilted Flush Water Rail ✅ (2026-07-08)**: the cascade was
declared a design mistake and replaced by the **tilted_flush_row** canon —
`water_rail_v1` rewritten IN PLACE (v2): a CONSTANT-depth channel (the
slope lives entirely in the mount: `mount_context` 1.0–2.0°, check
`assembly.row_drains_under_mount` over virtual heights, chain order from
lap joints — a reversal is caught), flush modules (ΔZ=0, face_gap 0.3–0.6,
pitch = module_w + face_gap), **lap_flow_joint** (a lip continuing the
floor into a through, open-from-below opening; slot 0.5–2.5 = deliberate
non-hermeticity with a controlled leak path —
`form.lap_slot_leak_path_controlled`), sealed magnet pockets (alignment
only), **lightweight dry shell** in the op (−40% plastic, param-gated,
reversible; the generic modifier `lightweight_dry_shell_v1` — a future
wave), the profile reference became LITERALLY straight (slope 0, full
seating, span gap 0 — a check), the adapters re-mated (cap→`feed` — the
row's single drop; collector→`drain_edge` — the lip tip, hang_drop derived
without the cascade term). Cascade goldens deleted (history is in git); the
new ones: `vertical_farm_row_3x1` (magnets on) +
`vertical_farm_flush_smoke`. Reports: water (tilted_flush_row, virtual
drop, lap_seam_leak: controlled), frame (full seating, span_gap 0), BOM
("mount the WHOLE row at 1.5 deg", a magnets line).

**VF-4.1 Printability & Collector Hardening ✅ (2026-07-08)**: the
collector became the END receiver of the final lap lip (capture 6–8, cheeks
around the wet zone, a low apron rim 2.4–3.5 — not a wall: open top +
continuity with the tray = washability via the `receiver_open_top_cleanable`
check; in pose — captures/envelopes/removable_by_hand); lightening windows
→ a THROUGH skeleton (no bridges by construction, −45%;
`cassette_support_span_ok` — the cassette covers everything, worst span
≤45); `BoreFeature.roof=teardrop` (45° chords, the collector drain
supportless); always-on `supportless_lightweight_windows_ok` (a slab probe
on the solid — before this wave the bridges of flat ceilings were measured
by nobody) + `horizontal_bore_supportless`;
`manufacturing.print_orientation` in the instance contract; magnets
press-fit 0.1–0.3 off the dry butt ±Y face (the rule is a check) +
magnet_installation in frame_report.

**VF-4.2 Collector Robustness + Overflow Honesty ✅ (2026-07-08)**: the
collector went from "hanging pillars" to a rigid U-frame (two full side
walls ≥3.5 from the floor to the arm carry the cantilevered tray;
`collector_structure_sturdy` closes the min_wall blind spot) + the drain
became VERTICAL, downward (the tube enters from below and leaves under the
row; teardrop removed from the collector, the kernel primitive lives on for
future horizontal bores); an honest `overflow_containment` note in
water_report (the through skeleton lets top overflow through — until the
VF-5 root chamber).

**VF-5A Root Chamber ✅ (2026-07-09)**: the under-cassette volume is
param-gated `under_cassette: skeleton|root_chamber`. root_chamber = a blind
floor (overflow containment) + open root grooves (level const-depth,
drained by the forward mounting tilt like the main channel — WITHOUT slope
geometry; the key: a wide tray drains without a new X primitive, the row
tilt does everything); canon amendment `passive_root_drainage_return`
(no_secondary_water_channel exempts the root grooves); the full-width
collector catches the lip + grooves (collector_catches_root_drainage);
magnets into the perimeter (x84); overflow contained; 3 removability modes;
golden vertical_farm_row_3x1_root_chamber.
**VF-5B** (hex honeycomb with drainage slits) — separate: the grooves are
already functional; the honeycomb = root separation at the cost of slits.

**VF-6 Endcap magnetic docking ✅ (2026-07-09)**: the collector and inlet
cap dock magnetically onto the top of the end walls of the end modules
(param-gate `endcap_dock`/`dock_magnets`, op `endcap_dock_pockets`, check
`assembly.endcap_docks_to_rail` — an honesty closer: a magnet without a
counterpart pocket = FAIL).

**VF-7 Print-feedback pass ✅ (2026-07-09)**: fixes from inspecting the
print — a manifold cassette mesh (cell 6→8 mm + always-on `mesh_manifold`),
the collector drains dry (drain = the lowest point, slope 2.5°), dimensions
fit the P1S (module 248→205), the cap support-free (print orientation
`saddle_up`).

**VF-8 Drain screen basket + maintenance ✅ (2026-07-09)**: a removable
screen basket in the collector sump above the drain (`drain_screen_v1`, op
`screen_wall_slots`, joint `drop_in_screen`). Three fail-safe modes
(`normal_no_bypass` is mandatory; zero unfiltered bypass by default — a
clog is visible in the open tray; `emergency_unfiltered_bypass` only via
the `allow_emergency_bypass` opt-in + a report flag). Checks
`screen_open_area_ratio_ok` (≥4× the bore, ~436 mm²), `screen_debris_capacity_ok`
(≥3 ml), `assembly.screen_normal_no_bypass`. A machine-derived
`maintenance` block in water_report (honest_note "DEBRIS-REDUCED water").
Pump topology doc note (gravity→reservoir→pump, NOT direct suction).

**VF-8.1 Lowered Sump + Radial Funnel ✅ (2026-07-09)**: a new kernel
primitive `FunnelCutFeature` — the first floor sloped in both X AND Y (a
converging beveled frustum, `cut_funnel` as a ruled loft). The collector =
a funnel-well, the drain at the absolute lowest point, a drop-in bucket in
the well ("water falls INTO the basket, not across the tray"); +6 checks
(sump_is_lowest / slopes_to_sump / not_barrier /
no_standing_before / drain_inside_footprint / removable).

**VF-8 Capped Inlet (2026-07-09, superseded by VF-9)**: the first step of
the fix — a special `inlet_mode: capped` for `rail_1` with a solid floor. A
crutch: it did not remove the through holes under water at the rail↔rail
seams and made `rail_1` special.

**VF-9 Universal Rail ✅ (2026-07-09)**: an inversion — the rail is
universal again; the through receiver replaced by a **floored lip-seat**
(the pocket lowered by `lip_t+clr`, a solid floor). The neighbor's lip
seats in, `lip top = channel floor` (no dam, no hole downward); the same
pocket catches the cap's drip → `rail_1` is no longer special, `inlet_mode`
removed. The invariant **`manufacturing.no_through_holes_in_wet_lap_zone`**
(no open-from-below cutboxes under the wet path, except the collector
drain) + form checks
`lap_receiver_has_floor` / `lap_receiver_residual_volume_ok` /
`rail_universal_inlet_accepts_cap_and_lap` + assembly
`lap_joint_no_external_downward_leak` / `cap_drip_lands_in_channel_safe_floor`.
**VF-9 Part B Support-free L-hook cap ✅ (2026-07-10)**: the cap prints
AS-MODELED without the `saddle_up` flip. Discovery: a two-sided straddle
across a ~13 mm wall does not print support-free (the shoulder's inner lip
hangs) → a **compact one-sided L-hook**: a short shelf (~3.5 mm overhang)
on the outer edge of the wall top + an outer leg/foot down to the bed + a
nose column above the channel (straight drain, a roof anchor). The
protruding plate removed. **The magnetic dock moved to the vertical +Y
face** (VF-6 amendment `endcap_dock_style: top|face`) — a dock on the wall
top required an un-printable overhang. `saddle_hang_ir` gains a hook branch
(the collector straddle untouched). The new
`manufacturing.cap_supportless_verified` closes the VF-7c blind spot (a
flat cantilever → FAIL). CAD acceptance: smoke+root_chamber strict PASS.

**VF-9.2 Chute-cap ✅ (2026-07-10)**: the cap's through Ø9.4 bore read as a
"tunnel" and had no stop for the tube → **variant B (approved)**: a socket
with a stop shoulder (a blind floor) → orifice Ø5 → a short chamber (≤10
mm) → an **open-top spout chute** (a U-trough of ribs), the drip 4.5 mm
inside the channel (DRIP_INSET, a paired shift of the feed/spout datums —
the row pose does not change). The user's rule = the validator
**`form.cap_water_path_visible`** (a closed horizontal water tunnel =
FAIL). `hose_bore_ok` inverted (the socket MUST be blind),
`fluid_path_open` — a composite polyline probe,
`no_standing_water_ir` — an exemption "a blind bore drains through a
coaxial orifice", the new assembly `cap_chute_drains_under_mount` (chute
drainage in the POSE of the mounted row).

Ahead: **VF-4.3** anti-slide retention of the row on the tilt-mounted
profile (seating is full, there is no longitudinal lock);
**lightweight_dry_shell_v1** generic modifier; **VF-5 Cassette Family**
(sprout mesh / microgreen mat / rockwool cube / soil seedling / netpot
cassettes on the Cassette Interface Standard; mat cassettes will make
`form.substrate_retained_under_mount` a real check); **VF-6** production
readiness (PP food-grade, draft angles, no-undercut report);
`dry_endcap_v1`.

---

## AF v2 — Composable Workshop System (waves A1–A4)

Goal: products start mating with each other. The most important leap.

### A1 — Ports & Interfaces v1 ✅ core (implemented 2026-07-07)

Ports turn the catalog into LEGO Technic: a connection is a DECLARED,
typed, gendered entity, not a convention between YAML files.

Implemented:

1. **Type registry** (`product/interfaces.py`, exactly the A1 vocabulary):
   screw_pattern, heatset_insert_pattern, strap_slot_pair,
   cylindrical_payload_socket, dovetail_rail, snap_joint, tongue_groove,
   removable_insert, fluid_inlet, fluid_outlet, cable_pass. A type knows:
   the joints that implement it, each side's frame keys, the clearance
   band, the fastened flag. Types without a joint (fluid_*) are honestly
   "declared ahead".
2. **The common port contract** — `interfaces:` on an archetype: id, type,
   gender (male/female/neutral), a datum anchor, clearance, target region,
   protected keepouts, an accepts filter, assembly_role (required/optional).
   The loader binds fail-fast (regions/types/gender/band); the datum is
   runtime truth, measured by `interface.frame_exists` on the built form.
3. **Validators** (all 7 from the spec): interface.frame_exists,
   interface.mate_compatible, interface.clearance_ok,
   interface.fastener_access_ok, interface.keepouts_preserved,
   interface.swap_part_builds (the `assembly/swap.py` harness),
   assembly.no_orphan_ports. Mate resolution in `assembly/mates.py`;
   dimensional depth stays in the joint IR (no duplicated measurements).
4. **Port-id anchoring**: `a: cuff.payload_socket` — a joint targets the
   PORT, not a bare datum (legacy datums are legal; a half-declared
   connection is an honest WARN).
5. **`forge compat`** — a derived matrix (7 mates on the current catalog,
   including the self-mate of the rails line_east↔line_west); no
   hand-written matrix exists by design.
6. **`dovetail_joint`** (the R4 remainder closed): a sliding fit with
   undercut retention, a per-side clearance band, flank angle, full
   engagement, a datum chain in pose; axial retention is friction-only —
   stated in the report, not hidden.

**Driver proofs** (both golden + swap tests):

- *Wearable adapter swap*: `forearm_cuff_socket_v1` (a dovetail crown
  instead of the built-in snap-C) + `flashlight_adapter_25_v1` ↔
  `rail_plate_adapter_v1` — the cuff body does not change by a single byte
  (locked by a test); the assembly `wearables/cuff_flashlight_25.yaml`
  builds at grade A, the `swappable_payload_interface` feature is built.
- *Vertical farm cassette swap*: `sprout_cassette_v1` — the SECOND
  implementor of the Cassette Interface Standard: coco ↔ sprout on an
  untouched rail. Along the way the swap harness caught a real
  incompatibility (a 20 mm window in a 16 mm channel) — measured by a joint
  in pose, not declared.
- Standard drift is unrepresentable: `shared:` overwrites the crooked
  parameters of a swapped part (locked by a test).

A1 remainder (next iterations): the port frame with normal/up vectors
(currently datum only), an axial dovetail end-stop, fluid joints (VF-3),
retrofitting screw/heatset ports onto legacy archetypes (bracket+cup),
cable_pass instances, matrix integration into the Cockpit.

### A1.5 — Interface Hardening ✅ (implemented 2026-07-07)

The interface layer was brought from "works on golden scenarios" to a
load-bearing platform standard:

1. **Port frames**: `frame: {normal, up, axis?}` on every port — axial
   tokens (±X/±Y/±Z) in the spirit of the quarter-turn poses; origin = the
   datum. Orthonormality fail-fast at load time; ALL 20 ports of the
   builtin catalog carry frames (the deprecation window for builtin is
   closed by a test).
2. **Frame validators** (all 4 from the spec): `interface.frame_orthonormal`,
   `interface.normal_points_outward` (a ray-march over IR material: the
   contour minus cutboxes/bores/channels; male ports are allowed a
   protrusion within a 20 mm budget; flow-through ports (fluid/cable)
   legitimately look into the channel void; "no material behind" = WARN, an
   inverted normal = FAIL), `interface.up_consistent` (axial semantics per
   type: slide in the port plane, flow along the normal),
   `interface.mate_frames_opposed` (normals counter-directed IN POSE;
   orientation-sensitive types require up agreement and axis continuity —
   a flipped line module is caught at the frame level, not only via the
   channels).
3. **fluid_joint** + a cross-type mate (`COMPLEMENT_TYPES`:
   outlet(male) ↔ inlet(female)): a handover must flow DOWN (gravity is
   the pump) with compatible channel widths; the first real client — the
   VF-3 adapters; the physics is ready and tested.
4. **Legacy retrofit**: ports on lamp_bracket↔lamp_socket_cup
   (screw_pattern, frame keys mount_bc/mount_bc_n added to the builders)
   and the branch_clamp pair (heatset_insert_pattern); desk_lamp_e27 and
   branch_lamp_clamp_60 pass the mate/frames/fastener checks.
   Lesson: **auxiliary joints** — a compression_gap on top of heatset
   datums does NOT implement the port (it rides on it); the implementing
   joint must exist separately; no_orphan_ports counts only those.
5. **compat report v2**: frames in the port table, an
   incompatibility-reasons section, `stranded required ports` (a required
   port without a single candidate in the catalog = an orphaned standard).

Remainder: normal/up on wearable strap/cable ports when they appear,
per-type protrusion budgets instead of the blanket 20 mm, the fluid_d key
with VF-3.

### A2 — Hardware Ontology + Build Package (BOM) ⬜

From scattered tables to a single ontology of purchased components; from a
single STL to a kit.

1. **`catalog/data/hardware/*.yaml`** — typed HardwareSpec: screws, heatset
   inserts, wall anchors (incl. butterfly), bearings, E27/GU10 sockets,
   magnets, zip ties, TPU pads:

   ```yaml
   id: heat_insert_M4_standard
   hole_diameter: 5.6mm
   boss_min_outer_d: 9.5mm
   boss_min_height: 7mm
   clearance_required: true
   install_direction: Z
   ```

   `core/fasteners.py` becomes the loader of this ontology (the existing
   constants are the first records, the API is preserved).
2. **The BOM is derived**, not declared: screws from screw_joints, inserts
   from heatset ops, wall anchors from the hardware references of anchor
   holes.
3. **Build Package Generator**: `parts/*.stl` (each in its own orientation) +
   `bom.yaml`/`bom.md` + `assembly_steps` (order from the joints: inserts →
   pads → cable → close → bolts) + a risk report (the existing findings) +
   a material recommendation.

Criterion: `esp32_box_with_lid` and `desk_lamp_e27` produce a build
package; a test cross-checks fastener counts in the BOM against the joints
(drift is unrepresentable).

### A3 — Requirements Model ⬜

Do not lose the meaning of the request. A `requirements:` block in the
product YAML:

```yaml
requirements:
  functional:      [hold cylindrical handle Ø65mm, wall mounted, removable by hand]
  structural:      [support 2kg static load, two fasteners only]
  manufacturing:   [FDM printable, minimal supports, low plastic use]
  aesthetic:       [biomorphic, not boxy]
  safety:          [no sharp contact edges]
```

Each requirement maps onto features/validators/params; the capability
report is extended to a per-requirement verdict: **met / partial / not
met / impossible**. A direct evolution of `requested_features` and the
built ⊆ supported invariant — the same honesty, one level up.

Criterion: a golden instance with requirements gets per-requirement
verdicts; an unmeetable requirement yields an honest engine_gap, not a
silent pass.

### A4 — Product Systems v1: Workshop Wall System ⬜

Above the archetype level — a compatible ecosystem: rails, hooks, holders,
adapters with a shared mounting pitch and the shared rail/dovetail
interface from A1.

- A system specification: a common interface_profile, a shared mounting
  pitch, family/extends/preset (the Bio-4A mechanism from BIOMORPHIC.md),
  maturity on presets.
- `rail_slider` (the R5 remainder) is absorbed here — the system's rail is
  its first client.

Criterion: a rail + 2–3 removable holders; every pair confirmed by
`forge compat` and mate probes in pose; bio presets of the holders sit on
top of the same cores (the law "the Bio package does not own generic
mounting logic").

---

## AF v3 — Engineering Reasoner (waves E1–E4)

Goal: the system reasons about loads, risks and trade-offs, not just about
shape. Wave details are refined once the A stage completes.

### E1 — Param Solver v1 ⬜

Requirements → derived dimensions → constraints → conflicts → suggested
compromises. NOT a general CSP: a library of deterministic derivation rules
on top of `product/resolve.py` (the order is fixed; determinism and
reproducibility are preserved). Conflicts are typed findings with suggested
compromises ("2 screws + a rib below + a wider plate"), in the spirit of
the repair rules.

Example criterion: "a holder for a 65 mm handle, 2 butterfly anchors,
economical but strong" → saddle_d, mouth_gap, wall, screw_spacing,
rib_count are derived and every value is justified by a rule reference.

### E2 — Load Path Analyzer (physics-lite) ⬜

The chain: load → lever → moment → fastener → wall → material → margin.
Without FEA: `cantilever_moment_check`, `screw_edge_distance_check` (a
generalization of min_web), `boss_strength_check`,
`heat_zone_material_check`; material profiles (PLA/PETG/ASA/PETG-CF) with
temperature limits. `load_paths:` generalize from the bio archetypes to all
load-bearing archetypes; at the assembly level the force chain runs through
the joints (lamp moment → dovetail → plate → wall anchors).

Criterion: the golden case "a 1.2 kg grow lamp at 180 mm reach" gets an
estimated_moment, a risk grade and recommendations backed by measurable
probes.

### E3 — Failure Mode Critic ⬜

A separate "how will this break" layer: a deterministic rule core over
IR+assembly (a thin dovetail root at a boss, a channel through a
load-bearing rib, screwdriver/nut access, a sharp inner corner in a TPU
recess, plate flex) + an LLM critic strictly as a hypothesis generator —
every hypothesis must be confirmed by a measurable probe, otherwise it is a
WARN note, not a finding. Output: top risks + suggested patches (typed,
like repair).

### E4 — Manufacturing Planner ⬜

AF thinks like a 3D-printing operator: `split_if: max_dimension_gt` (a cut
through butt_pin/dovetail from A1), per-part orientation,
tolerance/nozzle/material profiles, `avoid_supports_in` (channels, bosses,
dovetail slots), strength_direction vs layer direction (the link to E2). A
separate concern is keeping biomorphic surfaces within real printability.

Deep-mechanics clients, one iteration apiece (as in BUILDERS.md):
`pin_hinge`, `friction_hinge`, `living_hinge` (fatigue), threads,
`ratchet_teeth` — bounded-v1 geometry for these shipped in expansion wave
R2; inside the E stage each returns with its own physics and validators.

---

## AF v4 — Self-Extending Platform (waves M1–M3)

Goal: the system extends itself and learns from the workshop. Broad
strokes — details after the E stage.

### M1 — Functional Grammar & Multi-Resolution ⬜

Verbs of engineering action as the internal language: `attach_to_wall`,
`clamp_around`, `support_payload`, `route_cable`, `snap_fit`,
`split_for_printing`, … A request unfolds into a functional plan, then
into geometry:

```text
L0 functional block diagram → L1 layout volumes → L2 Form IR
  → L3 CAD solids → L4 manufacturing split → L5 print package
```

This is also the slot for LLM phase 4: the LLM is a translator of intent →
functional plan / requirements (A3); the engine does archetype and port
selection. Absorbs the "R5 assembly-intents" from the README —
prompt→assembly composition (the LLM composing multi-part assemblies from
the catalog via the Assemble screen) is already shipped; the verb grammar
is not.

### M2 — Design Memory / Workshop Feedback Loop ⬜

Every printed product returns into the system:

```yaml
build_observation:
  artifact_id: wall_tool_mount_65mm_v1
  print_success: true
  assembly_success: partial
  field_test: failed_after_2_days
  notes: "wall plate flexes"
  recommended_catalog_patch: [increase_backplate_ribs, add_triangular_buttress]
```

Observations → ledger → recommended catalog patches (via the existing
repair mechanism). The project's main moat: accumulating real print and
field experience, not abstract "learning".

### M3 — Catalog Authoring Pipeline ⬜

Catalog self-extension: request analysis → a YAML variant / composite /
recipe over existing ops / a new builder via sandbox → golden tests →
benchmark suite → promotion up the maturity ladder (`draft → … →
production_buildable`, already introduced in BIOMORPHIC.md). New builders
are born as a draft/coding-agent task, never as arbitrary Python at
runtime (the law from BUILDERS.md).

---

## Parallel line P — Props & Wearables (waves P1–P4)

Audience expansion: cinema (production design + functional fabrication) and
fashion (parametric atelier). The line runs parallel to the A/E waves, like
the Bio line; it leans on A1 (ports), A2 (packages), A3 (requirements). The
biomorphic line is its bridge: to engineering AF it gives style, to cinema
biomech props and creature parts, to fashion wearable armor and organic
accessories.

### P1 — Neutral Core & Mode Scaffolding ⬜

- An audit of the core language: "artifact" terminology in schemas/docs,
  neutral names wherever engineering semantics is not mandatory.
- `mode:` as a profile on top of A3/A2: default requirements, package
  composition, gate weights; a mode switch in the Cockpit. No new
  geometry — only priorities and vocabularies.
- Criterion: the same artifact run in the Engineering and Cinema modes
  yields different requirements defaults and different packages with
  identical geometry and identical honesty verdicts.

### P2 — Body / Human Fit Layer v1 🔶 (core implemented 2026-07-07)

Implemented (AF's first wearable artifact): `forearm_cuff_v1` +
`catalog/examples/forearm_flashlight_cuff.yaml` — grade A, side_profile,
S/M/L from one YAML by changing body_fit (locked by a test). Included:

- a `body_fit:` block on ProductInstance (`BodyFitSpec`, human ranges,
  `env_context()` → body_* names in resolve);
- micro-P1: `mode:` + the `MODE_PROFILES` registry (product/modes.py;
  wearable requires body_fit BEHAVIORALLY, mode/mode_tags in the summary);
- a resolve honesty fix: a non-resolving formula default = a named FAIL
  (this is exactly the body_fit require mechanism);
- the `BODY_CONTACT_SURFACE` role (absolute skin protection in all
  PROTECTED sets) + 7 measuring checks (donning throat, skin clearance,
  comfort edges, pad recesses, payload not-on-skin, snap retention, strap
  access) + `topology.payload_void_open`;
- the op `forearm_cuff_body` (a chordal mouth + strap tabs + the flashlight
  snap-C = the first client of `cylindrical_cradle`), the modifier
  `add_strap_slots` (a P3 preview, 15–40 mm straps, a skin guard around the
  arm circumference).

P2 remainder: other body regions (wrist/thigh/…), size grading via
families (A4), a bio skin on the cuff (the Bio-4M stage B canvas).

The body as a first-class input — no scanner, parametric:

```yaml
body_fit:
  region: forearm        # head | neck | shoulder | forearm | wrist | chest | waist | thigh | foot
  circumference: 270mm
  length: 240mm
  clearance: 6mm
  strap_width: 25mm
```

- A table of anthropometric regions with default ranges; size grading =
  parametric families (the extends/preset mechanism from A4).
- The `body_contact_region` role arrives together with its consumer:
  skin_clearance validators (the body clearance is measured), edge safety
  (contact edges rounded — a generalization of contact_r), weight (mass
  from volume × material).
- Driver client: **a forearm flashlight holder** ("a biomechanical holder
  on an actor's arm") — a body-cradle core + strap interfaces (P3) + a
  Bio-4M bio skin. One artifact covers cinema and wearable at once.
- Criterion: the golden example builds under two different `body_fit`
  values (glove sizes S and L) with no hand-editing of geometry; clearance
  and edges are measured.

### P3 — Soft–Hard Interfaces ⬜

The junction of rigid prints with the soft world — as interface
profiles/ports (the A1 mechanism) and modifiers (the kernel already
supports them):

- `strap_slot` (a generalization of the zip_tie slots to 20/25/38 mm
  straps), `sew_hole_row` (sewing to fabric), `velcro_patch_zone`,
  `elastic_band_anchor`, `foam_pad_recess` (kin of the clamp's TPU
  recesses), `fabric_clamp`; for cinema — `LED_channel` (kin of
  cable_channel + a diffuser window), `rigging_point` (a verified
  suspension point with a load_rating), `hidden_mount`,
  `quick_release`/`quick_repair_joint` (fast replacement of a broken part
  on set).
- Every interface is typed, with a validator (the slot is measured, the
  hole row does not tear the edge, the LED channel is continuous — reusing
  channel_continuous).
- Criterion: the P2 artifact gets straps + sewing points; the BOM (A2)
  automatically includes the strap/velcro as hardware items.

### P4 — Style Grammar + Mode Production Packages ⬜

- **A grammar of styles**: a registry of style packs on top of
  SurfaceStyle/Bio-4M — `giger_exoskeleton` (the engine already exists:
  implicit SDF skin), `retro_sci_fi`, `alien_organic`,
  `brutalist_utility`, `ritual_object`, `soft_biomorphic`, … The law is
  unchanged: style applies only via regions/keepouts and has NO right to
  break function (the BIOMORPHIC.md canon); every pack is sliders →
  controlled form/SDF passes, not "make it pretty".
- **Per-mode packages** (an A2 extension): cinema — a split for painting,
  magnet seats, LED routing, an assembly diagram, hero/stunt/background
  variants of one artifact (different weight/detail/material from one
  YAML); fashion — sizes, weight, a sewing/strap diagram, contact zones,
  material recommendations, an edge-safety report.
- Criterion: one artifact produces hero (implicit skin, high detail) and
  stunt (light, TPU, simplified) variants with one command; the reports
  honestly distinguish what was verified in each.

---

## PK line — Pack Economy (canon: [ECOSYSTEM.md](ECOSYSTEM.md))

PK-1 is shipped; the remaining waves are ⬜ (a declaration; implementation
in separate iterations):

- **PK-1 Pack Mechanism v1** ✅ — `packs/` as the loader's third source,
  `pack.yaml`, origin=`pack:<id>`, license/author metadata + notices in
  reports; VF carved out into its own pack and shipped as a FREE bundled
  pack (tier: free, Apache-2.0).
- **PK-2 Free Starters + Certified Criteria** 🔶 — the official free
  showcase pack (studio/repair/jigs/education) and community templates
  shipped (R1-Showcase); Certified criteria and the repo-boundary map
  remain ⬜.
- **PK-3 Commercial Layer** ⬜ — personal/commercial marking, notices
  in the build package; no DRM in core (entitlement only in cloud).
- **PK-4 Web Studio** ⬜ — a paid configurator on top of the core API;
  the Cockpit stays an open local debugger.

The **CP — Community Packs** subline (canon: [ECOSYSTEM.md](ECOSYSTEM.md),
"Community Operating Model"): CP-1 Pack Template ⬜ · CP-2 Community
Registry ⬜ · CP-3 Certification Review ⬜ · CP-4 Maintainer/Governance ⬜.
Rule: a community pack may be useful without a certificate; a Certified one
must be "boringly reliable". Repo publication is gated by the OS checklist
(OS-1 license … OS-8 public roadmap, see ECOSYSTEM.md).

---

## Absorbed tracks

| Former plan | Where it went |
|---|---|
| `dovetail_joint` / `tongue_groove` (R4 remainder) | **A1** — the ports' driver client |
| `rail_slider` (R5 remainder) | **A4** — the Workshop Wall System rail |
| "R3 split_plane → R4 snap/dovetail → R5 assembly-intents" (README) | split_plane ✅ (butt_pin), snap ✅; dovetail → **A1**, assembly-intents → **M1** (prompt→assembly composition shipped) |
| `pin_hinge`, `friction_hinge`, `living_hinge`, threads, `ratchet_teeth` | **E stage**, one iteration apiece with its own physics (bounded-v1 geometry shipped in wave R2) |
| Bio-4A (extends/preset/family) | the mechanism is built in **A4** |
| Bio-4B presets, Bio-5 curved, Bio-6 motifs & assemblies | a parallel line; multi-part bio assemblies — after **A1** (ports) |
| Bio-4M implicit SDF skin (BIOMORPHIC.md) | the giger/creature style-pack engine in **P4**; stage B (clamp integration) stays in the Bio line |
| `space_colonization_branching` | after Bio-5, off the critical path |
| Phase 4 "LLM frontend" (README) | the requirements translator in **A3**, the functional plan in **M1**; the LLM is never the brain of geometry |
| add_zip_tie_slots, TPU recesses, magnet pockets | forerunners of the **P3** soft–hard interfaces |

## Rules of the road

1. A wave is closed only with: a golden example + tests + `verified_by`
   validators for every claimed feature. Status in the tables flips to ✅
   only after that.
2. Nothing is marked done without a measurable check — the honesty canon
   extends to the roadmap itself.
3. The order of the waves may change with the circumstances of the
   workshop; a wave's acceptance criteria may not (they can only be
   honestly revised in a dedicated commit).
4. The document is updated at the end of every wave; obsolete tracks are
   not erased but moved into "Absorbed tracks".
5. One core for all audiences: a mode changes priorities, vocabularies and
   package composition — it never weakens checks and never forks geometry.
6. New region roles and mode entities strictly follow the law "a role
   arrives with its consumer": an entity appears together with the
   validator that measures it; otherwise it is a vocabulary hallucination.
