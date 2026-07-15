# Mobility / Bike / Vehicle — domain plan (MB)

Expansion of the domain from [ECOSYSTEM.md](../../ECOSYSTEM.md) ("Future Domains
to Watch → Mobility / Bike / Vehicle Accessories"). Template canon —
[INDEX.md](../INDEX.md).

## 1. Scope and positioning

Accessories for bicycles, car interiors, and van/camper spaces:
handlebar mounts for lights and cameras, interior clips and organizers,
cargo organization on 2020 profiles. AF's value versus STL catalogs:
the handlebar diameter is a PARAMETER (22.2 / 25.4 / 31.8 mm — one YAML),
the payload is a swappable dovetail adapter, environment gates are
validators, not fine print in the description.

**Which claims the domain does NOT make:**

- NOT the airbag zone, NOT the pedal zone, NOT the driver's field of view;
- NOT a road-safety-critical part (brakes, steering linkages, child seats);
- no crash-rated / vibration-rated claims without measuring probes;
- PLA for the high-heat interior is forbidden by a gate, not "not recommended".

## 2. Mode / Environment / Tier

The domain = pack, NOT a new mode (the rule of five axes). Auto/Vehicle is an
**environment profile**, not a mode: that's how ECOSYSTEM decided ("base mode +
warnings; a separate Mobility mode ONLY when the corresponding
validators appear").

```text
mode:        Engineering / Utility / Workshop
environment: vehicle / outdoor / high-heat / vibration / UV
tier:        Free + Certified Free; Pro — families and systems
```

## 3. What the engine already has — the reuse map

The domain's compass: **the bike light mount is almost assembled from existing
parts** — a handlebar is a tube, and all of A1's cuff-adapter mechanics are
already golden on the forearm.

| Building block | Status | Reuse in the domain |
|---|---|---|
| `pipe_clip_v1_sideprint` (snap_c arc retention) | ✅ | handlebar = tube Ø22.2–31.8; same arc physics, same sideprint "zero overhangs" |
| A1 swap mechanics: `forearm_cuff_socket_v1` + `flashlight_adapter_25_v1` ↔ `rail_plate_adapter_v1`, harness `assembly/swap.py` | ✅ | flashlight ↔ action-cam plate on the handlebar — the SAME dovetail_rail socket and the same harness, the mount body doesn't change by a byte |
| Interfaces `dovetail_rail`, `snap_joint`, `strap_slot_pair`, `screw_pattern` (frame normal/up, mate validation, `forge compat`) | ✅ | the domain's typed ports are ready, the compatibility matrix is derived |
| `wall_ring_mount`, `clamp_half_lower/upper` (TPU lands) | ✅ | clamp mounts on frame tubes / camper posts |
| `add_strap_slots` (15–40mm), `add_zip_tie_slots`, `cord_slot_pair` | ✅ | straps/zip ties — standard velo mounting |
| `aluminum_profile_ref_v1` (2020) + `profile_seat_slot`, `endcap_dock_pockets` | ✅ | van/camper cargo systems on the standard profile |
| `edge_magnet_pockets`, `nut_trap`, `heatset_insert_pocket` | ✅ | removable organizer lids, metal fasteners |
| `form.stability_footprint` (COM), snap strain physics | ✅ | the basis for retention checks |
| Environment-profile carrier on the instance | ⬜ | BLOCKER for MB-2: there's nowhere to hang material gates by environment |
| Vibration validators | ⬜ | honestly: no measuring probes — only WARN hints |
| Text embossing op ("NOT FOR SAFETY USE" marking) | ⬜ | desirable, not a blocker |

## 4. Waves MB-1..3

### MB-1 — Handlebar Mount System ⬜

Golden artifact: **`bike_light_handlebar_mount`** — a snap_c clip on the
handlebar (arc retention from `pipe_clip_v1_sideprint`, parameter bar_d) + a
`dovetail_rail` socket; the flashlight ↔ action-cam plate swap goes THROUGH
the existing swap harness (`flashlight_adapter_25_v1` / `rail_plate_adapter_v1`
reused as-is or with a minimal preset). Additionally: a strap mount variant
(`add_strap_slots`) for carbon handlebars where a snap is undesirable.

Criterion: the golden works for bar_d 22.2 and 31.8 with no manual geometry
edits; `interface.swap_part_builds` + `form.handlebar_retention_ok` are green;
`forge compat` shows the handlebar-clip mate ↔ both adapters.

### MB-2 — Car Interior Clips ⬜

Cable/glasses/parking-card clips, dashboard-safe holders
(not in the field-of-view/airbag zone). **Dependency: the environment carrier
on the instance ⬜** — the "PLA is not for the interior" gate must become a
measurable `manufacturing.material_env_ok`, not a note. Until the gate closes,
the wave does not start (a feature without a validator = a hallucination).

### MB-3 — Cargo / Van / Camper ⬜

Organizers on 2020 profiles (reuse of `aluminum_profile_ref_v1`,
`process: reference` from VF-4): hooks, trays, strap anchors, dividers.
A family with a unified mounting pitch — a candidate for the A4 mechanism.

## 5. Domain interfaces and standards

**Handlebar Mount Standard** (modeled on the Cassette Interface Standard):

- shared parameters: `bar_d`, `clamp_w`, `strap_width`, `payload_offset`;
- frame keys: `bar_axis` (tube axis), `payload_n` (socket normal),
  `strap_tab_*`;
- typed ports: `dovetail_rail` (payload, female on the clip),
  `strap_slot_pair` (strap), `snap_joint` (handlebar arc grip);
  the cassette lesson is reused: `shared:` overwrites the parameters of the
  swapped part — adapter desync is unrepresentable.

The domain does NOT multiply payload adapters: any existing/future
dovetail adapter of the platform (flashlight, plate, future ones) is
compat-compatible.

## 6. Candidate validators

| Validator | Basis | Status |
|---|---|---|
| `form.handlebar_retention_ok` | reuse of snap strain 1.5·δ·t/L² + arc coverage | ⬜ (assembled from existing parts) |
| `form.bar_diameter_in_range` | interface clearance band | ⬜ |
| `manufacturing.material_env_ok` | environment carrier ⬜ — capability gap | ⬜ BLOCKER for MB-2 |
| `assembly.payload_swap_verified` | direct reuse of `interface.swap_part_builds` | ✅ mechanics |
| `manufacturing.vibration_hints` | **WARN level**: honestly — without measurements this is a warning (locknut/safety zip tie), not a check | ⬜ |

## 7. Free / Pro boundary (the Printables test)

| Free / Certified | Pro |
|---|---|
| bike_light_handlebar_mount for one bar_d, a simple interior cable clip, a single hook on 2020 | the family "the whole handlebar range × payload adapters" with a compat matrix and reports |
| single organizers | a van/camper cargo SYSTEM (unified pitch, BOM, print notes) |
| — | commercial output / print-farm license |

A single flashlight holder exists on Printables — it's Free. What's paid is
the system: parametric range + verified swap + reports.

## 8. Risks and claims

1. The environment is aggressive (UV, +70°C interior, vibration) — until
   environment gates appear, the domain must carry a `vehicle-environment-warning`
   (Pack Trust Badge from ECOSYSTEM) on all products.
2. Do not pass off vibration hints as checks: a WARN with the text "not measured".
3. A legal frame in every PACK.md: accessory, not a safety device;
   the installation zone is the user's responsibility, but the forbidden zones
   are listed explicitly.
4. Mount failure = losing a light/camera, not a crash — the payload class of
   the products is fixed in claims (no child-seat brackets whatsoever).

## 9. Connections

- **A1/A1.5 ✅** — the domain's load-bearing mechanics (ports, dovetail, swap
  harness, frames); MB-1 is the third swap driver after the cuff and VF cassettes.
- **A2 BOM ⬜** — straps/screws/nuts of MB products in the build package.
- **Environment carrier ⬜** (PK line, "technical carriers") —
  the blocker for MB-2; MB is its first real client-customer.
- **P line** — strap mechanics (P2/P3) shared with wearable; camper hooks
  border on the Workshop Wall System (A4).
- **VF line** — the 2020 profile and `process: reference` are reused in MB-3.
- Neighboring domains: repair (interior clips ≈ replacement clips),
  electronics (camera/sensor mounts on vehicles).

This domain's shared capability gaps (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the
domain is their CLIENT, not their owner.
