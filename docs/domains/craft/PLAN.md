# Craft / Mold / Ceramics — domain plan

Statuses: ✅ implemented · 🔶 partial · ⬜ not started. Template canon —
[INDEX.md](../INDEX.md); commercial rules — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope and positioning

Parametric molds for casting and impressions: open molds (soap, plaster,
wax, decorative concrete), two-part molds with registration keys, stamps and
texture rollers for ceramics/polymer clay, templates/ribs for
pottery. What gets printed is not the product but the **tool** — the mold from
which the user casts the product. AF's value: draft angle, casting-material
shrinkage and demold clearances are measurable parameters with validators,
not "by eye" as in typical STL molds.

What claims this domain does NOT make:

- Does NOT claim food-safe by default: molds for chocolate/ice — only with
  an explicit disclaimer about material, FDM layering (pores = bacteria) and
  food-grade coating; no guarantees of food contact (food-safe
  metadata gap ⬜).
- Does NOT cover hot casting above the mold plastic's heat resistance (metal,
  high-temperature resins) — only plaster/silicone/wax/soap/concrete and
  similar cold/warm materials.
- Does NOT promise mold service life (abrasive materials eat PLA) —
  material notes only.

## 2. Mode / Environment / Tier

Domain = pack, NOT a new mode: molds are engineering parts under the regular
quality contract; there are no unique mode-level checks (draft/demold are
form.* validators, not a new contract).

```text
mode:        Engineering / Utility (per product)
environment: workshop (wet casting — WARN note, not a wet gate)
tier:        Free (open molds) + Pro (two-part, registration, casting profiles)
```

## 3. What the engine already has — reuse map

| Domain block | How it is built today | Status |
|---|---|---|
| Mold tub/trough | `rounded_box_shell` (walls + floor) | ✅ |
| Round/axisymmetric molds | `revolve_band` / `recipe_revolve` | ✅ |
| Half-molds seating into each other | `inset_plug` — plug↔interior fit with clearance chain: nearly ready-made mold registration | ✅ |
| Registration keys of the halves | `pin_pair` (butt_pin) — pin/socket with band fit | ✅ |
| Closing the halves | `edge_magnet_pockets` (dry sealed pockets, alignment-only) | ✅ |
| Bolting the halves together | hole/counterbore patterns + `nut_trap` | ✅ |
| Tub stiffening ribs (casting pressure) | rib modifiers, `truss_web_cutouts` | ✅ |
| Pour funnels/channels | `port_cutout`, `axial_channel` (vent/pour as channels) | 🔶 (funnel cone — via revolve parameters) |
| Draft angle in ops | no carrier for wall taper | ⬜ (VF-5 production readiness already planned draft angles — shared building block) |
| Texture (stamps/rollers) | texture op — direct link to the Bio-4M SDF engine | ⬜ (CR-3) |
| CASTING material profiles (shrinkage/viscosity) | no carrier; shrinkage is currently a shrinkage_pct parameter | ⬜ |
| Food-safe metadata | no carrier | ⬜ |

## 4. Waves CR-1..3

### CR-1 — Open Molds ⬜

Golden: **`parametric_soap_mold_v1`** — an open mold: cavity
(rectangular/oval, from `rounded_box_shell` + cavity subtraction),
**draft angle** on the cavity walls (new building block ⬜ — parameter
`draft_deg` 1–5°, implemented as taper of the subtracted body),
**shrinkage** via a `shrinkage_pct` scale parameter (the cavity grows by the
casting material's shrinkage), demold fillets on all internal edges
(removability + no stress concentrators in the cast piece). Side-goldens:
a round puck mold on `recipe_revolve`, an N-cell tray (cavity ×
pattern).

Closure criterion: golden at grade A; `form.draft_angle_ok` and
`form.demold_clearance_ok` (§6) actually measure taper and edges; the report
carries a "casting material → recommended shrinkage_pct" table (§5);
S/M/L variants from one YAML.

### CR-2 — Two-Part Molds ⬜

Half-molds with a parting plane: registration via `pin_pair`
(butt_pin_joint — pin↔socket fit already with band) and/or an
`inset_plug` rim (one half seats into the other via the clearance chain);
closing — `edge_magnet_pockets` or a screw tie
(counterbore + `nut_trap`). Pour funnel (cone via
`recipe_revolve`) and vent channels (`axial_channel` from the cavity's top
points to the parting plane). Golden candidate: `two_part_figure_mold_v1`
(axisymmetric cavity). Wave validators: `assembly.mold_halves_registered`
(keys coaxial, parting gap within band), `form.pour_vent_topology_ok`
(funnel at the top point, a vent from every local maximum of the cavity —
a relative of the water_report topology, just air instead of water).

### CR-3 — Stamps / Texture Rollers / Ceramics ⬜

Stamps and texture rollers: body — `rounded_plate` (stamp) or
`revolve_band` (roller, already supports bushings/handles), working surface —
**texture op ⬜**: direct link to the Bio-4M SDF engine (SDF fields already
generate organic relief in bio-skins — here the same relief becomes the
tool's working surface, an inverted impression).
Plus ceramic templates: profile ribs (`rounded_plate` + profile
cutout), wall-thickness gauges. The wave is blocked by the texture op — until
then only geometric textures (hex/grid/voronoi field modifiers ✅
as first-generation relief, 🔶).

## 5. Domain interfaces and standards

**Mold Registration Standard** (modeled on the Cassette Interface Standard):

1. **Shared parameters** (names are the contract): `cavity_l/w/d`,
   `draft_deg` (1–5), `shrinkage_pct`, `parting_clearance` (0.1–0.3),
   `key_d`, `key_count`, `wall_t`.
2. **Shrinkage convention** — shrinkage of the CASTING material, not the print
   (print compensation is owned by the slicer). Reference table in the report:

   | Casting material | shrinkage_pct (typical) |
   |---|---|
   | soap base | 0.5–1.0 |
   | plaster | 0.1–0.3 |
   | silicone (platinum) | 0.1–0.4 |
   | wax | 1.0–2.5 |
   | decorative concrete | 0.3–0.6 |

   The numbers are a recommendation with a "verify against the material
   datasheet" note; full casting material profiles — carrier ⬜ (Pro, §7).
3. **Frame keys**: `parting_plane_z`, `cavity_floor_z`, `key_*_xy`,
   `funnel_axis` — published by the builder, measured by validators.
4. **Typed ports**: registration keys are a reuse candidate for the
   `removable_insert` family (tool-free separation of the halves); a new
   `mold_registration` type is introduced only together with its mate validator ⬜.

## 6. Validator candidates

| Validator | What it measures |
|---|---|
| `form.draft_angle_ok` | actual taper of all cavity walls ≥ draft_deg along the demold direction (gap ⬜ — new building block, shared with VF-5 production readiness) |
| `form.demold_clearance_ok` | no undercuts against the demold direction; internal cavity edges filleted ≥ r_min |
| `form.mold_wall_ok` | tub wall withstands casting pressure: thickness/ribs derived from cavity_d (generalization of min_wall) |
| `form.pour_vent_topology_ok` | funnel at the top point of the parting plane; a vent from every local maximum of the cavity (CR-2) |
| `assembly.mold_halves_registered` | keys coaxial in pose (band), parting gap = parting_clearance, halves separate by vertical lift |
| `manufacturing.mold_surface_note` | note about working-surface layering (post-processing/coating) — honesty note, not a gate |

## 7. Free / Pro boundary (Printables test)

| Free / Certified Free | Pro |
|---|---|
| open molds (soap, plaster, cell tray) with draft + shrinkage | two-part molds: registration, funnels, vents, `assembly.*` report |
| single stamp with a geometric texture | casting material profiles (carrier ⬜): shrinkage/viscosity/vents from the profile |
| — | registration systems as a family (key/closure presets), texture libraries on top of the texture op ⬜ |

An open soap mold is easy to find ready-made — Free by test; parametric
two-part molds with verified registration and vent topology are what
an STL cannot replicate.

## 8. Risks and claims

- **Food-safe**: molds for chocolate/ice — only with the disclaimer "material
  and coating are the user's responsibility; FDM surface is porous";
  food-safe is not claimed by default (metadata gap ⬜). Certified for
  food molds is not issued until a carrier appears.
- **Casting chemistry**: exothermic resins/aggressive materials can warp
  the mold — a mold-material note (PETG vs PLA) in every report.
- **The draft validator is honest or absent**: until `form.draft_angle_ok` ⬜
  the draft_deg parameter is not advertised as "verified" — a feature without
  a measuring validator = a hallucination.
- **Shrinkage is a recommendation**: the §5 table is not a guarantee of cast
  dimensions; the report always carries a "verify against the material
  datasheet" note.
- **Abrasion/wear**: concrete and grog eat the mold — a service-life note.

## 9. Connections

- **A1/A1.5 ✅**: registration keys via existing joints
  (the `removable_insert` family as the halves' separation joint); the
  `mold_registration` type is a candidate for the port registry.
- **A2 BOM ⬜**: magnets/screws closing the halves as hardware items.
- **VF-5 production readiness**: draft_angle ⬜ — shared building block
  (VF planned draft for injection-molded cassette production; build it once,
  both reuse it).
- **Bio-4M ✅ / texture op ⬜**: the bio-skin SDF engine is a ready-made
  relief generator for CR-3; the texture op turns it into the tool's working
  surface.
- **PK line ⬜**: casting material profiles — pro content of the pack mechanism.
- **Neighboring domains**: repair (shared revolve/clearance fits),
  accessibility (shared texture gap), education (an open mold is the
  ideal teaching artifact: "the validator catches an undercut").

The shared capability gaps of this domain (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the domain
is their CLIENT, not their owner.
