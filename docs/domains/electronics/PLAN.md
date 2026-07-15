# Electronics / IoT / Smart Home — domain plan

Statuses: ✅ implemented · 🔶 partial · ⬜ not started. Template canon —
[INDEX.md](../INDEX.md); commercial rules — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope and positioning

Enclosures and rigging for DIY/IoT electronics: ESP32/Arduino/Raspberry Pi
boxes, sensor mounts, cable entries, DIN-rail and 2020 mounts, ventilation,
wall boxes. The most "ready" domain of the engine: enclosure archetypes (screw
AND snap), port_cutout with PORT_SIZES, standoffs, wire_exit and the whole
cable-management suite already exist — EL-1 is nearly pure YAML on top of ops.

What claims this domain does NOT make:

- Does NOT claim IP ratings (IP54/IP65…) without a physical test — until
  the seal contract ⬜ the word "waterproof" cannot appear in reports.
- Does NOT certify mains-voltage enclosures: PETG/ABS are not UL94-V0 by
  default; 230V mains is an insulation/flame-resistance warning, not a
  supported scenario.
- Does NOT promise EMI shielding or thermal design (ventilation is measured
  by geometry, not CFD).

## 2. Mode / Environment / Tier

Domain = pack, NOT a new mode: the enclosure contract is fully covered by
Engineering (walls, ports, fasteners, frames) + Utility.

```text
mode:        Engineering / Utility
environment: indoor / outdoor / wet / high-heat
tier:        Free (single enclosures) + Pro (families)
```

## 3. What the engine already has — reuse map

| Domain block | How it is built today | Status |
|---|---|---|
| Screw enclosure | `enclosure_base_v1` + `enclosure_lid_v1` (joint screw + lid_seat) | ✅ |
| Snap-fit enclosure | `enclosure_base_snap_v1` + `enclosure_lid_snap_v1` (snap strain physics) | ✅ |
| Connector cutouts | `port_cutout` + PORT_SIZES (usb_c/audio/…) | ✅ |
| PCB standoffs | `standoff_pattern`, `boss_pattern`, `heatset_insert_pocket`, `nut_trap` | ✅ |
| Cable exits | `wire_exit`, `cord_slot_pair` | ✅ |
| Ventilation | hex/grid field modifiers | ✅ |
| Cable rigging around the node | `cable_junction_box_v1`, `cable_raceway_v1`, `cable_grommet_plate_v1`, `cable_comb_v1`, `underdesk_cable_clip_v2/v3` | ✅ |
| Anchoring/ties | `zip_tie_anchor_v1`, `strap_slot_pair` port | ✅ |
| Mounting on 2020 profile | `aluminum_profile_ref_v1`, `profile_seat_slot`, `endcap_dock_pockets` | ✅ |
| Assembly cable ports | `cable_pass` type (A1 registry; no instances) | 🔶 |
| DIN-rail clip | TS35 spring-latch op | ⬜ |
| Cable gland (threaded entry) | threads | ✅ shipped (`thread_internal_clearance`, `threaded_plug_body`) |
| Seal contract (gasket/labyrinth) | groove + continuity validator | ⬜ |
| Enclosure marking | text/label embossing op | ⬜ |
| Environment profile on instance (outdoor gate) | environment carrier | ⬜ (PK line) |

## 4. Waves EL-1..3

### EL-1 — Board Families + Sensor Mounts ⬜

Board presets for ESP32 / RPi Zero / RPi 4 / Arduino Nano/Uno on
EXISTING ops: a "board → standoff pattern + port cutouts" table —
nearly pure YAML. Sensor mounts (BME280/PIR/camera) — small plates with
hole patterns + `zip_tie_anchor`/strap.

Golden artifact: **`esp32_sensor_node_box`** — `enclosure_base_snap_v1`
+ `standoff_pattern` for ESP32 + `port_cutout` usb_c + hex-vent field +
`wire_exit` for the sensor ribbon; lid `enclosure_lid_snap_v1`.

Criterion: golden at grade A; standoff pattern and ventilation covered
by validators (§6); swapping the board via preset (esp32 → nano) does not touch
the YAML structure — only the board key (pinned by a test).

### EL-2 — Mounting: DIN / 2020 / Gland ⬜

- **DIN-rail clip op ⬜** — the domain's main new op: a TS35 spring
  latch (a relative of the snap strain physics); it ships strictly with its
  own retention validator.
- **2020 mounts** — reuse of `profile_seat_slot`/`aluminum_profile_ref_v1`
  + dovetail/screw ports: a box on the profile with no new hardware.
- **Cable gland** — thread ops have shipped; before them an honest
  surrogate: `wire_exit` + a zip-tie clamp (`zip_tie_anchor`) as
  strain relief, without the word "gland" in the report.
- Criterion: golden din_mounted_box (the same esp32 box with a swapped
  mounting preset) + a 2020 variant; clip retention measured.

### EL-3 — Outdoor / Wet ⬜

- **Seal contract ⬜**: a groove for cord/TPU gasket around the perimeter of
  lid_seat + a contour continuity validator (link to VF water
  discipline: "no hidden wet cavities", leak path is controlled).
- Drip loops / bottom entries: the rule "water does not run in along the cable" —
  a geometric check that wire_exit points downward.
- Until a physical test the best honest verdict is "rain-shielded,
  not rated"; IP claims remain out of scope (§1, §8).
- Criterion: golden outdoor_sensor_box with a seal groove; contour
  continuity and entry direction — via validators.

## 5. Domain interfaces and standards

**Board Mount Standard** (modeled on the Cassette Interface Standard):

1. **Shared parameters** (name contract): `board_l`, `board_w`,
   `hole_pattern` (list of xy), `standoff_h`, `port_side`,
   `port_offsets`, `vent_ratio`, `mount_kind` (din|2020|wall|strap).
2. **Frame keys**: `pcb_floor_z`, `standoff_top_z`, `port_face_*`,
   `lid_seat_z`, `vent_zone_uv` — published by the builder, measured
   in pose (the connector must land in the cutout — a mate probe, not faith).
3. **Typed ports**: lid↔base — the existing `screw_pattern`/
   `snap_joint` (+ lid_seat joint); cable through the assembly's walls —
   `cable_pass` (the type exists in the A1 registry, first instances come from
   this domain); mounting on a profile — `dovetail_rail`/`screw_pattern`. A new
   candidate type `din_rail_clip` is introduced in EL-2 together with its
   mate/retention validator ⬜.

## 6. Validator candidates

| Validator | What it measures |
|---|---|
| `form.board_standoff_pattern_ok` | standoff pattern matches the board's hole_pattern within band, standoffs not under connector keepout zones |
| `form.vent_area_ratio_ok` | total vent-field area ≥ vent_ratio of the wall area; bridges ≥ min_wall |
| `form.port_cutout_reachable` | cutout coaxial with the connector at standoff_h (frame probe), chamfer on the cable entry |
| `form.din_clip_retention_ok` (future, EL-2) | TS35 latch strain within band, screwdriver release travel provided |
| `form.seal_groove_continuous` (future, EL-3) | gasket groove is a closed contour of constant cross-section |
| `manufacturing.gland_thread_printable` (future, after threads) | entry thread printable with the chosen nozzle/orientation |

## 7. Free / Pro boundary (Printables test)

| Free / Certified Free | Pro |
|---|---|
| single enclosure for a specific board (esp32_sensor_node_box) | families: boards × entries × mounting (DIN/2020/wall/rail) |
| sensor mount, zip anchor | outdoor variants with the seal contract and print notes |
| — | private board profiles (own PCBs) + the A2 package (BOM: screws, inserts, gasket) |

An ESP32 enclosure exists on Printables by the thousands — Free by test; what
is paid is the combination matrix with mate probes and reports.

## 8. Risks and claims

- **Mains voltage**: 230V volumes — a hard warning (insulation,
  flame resistance: PETG/ABS are not UL94-V0 by default); the domain does not
  certify electrical safety.
- **IP ratings**: not claimed without a test; the seal groove yields
  "rain-shielded", not "IP65" (honesty canon).
- **Thermals**: vent_ratio is a geometric measure, not a thermal calculation;
  hot boards (RPi 4 under load) — a note about forced airflow.
- **Board dimension drift**: Arduino/ESP32 clones drift on hole positions —
  board presets carry a source note and a band, not a point value.
- **Wave dependencies are honest**: the gland was not promised before threads shipped;
  the DIN clip does not merge without a retention validator.

## 9. Connections

- **A1/A1.5 ✅**: lid/snap/screw ports and mate frames already carry the
  enclosure; `cable_pass` gets its first instances here; `din_rail_clip` is a
  candidate for the type registry.
- **A2 BOM ⬜**: `esp32_box_with_lid` is already a named criterion of wave
  A2; the domain is its first consumer (screws/inserts/gasket in the BOM).
- **A4 families ⬜**: the "boards × mounts" matrix waits for extends/preset.
- **E stage**: threads ✅ shipped (glands unblocked), E2 material profiles (thermals) ⬜.
- **VF line ✅**: water discipline and leak-path thinking are the model for
  the EL-3 seal contract; 2020 mounting is shared with the VF-4 profile ops.
- **Domains**: jigs (soldering fixtures for the same board presets),
  repair (enclosure latches/lids — shared snap ops).

The shared capability gaps of this domain (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the domain
is their CLIENT, not their owner.
