# Music / Studio / Creator — domain plan (ST)

Domain expansion from [ECOSYSTEM.md](../../ECOSYSTEM.md) ("Future Domains
to Watch → Music / Studio / Creator Tools"). Template canon —
[INDEX.md](../INDEX.md).

## 1. Scope and positioning

The musician's/creator's workspace: audio-interface mounts, synth and
controller stands, patch-cable management, headphone hooks,
acoustics and LED channels. **The platform's cheapest showcase domain**: reuse
is nearly 100%, most products are pure YAML presets on existing
ops/archetypes, not a single new building block in the first wave.

**What claims this domain does NOT make:**

- no acoustic claims ("improves room sound" — spacers
  hold the panel, they do not certify RT60);
- no electrical safety (LED channels are mechanics, not electrics);
- no 19" rack-mount standard with load-bearing claims (desktop only).

## 2. Mode / Environment / Tier

Domain = pack, NOT a new mode: the musician's desk has no unique
validator contract — Utility/Engineering/Workshop suffice
(ECOSYSTEM: "Desk / Studio → domain / pack").

```text
mode:        Utility / Workshop / Engineering
environment: desk / studio
style:       retro-futurist / minimalist / cinematic
tier:        Free / Certified-centric; Pro is minimal
```

## 3. What the engine already has — reuse map

| Building block | Status | Reuse in the domain |
|---|---|---|
| `underdesk_cable_clip_v2/v3` (v3 sideprint) | ✅ | base of the ST-1 golden: the under-desk mount is the same family |
| `headphone_hook_v1` | ✅ | studio preset as is |
| `cable_comb_v1`, `cable_raceway_v1`, `cable_grommet_plate_v1`, `cable_junction_box_v1`, `zip_tie_anchor_v1` | ✅ | patch cables, desk cable routing |
| `phone_stand_v1` (device_slot = f(tilt), COM gate) | ✅ | generalization to controllers: MPC / MiniFreak — same slot mechanism and same `form.stability_footprint` |
| `adapter_plate_v1`, `fastener_plate_v1`, `standoff_pattern`, `boss_pattern` | ✅ | mounting plates for interfaces and small hardware |
| `enclosure_base_v1`/`enclosure_lid_v1` (+ `*_snap_v1`), `port_cutout` (usb_c/audio), `wire_exit` | ✅ | pedals, DI boxes, custom boxes |
| `wall_tool_ring_clamp_v1` / `wall_ring_mount` | ✅ | wall rings for microphones/headphones by Ø |
| `truss_beam_v1`, `shelf_bracket_v1` (loft + gussets) | ✅ | desktop risers ST-3 |
| Interfaces `screw_pattern`, `snap_joint`, `cable_pass`; `forge compat` | ✅ | typed ports and compatibility out of the box |
| hex/grid/voronoi modifiers, magnet pockets, Bio-4M bio-skins | ✅ | style showcase (retro-futurist panels) |
| Text embossing op (channel labels on combs) | ⬜ | nice-to-have, not a blocker |
| Style registry as a schema field | ⬜ | styles are still a document vocabulary (ECOSYSTEM canon) |

The domain creates NO capability gaps — that is its value as a showcase.

## 4. Waves ST-1..3

### ST-1 — Desk Audio Essentials ⬜

Golden artifact: **`underdesk_audio_interface_mount`** — a preset on
existing ops (rounded_plate + rounded_rect_cutout + screw/heatset +
cord_slot_pair) — **pure YAML, zero new Python**; dimensional presets
MiniFuse / Scarlett. Also in the wave: the `patch_cable_comb` preset
(cable_comb_v1, pitch sized for patch cables) and the headphone hook studio
preset.

Criterion: golden builds at grade A under two dimensional presets
(MiniFuse 2 / Scarlett 2i2) by swapping a single parameter block;
`form.device_slot_fit_ok` and manufacturing.* green; photo set for
the OS-7 gallery.

### ST-2 — Stands & Mic Line ⬜

Synth/controller stands: a generalization of `phone_stand_v1` —
device_slot = f(tilt) for MPC One / MiniFreak (device presets by mass
and dimensions); **the COM gate `form.stability_footprint` already exists** and
becomes the wave's main gate (a heavy controller on a tilted
stand is exactly its case). Plus mic cable clips (XLR clips on a stand —
the underdesk/pipe clip family).

### ST-3 — Room & Light ⬜

Acoustic panel spacers (adapter_plate + standoff_pattern; claims — see
§1), LED/neon strip channels (reuse of `cable_raceway_v1` — a channel is a
channel), desktop risers (`truss_beam_v1` / `shelf_bracket_v1` with
gussets). Retro-futurist style presets on top of the existing modifiers.

## 5. Domain interfaces and standards

**Desk Device Mount Standard** (modeled on the Cassette Interface Standard):

- shared parameters: `device_w/d/h`, `tilt_deg`, `lip_h`, `cable_gap`;
- frame keys: `slot_floor_n` (cradle normal), `cable_exit_*`;
- typed ports: `screw_pattern` (under-desk/wall mounting),
  `cable_pass` (cable exits — instances of the port declared in A1),
  `snap_joint` (removable box lids).

Device presets (MiniFuse, Scarlett, MPC, MiniFreak) are a data vocabulary
on top of the standard, not new archetypes: changing the device = changing the
preset.

## 6. Validator candidates

| Validator | Base | Status |
|---|---|---|
| `form.stability_footprint` | exists (phone_stand COM gate) | ✅ reused as is |
| `form.device_slot_fit_ok` | clearance-band mechanics of the interfaces | ✅ mechanics exist |
| `form.cable_comb_throat_ok` | tooth throat measurement vs cable Ø | ✅ mechanics exist |
| `manufacturing.min_wall` / `bed_fit` / `overhang` / `supportless` | exist | ✅ |
| `assembly.no_orphan_ports`, `interface.mate_frames_opposed` | exist | ✅ |

Everything exists or is assembled from what exists — the waves require no new
validator families.

## 7. Free / Pro boundary (Printables test)

The domain is **Free/Certified-centric**: nearly everything standalone is easy
to find on Printables — which makes it Free by rule. Pro is minimal:

| Free / Certified | Pro |
|---|---|
| interface mount, patch comb, headphone hook, single-device stand, LED channel | at most a **full studio kit**: a coordinated set (mount + combs + stands + risers) with a unified style, compat report and BOM |
| device presets one at a time | batch generation of a dimensional lineup for a print farm |

If the full kit does not accumulate added value, it honestly stays
Certified Free: the domain's role is not revenue (see §8–9).

## 8. Risks and claims

1. The main risk is zero: no body, no water, no transport, no loads beyond
   desktop. That is exactly why the domain is the ideal showcase.
2. Do not promise acoustics/electrics (see §1) — claims are fixed in PACK.md.
3. Stands with heavy controllers are the only risky mechanics:
   the COM gate is mandatory on every device preset (not just the golden).
4. The reputational risk: the showcase must be "boringly reliable" —
   Certified criteria (golden + print confirmation) with no exceptions.

## 9. Connections

- **Role in the ecosystem**: showcase of the CP registry and the OS-7 photo
  gallery; the author's audience — the domain serves trust and community, not
  revenue.
- **A1/A1.5 ✅** — screw/snap/cable_pass ports; `forge compat` on the studio
  kit. **A2 BOM ⬜** — screws/inserts in the build package for the kit variant.
- **PK line** — ST-1 is a candidate for the first pure-YAML pack (PK-1
  precedent "a pack without Python"); the PK-2 Certified criteria are trialed
  here.
- **CP line** — the exemplary community template: "make a preset for your
  device" = the ideal good first pack (OS-6).
- Neighboring domains: electronics (enclosures/DIN in more depth), education
  (a stand as a parametrization lesson), repair (equipment knobs/feet).

The shared capability gaps of this domain (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the domain
is their CLIENT, not their owner.
