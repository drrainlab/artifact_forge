# Pet / Aquarium / Terrarium — domain plan

Statuses: ✅ implemented · 🔶 partial · ⬜ not started. Template canon —
[INDEX.md](../INDEX.md); commercial rules — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope and positioning

Mounting hardware and systems around aquariums, terrariums and pet care: clips
for air/drip tubing, sensor and diffuser holders, light brackets,
mesh dividers, feeder enclosures, later — dispensers and misting.
AF's unique advantage: **the VF water discipline transfers wholesale**
— transient water path, water_report, overflow honesty and fluid ports already
exist and are proven; no STL catalog will tell the user
where the water goes on failure. The second advantage — parametric
families for non-standard tube diameters and glass thicknesses.

What claims this domain does NOT make:

- Does NOT claim "safe for animals" and does NOT claim aquarium
  non-toxicity of materials without tests — only warnings and material
  recommendations (PETG, "no brass inserts in water", etc.).
- Does NOT cover life-support products whose failure kills the animal
  (heater guards claiming protection, auto-feeding as the
  sole food source) — only with an explicit "not the sole
  system" note.
- Does NOT promise resistance to biofilm/fouling — a regular-cleaning
  warning in every wet report.

## 2. Mode / Environment / Tier

Domain = pack + environments, NOT a new mode: dry mounting lives in
Utility/Engineering; everything watery lives in the existing Fluid/Grow contract.

```text
mode:        Utility / Engineering (dry) · Fluid/Grow (wet systems)
environment: wet / humid (ECOSYSTEM vocabulary; technical carrier ⬜, PK line)
tier:        Free + Certified; Pro — only once a serious system appears (§7)
```

## 3. What the engine already has — reuse map

| Domain block | How it is built today | Status |
|---|---|---|
| Tube clips Ø4–16 (air/drip/CO2) | `pipe_clip_v1_sideprint` (snap_c) + `axial_channel` | ✅ |
| Fastening clips to glass/stand | `zip_tie_anchor`, zip slots, `wall_ring_mount`, wall hooks | ✅ |
| Light brackets | `lamp_bracket_v1` + `lamp_socket_cup_v1` | ✅ |
| Meshes/dividers/false bottom | `mesh_floor` (orthogonal through mesh) + mesh integrity check (manifold) | ✅ |
| Feeder enclosures, electronics boxes near water | enclosure base/lid (+snap), `rounded_box_shell`, `port_cutout`, `wire_exit`, grommets | ✅ |
| **Water discipline wholesale** | transient water path (TRANSIENT_WATER_PATH role), "no hidden reservoirs", water_report (topology, drainage, containment), overflow honesty (VF-4.2), fluid_inlet/outlet ports (gravity is the pump) | ✅ |
| Clamps on tubes/rods | `clamp_half_lower/upper` (TPU pad lands — do not scratch glass/acrylic) | ✅ |
| Cable near water (drip loop) | cable_raceway/comb, `cable_pass` port, `cord_slot_pair` | ✅ |
| Gate/shutter mechanics for dispensers | hinge/slide op missing | ⬜ (PT-3, E stage) |
| Material/toxicity metadata | no carrier — warnings are text notes for now | ⬜ |
| wet/humid environment profile on instance | carrier missing | ⬜ (PK line) |
| Suction cups / magnet-through-glass fit | magnet pockets ✅, but the "through glass t" pair is not validated | ⬜ |

## 4. Waves PT-1..3

### PT-1 — Dry Mounts ⬜

Everything outside the water: tube clips, hose organizers, stand brackets.
Golden: **`aquarium_tube_clip_family`** — a snap_c clip as a
parametric family with presets **Ø4 / 6 / 8 / 12 / 16** (airline
tube → drip line → filter hose) + zip fastening to glass/stand
(zip slots) in one YAML. The family proves the same thing the second cassette
proved for VF: when the preset changes, the snap physics (strain) is
recomputed and validated on every Ø, not on a single "reference" one.

Closure criterion: family at grade A on all five presets;
`form.tube_clip_retention_ok` (§6) measures retention by reusing the snap
physics; side-goldens on ready archetypes: a lamp_bracket preset "aquarium
light", a net/scraper hook (as a wall_hook preset).

### PT-2 — Wet / In-Tank ⬜

Holders at the waterline and in the water: diffuser/misting-nozzle mount,
sensor holders (temperature, TDS) on glass, flow guides.
The wave's key work — **mandatory material/toxicity warnings** in
reports: any instance with the TRANSIENT_WATER_PATH role or an
in-tank flag gets `manufacturing.wet_material_warning` (§6) — a block of
recommendations (PETG/PP, no brass/copper in water, biofilm cleaning) and an
honest "not tested for toxicity". This is a bid for the ECOSYSTEM
**wet-safe-tested** trust badge — but the badge comes only AFTER real
tests; until then, a warning layer. Suction cup / magnet-through-glass — once
the pair validation is ready ⬜.

### PT-3 — Systems (feeder-dispensers, misting) ⬜

First systems: a gravity feeder-dispenser (hopper enclosure +
shutter/gate — **blocked by the hinge/slide op ⬜**, E stage; until then —
static feeders without mechanics) and terrarium misting —
a direct VF reuse: fluid_inlet/outlet ports, handover only downward,
water_report over the entire chain "user's reservoir → nozzles → drainage",
overflow honesty ("where it drips on failure" — a mandatory block).
Criterion: one system golden with a full water_report and
`assembly.no_orphan_fluid_ports` green.

## 5. Domain interfaces and standards

**Tube Clip Standard** (modeled on the Cassette Interface Standard):

1. **Shared parameters** (names are the contract): `tube_d` (nominal 4–16),
   `clip_grip_pct` (C-profile wrap), `retention_gap` (band),
   `mount_kind` (zip / screw / hook).
2. **Frame keys**: `tube_axis`, `clip_mouth_w`, `anchor_slot_xy` —
   published by the builder, measured by validators.
3. **Typed ports**: tube in clip — the existing
   `cylindrical_payload_socket` (reuse of A1 mate validation); water —
   ONLY the existing `fluid_inlet`/`fluid_outlet` (fluid_joint:
   handover only downward — "gravity is the pump" applies to
   misting too); sensor cable — `cable_pass`. PT-1/PT-2 introduce
   no new types.
4. **Wet convention**: every wet path is declared via the
   TRANSIENT_WATER_PATH role; hidden cavities in the wet zone are a FAIL via
   reuse of the VF cleanability checks (the brush reaches wherever water does).

## 6. Validator candidates

| Validator | What it measures |
|---|---|
| `form.tube_clip_retention_ok` | C-profile wrap/opening vs tube_d: retention present, snap-in strain within band (snap-physics reuse) |
| `form.clip_glass_contact_soft` | contact lands on glass/acrylic are flat or TPU recesses (pad-land reuse) — no scratching |
| `manufacturing.wet_material_warning` | wet-zone instance carries a material block (recommendations + "not tested for toxicity" + cleaning note); gap: toxicity/material metadata ⬜ — until the carrier the check verifies the warning block is present in the report |
| `form.no_hidden_wet_cavity` (VF reuse) | no closed cavities in the wet zone; everything is washable |
| `assembly.no_orphan_fluid_ports` (reuse) | every PT-3 fluid chain is closed: inlet, path, drainage |
| water_report (VF reuse) | water topology, containment, overflow honesty for PT-3 systems |

## 7. Free / Pro boundary (Printables test)

| Free / Certified | Pro |
|---|---|
| tube_clip_family (all Ø), hooks, brackets | — |
| sensor/nozzle holders with wet-warnings | — |
| static feeders | — |
| — | only once a serious system appears: a dispenser with mechanics / a misting system with water_report, family presets and BOM |

A single clip is Googlable on Printables in a minute — Free by test.
Until PT-3 delivers a system (dispenser/misting), the domain has no Pro
shelf — this is honestly recorded; the domain lives as a Free/Certified
showcase of wet discipline.

## 8. Risks and claims

- **"Safe for animals" is not claimed.** Neither non-toxicity nor
  fish-safe/reptile-safe — only material recommendations and warnings;
  the wet-safe-tested trust badge comes after real tests, not before.
- **Biofilm/cleaning**: every wet instance carries a regular-cleaning
  note; geometrically — VF-cleanability reuse (no hidden cavities).
- **Life support**: feeder/misting always with a "not the sole
  system" note; fault tolerance is not claimed.
- **Water + electrics**: sensor/light holders carry a drip loop note
  (cable below the entry point) — a note, not a gate, until the environment carrier ⬜.
- **UV/moisture and material**: PLA degrades near water — a PETG/PP
  recommendation in every wet report.

## 9. Connections

- **VF line ✅** — the core donor: water discipline (transient path,
  water_report, overflow honesty VF-4.2), fluid_joint, cleanability checks,
  mesh_floor + mesh integrity; PT-3 misting is the first external consumer
  of the VF water ports.
- **A1/A1.5 ✅**: `cylindrical_payload_socket`, `fluid_inlet/outlet`,
  `cable_pass`, mate validation — PT contributes nothing new to the registry
  before PT-3.
- **A2 BOM ⬜**: tubes/zip ties/suction cups as hardware items of the systems.
- **E stage ⬜**: the hinge/slide op unblocks the dispensers' shutter
  mechanics (PT-3).
- **PK line ⬜**: the wet/humid environment carrier is exactly the gap
  this domain turns from text notes into gates; the PK-2 Certified criteria
  are the target shelf for PT-1/PT-2.
- **Neighboring domains**: electronics (sensor enclosures near water — shared
  enclosure ops + wet-warnings), mobility (env gates as a parallel
  precedent for the environment profile).

The shared capability gaps of this domain (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the domain
is their CLIENT, not their owner.
