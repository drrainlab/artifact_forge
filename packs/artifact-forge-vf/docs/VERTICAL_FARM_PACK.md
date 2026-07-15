# Vertical Farm Pack — section canon (tilted flush row)

> **DESIGN CORRECTION (2026-07-08).** The cascade architecture of VF-1..VF-4
> (slope inside the channel, ~7.9 mm steps between modules, drip-handover
> between modules) has been declared a **design mistake** for the target
> product and replaced by the **tilted_flush_row** canon described in this
> document. The cascade goldens were removed; the history lives in git
> (VF-3/VF-4 commits).

Modular vertical-farm elements for microgreens on coco substrate.
Golden artifacts: `water_rail_cell_2020_petg` (a cell made of three printable
parts) and `vertical_farm_row_3x1` (a full row: cap → 3 flush modules →
collector on two straight 2020 profiles, magnets enabled).

```
Base Water Rail        — transports and constrains water (never stores it)
Coco Cassette          — defines substrate-to-water contact
Snap Retainer Frame    — lightly holds the coco down without squeezing it
Inlet Cap / Collector  — water enters as a drip, exits into the drain tube
Straight 2020/3030     — CARRIES the row (reference hardware, cut to length)
```

## Section laws

1. **Transient pulse, storage forbidden.** Water is fed as a pulse, travels
   along the channel and leaves. Standing water anywhere is a contract FAIL
   (`closed_water_reservoir`, `dead_water_pocket` in `must_not_have`).
2. **The slope belongs to the MOUNT, not the geometry.** The channel has
   CONSTANT depth (`form.water_channel_constant_depth_ok`); the rail and the
   profiles are modeled horizontal; the whole row is mounted at 1.0–2.0°
   (default 1.5°) — this is machine-declared in the assembly's `mount_context`
   and verified by `assembly.row_drains_under_mount` (virtual heights
   v = z + y·tan(slope); no mount_context / band violated / row reversed →
   FAIL). A single cell is buildable horizontally but operational only when
   mounted — on the part this is an honest INFO note
   `form.drainage_requires_mount` (does not affect grade).
3. **Modules flush, joints lap-flow.** Adjacent modules sit in ONE plane
   (ΔZ = 0), end faces at a controlled `face_gap` of 0.3–0.6; row pitch =
   `module_w + face_gap`. Water handover is a lap joint: a lip continuing the
   FLOOR PLANE of the channel (lip top = floor level: higher — a dam, lower —
   a step) rests in a THROUGH, bottom-open cutout in the receiver's floor;
   a deliberate 0.5–2.5 mm slot remains at the lip tip.
4. **The seam is not a water path and not a sealant.** The main flow crosses
   the joint OVER THE TOP of the lip. Stray drops into the slot fall through
   open air — visible, cleanable, clear of aluminum/magnets/dry zones
   (`form.lap_slot_leak_path_controlled`). Sealed inter-module joints —
   **never** (anti-goal), including accidentally (slot < 0.5 — FAIL).
5. **Rail owns water; cassette owns agronomy.** New crops = new cassettes,
   the rail stays untouched (Cassette Interface Standard below).
6. **The profile carries, the plastic positions.** The rail is not a slab but
   a dry frame around a protected water core (lightweight dry shell,
   −40% plastic): large smooth windows, open from below, NOT honeycomb;
   the load-bearing function belongs to the standard STRAIGHT profile,
   seating is full (span gap 0 — a check, not a note).
7. **Magnets are alignment only.** Sealed dry pockets d6.4×2.4 in both ±Y
   faces (default off): not a sealant, not a support; no magnet face ever
   sees water (≥1.2 mm of plastic to any wet zone).
8. **Everything is brush-cleanable.** The channel is open to the sky, the lap
   cutout is through, the snap windows are through, the lightweight windows
   open downward — no hidden wet cavities (always-on manufacturing checks).
9. **A beautiful but engineering-wrong tray is a FAIL.** Every feature is
   verified by checks; strict mode stops the build.

## Water geometry (as built)

```
       cap (drip tower)                  lap joint (ΔZ = 0)                 collector
        │ FALL_ENTRY 2.5         lip 4×1.4, top = channel floor           catches the
        ▼                        ▼   slot 0.5–2.5 (open below)            last module's
   ┌──────────────┐  face_gap ┌──────────────┐          ┌──────────────┐    lip
   │ channel 16×5 │◄──0.4───► │ channel 16×5 │─── ... ─►│ channel 16×5 │──► tray→drain
   └──────────────┘           └──────────────┘          └──────────────┘
   ═══════════════════ straight 2020 profile, full seating ═══════════════════
                the whole row is mounted at 1.5° (mount_context)
```

- The channel is cut from the seat-pocket floor, depth `channel_d = 5` is
  CONSTANT; ≥ 2 mm of material below the floor (`channel_floor_margin`).
- Rail datums: `inlet`/`outlet` — on the floor plane, `face_gap/2` OUTSIDE
  the faces (the outlet-on-inlet mate yields ΔZ=0 and pitch `module_w +
  face_gap` by construction); `feed` — floor + FALL_ENTRY 2.5 (the ONLY drop
  in the row — the cap drips here); `drain_edge` — the bottom of the lip tip
  (the collector mates here; the 4 mm lip protrusion = the drip edge's air
  gap).
- Lap physics at ΔZ=0: any lip thickness ON the water path is either a dam
  (1.4 mm of head at 1.5° = a ~53 mm puddle) or a hidden pocket. Hence the
  lip continues the floor, and the receiver cutout is through (a sump is
  unrepresentable); modules are separated by a vertical lift (the cutout has
  no ceiling).

## Cassette Interface Standard (MVP-1.5)

Any future cassette (`sprout_mesh_cassette_v1`, `rockwool_cube_cassette_v1`,
`netpot_cassette_v1`, …) must:

1. **Share the shared parameters** (the names are a contract):
   `cassette_l`, `cassette_w`, `cassette_h`, `seat_clearance` (0.5–1.0),
   `module_pitch`. In the assembly example they are declared once — a desync
   is unrepresentable (`_inject_shared`).
2. **Publish the frame keys** (the machine half of the interface):
   `cassette_u0/v0/u1/v1`, `cassette_h`, `floor_bottom_z`,
   `window_cx/window_w/window_floor_z` + the shell keys for snap
   (`shell_wall`, `inner_u0/u1`). The rail publishes `seat_*` and `channel_*`.
3. **Pass the `removable_insert` joint** in pose: clearance within the band,
   tool-free rim, the window INSIDE the channel, reach 1–2 mm, a drainage gap
   ≥ 1 mm under the window. Removal under the mount slope is the same
   vertical lift (cos 2° ≈ 0.9994):
   `assembly.cassettes_removable_under_mount` — a rollup note.
4. **Pass the cassette checks**: `form.cassette_no_reservoir`,
   `form.no_secondary_water_channel`, `form.snap_pockets_cleanable`;
   `form.substrate_retained_under_mount` — an INFO note (coco at 1.0–2.0°
   is static; for future mat cassettes it will become a real check with a
   governor lip).

⚠️ The contact window is **narrower than the channel** (default 12 mm with a
16 channel): a window wider than the channel physically cannot drop into it.
Contact area is gained through window length along the flow (`window_l`).
The channel floor is flat — window reach is uniform along the whole length.

## Registry (recipe ops — form/recipe_ops_water.py)

| op | kind | what it does |
|---|---|---|
| `water_rail_body` | base | body + seat + CONSTANT-depth channel + corridors + 4 water datums + lightweight windows (param-gated, reversible) |
| `lap_outlet_lip` | feature | a lip continuing the floor past the front (−Y); the drain_edge datum |
| `lap_inlet_receiver` | feature | a through, bottom-open cutout in the inlet floor (+Y) |
| `edge_magnet_pockets` | feature | sealed dry pockets d6x2 in the ±Y faces (default off) |
| `profile_seat_slot` | feature | 2 bottom slots for 2020/3030 along the flow, dry |
| `tongue_groove_edges` | feature | tongue (+X) / groove (−X), positioning only |
| `substrate_tray_body` | base | the cassette shell (wall default 2.2 — a lightweight touch) |
| `contact_window` | feature | a slab under the bottom (drop 1–2 mm); BEFORE mesh_floor |
| `mesh_floor` | feature | a flat orthogonal through mesh |
| `lift_tabs` | feature | 2 finger recesses in the rim |
| `retainer_frame_body` / `frame_snap_hooks` | base/feature | the frame + 4 hooks |
| `inlet_cap_body` | base | the drip tower; mates `rail.feed` |
| `collector_endcap_body` | base | an L-shaped tray; the catch datum AT THE LIP TIP, mates `rail.drain_edge`; derived `hang_drop = seat_depth + channel_d + lip_t` |
| `profile_ref_body` | base | a STRAIGHT profile cut-to-length (slope 0 — the model is literally truthful), stations at the flush pitch |

Joints (`assembly/joints.py`): `removable_insert`, `tongue_groove`,
`snap_joint`, **`lap_flow_joint`** (flush handover: ΔZ=0 ±0.05, face_gap
0.3–0.6, lip 3–6 inside the cutout, slot 0.5–2.5, the receiver ≥ the giver
in width), `fluid_joint` (drip — ONLY at the adapters: cap→feed,
drain_edge→collector), `saddle_hang` (auxiliary verification),
`profile_perch` (local seating of the slot on the profile).

## mount_context (product/assembly.py)

```yaml
mount_context:
  type: tilted_flush_row
  slope_deg: 1.5          # schema 0–3; operational band 1.0–2.0 — by check
  slope_source: "whole row mounted on straight 2020 profiles at 1.5 deg"
```
`slope_axis: Y` / `slope_direction: inlet_to_outlet` are fixed as literals.
The CAD stays horizontal; non-90° poses do not exist. Row checks
(`assembly/carrier.py`) compute virtual heights and take the chain order
from the lap-joints (a→b), not from poses — a reversed row is caught.

## Row checks in global poses (assembly/carrier.py)

- `assembly.row_flush_aligned` — all modules in one plane (ΔZ ≤ 0.1),
  pitch `module_w + face_gap` (±0.3);
- `assembly.row_drains_under_mount` — a monotonic virtual descent of the
  floors from the first inlet to the last outlet under the declared mount;
- `assembly.profile_support_full_length` — every rail on EVERY straight
  profile, full seating, span gap 0 (a nonzero modeled profile slope → FAIL);
- `assembly.magnet_alignment_ok` — pockets of adjacent faces coaxial ±0.5
  (n/a-PASS without magnets);
- `assembly.cassettes_removable_under_mount` — a rollup of the insert
  verdicts.

## Regions / roles

- `transient_water_path` — the channel, lap_lip, lap_receiver, the contact
  window, spout_path, catch_tray.
- `substrate_support_mesh` — the mesh canvas.
- Lap cutouts lying inside declared water regions do NOT violate
  interface-keepout (keepout protects a port from DRY features and modifiers,
  not from the water system's own voids).
- The rest: seat/tongue/groove/profile/magnet pockets → `interface_keepout`;
  snap roots → `high_stress_region`; the dry back zone → `mounting_surface`.

## Reports

- `water_report.yaml`: the channel (slope 0, drop 0), lap_handover
  (lip/receiver/face_gap + "seam is not primary water path"), the `row:`
  block — kind `tilted_flush_row`, slope from mount_context, modules_flush /
  stair_step:false, total_virtual_drop_mm, handovers (lap_flow ×N−1 +
  drip ×2), standing_water_under_mount, lap_seam_leak: controlled +
  drips_clear_of, orphan_fluid_ports.
- `frame_report.yaml`: carrier (straight profiles cut-to-length, the MODEL's
  slope_deg 0), slope_source: physical_mount + slope_deg from mount_context,
  full_profile_seating: true, span_gap_mm: 0, stair_step: false.
- BOM (`assembly/bom.py`, derived-only): the profile — "standard straight,
  cut to length; mount the WHOLE row at {slope} deg"; magnets — "d6x2 …
  module alignment only … preferably coated/epoxy-protected"; the silicone
  tube from hose_port; no HardwareSpec (reserved for A2).

## Lightweight open skeleton (VF-4.1; generic modifier — a future wave)

- Windows are cut THROUGH the under-seat slab (open from below AND above —
  no bridges by construction): what remains is the perimeter frame, the
  channel spine, the profile bands and the 2.0 ribs — an open skeleton.
  The 220×220 cassette covers each opening and rests on the ring+ribs:
  `form.cassette_support_span_ok` (≥4 windows inside the seat footprint,
  the grid intact, worst span ≤ 45). Forbidden zones —
  `form.lightweight_windows_dry_ok`.
- NOT honeycomb: dirt/biofilm/salt — only large smooth cleanable windows.
- Reversible: `lightweight: false` → a solid slab (the smoke test keeps both
  variants). Savings on the default cell: 1068 → 588 cm³ (−45%).
- `lightweight_dry_shell_v1` as a reusable modifier — a separate wave
  (ROADMAP).

## Printability contract (VF-4.1)

- **Orientation is part of the contract**: printed instances declare
  `manufacturing.print_orientation: as_modeled` (= bottom down for VF);
  a mismatch with the builder's decision is a FAIL
  (`manufacturing.print_orientation_declared`).
- **Always-on**: `manufacturing.supportless_lightweight_windows_ok` — a slab
  probe ON THE SOLID above the ceiling of every bottom blind pocket
  (through → pass; bridge ≤25 → pass note; ≤35 → WARN; more → FAIL);
  `manufacturing.horizontal_bore_supportless` — a horizontal round bore
  > Ø8 without a teardrop roof → WARN.
- **Teardrop bore** (`BoreFeature.roof="teardrop"`): 45° chords to a peak
  d/2·√2 above the center — a self-supporting ceiling for a horizontal bore;
  the volume ⊃ the cylinder, all probes valid. The collector drain is
  teardrop.
- **Magnets are installable**: press-fit 0.1–0.3 diametral, from the DRY
  mating face (±Y faces only — a check rule), a drop of CA in a BOM note;
  frame_report prints `magnet_installation: {method: press_fit_dry_face,
  water_exposed: false, role: alignment_only}`.

## Collector = end receiver, U-frame, vertical drain (VF-4.1 + VF-4.2)

The collector does not "stand nearby" — it RECEIVES the final lip: capture
6–8 mm from the face (the lip tip ≥2 to the apron rim), cheeks lip_w/2+1.5
wrap the wet zone, mouth ≥ lip + 2×1.4, the apron is a low rim 2.4–3.5 above
the handover plane (NOT a wall: a blind coco-trapping slit is unrepresentable
— `form.receiver_open_top_cleanable`: an open top, continuity with the tray,
the drop's path = the brush's path). In pose:
`assembly.collector_captures_drain_edge` (the tip inside the volume),
`collector_mouth_envelopes_outlet_lip`, `collector_removable_by_hand`
(no ceiling above the captured lip within a 15 mm lift window). The joint is
still UNsealed: cleanable, tool-free.

**VF-4.2 robustness**: the tray hangs as a cantilever — it is carried by TWO
full side walls of the U-frame (thickness ≥3.5, from the tray bottom to the
arm, full length), not by thin posts; `form.collector_structure_sturdy`
closes the `min_wall` blind spot (it measured the `wall` parameter, not the
actual rib cross-sections). The drain goes **vertically down**: the bore is
drilled through a solid sump (the `drain_extension` widening, tube grip
`drain_grip` ≥12 mm), the push-in tube enters FROM BELOW and runs under the
row (port `drain_out`, normal −Z); `form.collector_tray_drains` is rewritten
for the vertical (floor→sump, the mouth at the lowest point, through
downward). There is no horizontal bore and no teardrop on the collector
anymore — `BoreFeature.roof="teardrop"` remains a kernel primitive, and the
always-on `horizontal_bore_supportless` guards future horizontal bores.

## Root chamber under the cassette (VF-5A) — param-gate `under_cassette`

`under_cassette: skeleton | root_chamber` — both modes of a single rail.
- **skeleton** (VF-4.1): through windows, −45% plastic, but top overflow
  drips down (see overflow_containment).
- **root_chamber** (VF-5A): under the cassette — a SOLID block with a
  **blind bottom** (z0..4 — overflow containment) and top-open **root
  troughs** (2 per side, level const-depth, depth 12). Roots grow down into
  the troughs; water drains **forward by the mount slope exactly like the
  main channel** — no geometry slope (`form.root_chamber_ok`: level,
  full-length, blind bottom ≥2, clear of the spine). Troughs of adjacent
  modules meet across the face_gap → a continuous drainage path along the
  row to the collector (`passive_root_drainage_return` — a legalized
  separate subsystem, excluded by `no_secondary_water_channel`; NOT a second
  pulse channel).
- **The collector** for root_chamber is a full-width tray (`tray_w` up to
  180): it catches the channel lip (center) + all root troughs across the
  module width (`assembly.collector_catches_root_drainage`; a narrow
  collector spills → FAIL). The arm sits above the rail (not above the
  mouth) — no redesign was needed.
- **Magnets** in root_chamber sit in the solid perimeter (x~84, offset up to
  90): at the default x60 the pocket landed in a trough (a wet zone) — the
  magnet checks honestly failed.
- **Cassette removal** (in the water report `cassette_removal`): clean before
  rooting / NOT mid-cycle (roots in the troughs) / end-cycle together with
  the harvest. For microgreens/lettuce/herbs this is the norm.
- Golden: `vertical_farm_row_3x1_root_chamber` (root_chamber rails, magnets
  x84, a full-width 160 mm collector — the walls pass under the x90 profile)
  — overflow_containment: contained.
- **Hex cells (closed cups with drainage slits) — VF-5B**, separately: the
  troughs (VF-5A) already give open drainable root zones; hex cells would
  add per-plant root separation at the cost of drainage slits.

## Endcap magnetic docking (VF-6) — `endcap_dock` / `dock_magnets`

The end adapters (the collector at the front, the inlet cap at the back)
magnet onto the row's terminal modules. The terminal module's end-face
inter-module magnets "hang idle" — but they cannot be reused directly: they
sit at x=±84, z=8 near the side edge, where the collector cheek is only
~6 mm (squeezed between the tray mouth and the x90 profile), and the cap
does not reach there at all (±32). The fork is resolved by a **vertical dock
at a shared x=±22**:

- **rail** (`endcap_dock: none|front|back|both`, op `endcap_dock_pockets`):
  a pair of Z-pockets opening **UP** in the top of the END wall (z=body_h),
  at x=±`dock_x` (22), inset `dock_inset` (7) from the face — in the dry
  perimeter, above the troughs (11.6 mm z-separation), supportless to print.
- **collector/cap** (`dock_magnets: true`): counterpart Z-pockets opening
  **DOWN** in the arm sole / saddle ceiling — exactly on the interface
  contact plane (arm ↔ wall top, world z=8). The shared x=±22: the collector
  takes it with its full-width arm (cheeks and profile are irrelevant), the
  cap (±32) freely.
- Magnet-to-magnet, alignment-only, press-fit, a dry face — the same canon
  as the inter-module ones.

Checks:
- `form.dock_pockets_dry` — the dock pockets are blind, vertical (axis Z),
  ≥1.2 to any wet zone, in the press band (rail + both adapters).
- `assembly.endcap_docks_to_rail` — an **honesty-closer**: the world
  positions of the adapter's and the rail's pockets must coincide in pose
  (worst offset ≤1.0); a magnet without a counterpart = FAIL ("no dock
  pocket" / "does not mate"). In the golden the offset = 0.00.

Golden: `vertical_farm_row_3x1_root_chamber` — rail_1 `endcap_dock: back`,
rail_3 `front`, rail_2 without a dock; cap + collector `dock_magnets: true`.

## Print-feedback pass (VF-7) — mesh, drain, dimensions

Three fixes from inspecting the printed parts in Bambu Studio:

- **The cassette mesh = a manifold STL.** The printed cassette came out with
  "16 non-manifold edges" and individual solid/fused cells. The BRep is
  VALID — it is the TESSELLATION that breaks: OCC BRepMesh on a single
  planar floor face with ~780 square holes drops part of it (finer than
  tolerance is WORSE: 16→157). The clean-tessellation threshold is ~450
  cells → the default cell **6→8 mm** (784→~440; coco holds in 8 mm). Plus a
  new **always-on `manufacturing.mesh_manifold`**: it tessellates the export
  mesh of a field part, **welds vertices by position** (OCC yields per-face
  output, vertices are duplicated on shared edges — the raw index is always
  "non-manifold"), counts edges with ≠2 faces → FAIL if the slicer would
  reject the STL. It catches exactly that defect (cell=6 fail, cell=8 pass);
  gated by `form.fields` (simple extrusions are trivially manifold). Listed
  in `substrate_mesh_floor.verified_by`.
- **The collector drains dry.** The drain sat AHEAD of the floor's lowest
  point → water stagnated at the back. Now the end of the sloped channel =
  the drain position (the lowest point coincides with the drain, nothing
  deeper behind it), slope 1.5→2.5° — the tray empties
  (`collector_tray_drains`: "empties out the bottom").
- **Dimensions for the P1S.** The rail printed at 251.6×252 on a 256 bed →
  "too close to exclusion". The default module **248→205** (print ~209,
  ~23 mm margin to 256 on each side), cassette 220→177, pitch 250→207,
  profile 780→640. The resize squeezes the perimeter: the fixed 20 mm
  aluminum profile + the side wall of the full-width collector eat half the
  width → troughs `trough_w` 26→18, module magnets move BEYOND the profile
  (`magnet_x_offset` ~95, band up to 106), collector `tray_w` 160→120.
  **A ~200 mm module is the design floor**: below it the collector no longer
  fits between the troughs and the profile without changing the scheme. The
  root_chamber golden is retuned; the base VF goldens are pinned at 248
  (fixtures). Cassette Interface Standard: mesh nominal ~207.
- **The cap prints without supports** (VF-7c). As-modeled, the saddle opens
  DOWNWARD — a wide bridge, the outer lip hangs ("floating cantilever" in
  Bambu; the engine's `manufacturing.overhang` does NOT catch this — a blind
  spot: the IR check does not model the saddle's bridge ceiling). A new
  print orientation **`saddle_up`** (`orient_for_print`, a 180° flip around
  X, baked ONLY into export — the part frame and all validators untouched):
  the saddle becomes an UPWARD recess (a clean pocket, no bridge), the spout
  an ascending rib, the drip tower's flat top rests on the bed. The
  `inlet_cap_body` op sets the orientation itself; the row goldens declare
  it on the cap. Support-free is justified by geometry; final confirmation
  happens in the slicer (the engine does not verify the saddle bridge).

## Drain screen basket + maintenance layer (VF-8)

The row recirculates: the collector drain → (external reservoir + pump) →
the next row's inlet cap. Coco crumbs and root fragments in the drain water
clog the pump/tubes and dirty the next row. The solution is a **removable
filter basket in the collector sump above the drain** (pull it out, rinse,
put it back): one printed part, no extra plumbing, plus a machine-derived
maintenance report.

The honest outcome (NOT "clean water"): **debris-reduced water** — the
screen removes coarse coco crumbs and root fragments, fine coco dust may
pass; a clog is visible IN THE OPEN (the collector tray fills up in plain
sight, no hidden back-up).

**Fail-safe semantics (three modes, resolving the no-bypass ↔ overflow
conflict):**
- `normal_no_bypass` — MANDATORY: all water headed to the drain goes through
  the mesh/slots, the basket flange sits in the seat recess and blocks the
  side annulus — there is no way around the seat.
- `emergency_visible_overflow` — MANDATORY: a clog shows as a rising level
  in the OPEN collector tray; there is no hidden back-up volume.
- `emergency_unfiltered_bypass` — **OFF by default**, explicit opt-in only.
  By default the basket rim stands ABOVE the tray's overflow path → a clog
  spills the open tray in plain sight and NEVER overtops the basket toward
  the drain (debris goes no further). Lowering the rim below the overflow is
  possible ONLY via `allow_emergency_bypass: true` on the joint — and then
  the report flags it.

**Geometry = LOWERED SUMP + RADIAL FUNNEL (VF-8.1, a pivot driven by the
user's feedback: "not a screen across the channel but a drain bucket in a
well").** A new kernel primitive **`FunnelCutFeature`** — the first floor
sloped in X AND Y at once (`ChannelCutFeature` can slope only in Y): a
downward-converging (optionally skewed — different top/bottom centers)
frustum, subtracted with a ruled loft (cad/bores.py `cut_funnel`, the same
mechanism as the channel's). The collector (param-gated `screen_seat`): the
tray floor converges as a FUNNEL to a central well from ALL sides, the drain
sits at the ABSOLUTE lowest point of the well, a compact removable bucket
basket sits IN the well above the drain — **water falls INTO the basket
rather than hitting a wall**. The drain moves from the back wall to the tray
center (`y_drain` is centered in the arm-clear zone, `drain_extension` is
added), the funnel is skewed (the throat at the drain, the bell opened
forward over the tray) — it drains the whole floor. Plus a vertical
**shaft** (throat→rim) opens the roof above the well so the basket can drop
in and a brush can reach (it is drained by the funnel+bore below). Off by
default → existing collectors are byte-for-byte untouched.

**The basket** is a compact sink-filter cup (`substrate_tray_body`→
`lift_tabs`→`screen_wall_slots`): a fine 2 mm bottom mesh + wide vertical
slots in ALL 4 walls (a shallow pan in a shallow tray gives little bottom
mesh — the walls carry the main filter area). Invariants: **open area
≥ ~300 mm²** (≈4× the Ø9.4 drain bore; actual ~334) — the screen does not
choke the flow; **debris reservoir ≥ 3 ml** (actual ~3.3). Its own
`screen_wall` (NOT the shared `wall`) — the row's thick rail walls do not
thicken the little cup.

**Verification axes (VF-8.1):**
- form: `collector_sump_is_lowest_point` (the well below the tray floor, the
  bore from its bottom), `tray_floor_slopes_to_sump` (the funnel converges
  to the drain from all sides), `basket_not_transverse_flow_barrier` (the
  bell wider than the throat + recessed → water falls inside, the tray is
  not blocked), `no_standing_water_before_screen` (a monotonic descent to
  the drain), `screen_open_area_ratio_ok`, `screen_debris_capacity_ok`;
- assembly (the `drop_in_screen` joint IR check): `screen_normal_no_bypass`
  (the basket covers the drain, mesh-only, anti-shift, tool-free, the rim
  above the overflow — otherwise FAIL without `allow_emergency_bypass`),
  `drain_inside_screen_footprint` (the drain within the basket footprint in
  pose), `screen_removable_from_sump` (the rim raised, a straight pull);
- reuse of `manufacturing.mesh_manifold`, `topology.single_connected_solid`,
  `form.lift_access_ok`.

**Maintenance report.** `water_report._row_water(...)` gained a
`maintenance` block (drain_screen: "rinse", honest_note "DEBRIS-REDUCED
water"; collector/channel/tubes/cassette — per the parts present;
`all_tool_free`, `service_interval_hint: grow-test`). Lines appear only for
parts actually present.

**Pump topology (a doc note, not geometry):** `collector drain --(gravity)-->
reservoir --(pump)--> inlet cap`. NOT "the pump sucks directly through the
basket" — direct suction clogs the screen faster, pulls air and drags debris
onto the mesh. The screen guards the gravity path to the reservoir; the pump
draws from the settled reservoir.

**Mate = a DATUM, not a port.** The basket↔well joint goes through the
`screen_seat`/`seat` datums + `drop_in_screen` + honesty via
`assembly.screen_normal_no_bypass` (the `saddle_hang`/`hose_port`
precedent), without an interface port: a female port of the well (+Z) under
the skewed geometry has no clean outward normal, and the INTERFACE_TYPES
registry is frozen at the 11 A1 types. **CAD acceptance** (strict
`forge build` catches what pre-CAD validate misses — closed by the cheap
`test_root_chamber_row_builds_strict`): the brush reaches the whole channel
run (`brush_access` — the shaft opens the roof above the back half of the
well); `no_standing_water` does not flag the well (the through vertical bore
drains it, the `_pocket_drained_by_through_bore` exemption);
`no_interference` pass (the basket drops into the open well, no collision);
the well mouth = the basket's OUTER + 2·clr (the 0.75 gap in band). A
justified evolution of the first VF-8 (a corner drain → a central
funnel-well), which along the way eliminated the "basket in a blind corner"
class of problems.

Golden: `vertical_farm_row_3x1_root_chamber` — the collector
`screen_seat: true`, part `screen` (`drain_screen_v1`), joint
`drop_in_screen`. The honest remainder: an external pre-filter for the
reservoir/pump (plumbing); a round skirt slot-mesh (needs cylindrical
"slots"); a two-stage coarse+fine screen (not chosen); the exact cell size
vs clogging rate — grow-test (agronomy is not verifiable by CAD).

## Universal rail — floored lip-seat receiver, no through holes under water (VF-9)

VF-8 made `rail_1` special (`inlet_mode: capped`) — a crutch for two
symptoms of ONE problem: the through, bottom-open `lap_in_lap_receiver`
under the channel. It (1) forced the cap to feed a special capped rail and
(2) left a downward-open hole right under the water at EVERY rail↔rail
joint — "it will leak out", not a "controlled leak". The root is the very
idea of a through receiver (so that a solid bottom would not make a dam at
ΔZ=0).

The inversion (VF-9): the rail is again **UNIVERSAL**, and the receiver is a
top-open **FLOORED lip-seat**: the pocket is lowered exactly
`lip_t + clearance` below the channel floor, with a **solid bottom**. The
neighbor's lip sits in it, `lip top = channel floor` — a continuous water
surface (no dam), while there is **no hole downward**. The same floored
pocket also catches the cap's drip (it does not fall through) — so `rail_1`
stops being special, and the cap no longer has to deliver water inboard.

- `_lap_inlet_receiver`: `pocket_floor = channel_floor − (lip_t +
  lip_clearance)` (default 1.4 + 0.3 = 1.7 mm), the pocket z from
  `pocket_floor` to `floor+0.2` — shallow (depth ≤ 2.2, exempt in
  `no_standing_water_ir`). It publishes `lap_pocket_floor_z`,
  `lap_pocket_depth`. No `inlet_mode`/`inlet_capped`.
- `check_lap_joint_geometry_ok` / `lap_slot_leak_path_controlled` are
  rewritten: the receiver MUST be floored (`z0 > 0.05`, floor =
  `lap_pocket_floor_z`); there is no open path downward, only the top
  tip-slot at the joint is open.
- New form checks: **`lap_receiver_has_floor`** (a solid bottom),
  **`lap_receiver_residual_volume_ok`** (this is a lip-SEAT, depth ≤ 2 mm,
  not a reservoir — reports `lap_receiver_residual_volume_mm3`),
  **`rail_universal_inlet_accepts_cap_and_lap`** (one floored inlet catches
  both the drip and the lip).
- **The `manufacturing.no_through_holes_in_wet_lap_zone` invariant**
  (always-on): no cutbox with an open bottom (`z0 ≤ 0.05`) may sit under an
  active water path (regions `water_channel`/`lap_receiver`/`lap_lip`),
  EXCEPT the sanctioned collector drain. PASS after the floored fix; FAIL if
  the through receiver is brought back.
- Assembly checks: **`assembly.lap_joint_no_external_downward_leak`** (the
  lap_flow joint — the receiver is closed from below) and
  **`assembly.cap_drip_lands_in_channel_safe_floor`** (cap↔rail.feed — the
  drip lands on a channel-safe floor, not into a through hole), both in
  `row_water_chain.verified_by`.
- Goldens: `inlet_mode: capped` removed from `rail_1` — all rails are
  identical.

Row architecture: `a universal rail (floored receiver + outlet lip, no wet
through holes) → lap handover with no external downward leak → collector =
the only intentional drain downward`. CAD probe (rail_2): under the feed
column there is now solid material (was 0.00 through); the shallow seat
groove above, a solid bottom below.

## Support-free L-hook cap (VF-9 Part B)

The old cap printed only via the `saddle_up` flip: as-modeled, the saddle
ceiling is a flat bridge over ~14 mm with a hanging outer lip ("floating
cantilever", Bambu flags it; the engine's `manufacturing.overhang` did NOT
catch this — the VF-7c blind spot). Part B's goal — print AS-MODELED,
without a flip.

The geometric discovery: **a two-sided straddle across a ~13 mm wall cannot
be printed support-free** — above the wall's gap (the wall itself is absent
when the part is printed) the shoulder's inner lip always hangs; a gable
above the z=8 plane does not help (a ceiling at z=8 is still over air). The
only support-free options are a one-sided hook or reorient/flip. The
solution (user-approved): a **compact one-sided L-hook + face dock**:
- A short rest ledge (**hook_reach ~3.5 mm**, `HOOK_LEDGE_BAND`) rests on
  the OUTER edge of the wall top; the outer leg/foot holds the +Y face and
  reaches the bed. The ledge is a 4.4 mm one-sided overhang (printable),
  NOT a 14 mm cantilever.
- A **nose column** above the channel (`|x|<nose/2`) reaches the bed,
  carries the vertical bore (a straight drain, cleaned from above) and
  serves as the inner anchor of the roof above the channel (a bridge, not a
  cantilever); it extends ~10 mm inward — solid walls on both sides of the
  bore (otherwise the hollow post is not a "rib" for
  `topology.ribs_present`).
- The protruding spout plate is removed; `print_orientation: as_modeled`,
  the flip is deleted.
- **The magnetic dock moved from the wall top to the vertical +Y face**
  (Y-axis pockets): a dock on the wall top would need a ~7 mm inboard ledge
  (an un-printable overhang), while a vertical face prints cleanly. The VF-6
  rail amendment: `endcap_dock_style: top|face` (top = Z-pockets in the wall
  top, collector; face = Y-pockets in the end face, cap). `dock_drop` — a
  shared drop from the wall top so that the cap and the rail meet at the
  same world z. `_endcap_dock` (carrier) and `check_dock_pockets_dry` handle
  both axes.
- `saddle_hang_ir` gained a hook branch (gated by `hang_mode`): it verifies
  the ledge reach (`HOOK_LEDGE_BAND`, ≤ the wall thickness), the leg gap at
  the face, the seating on the wall top; the collector remains straddle
  (unchanged). The hook **does not depend on the wall thickness** (it grips
  the outer edge) — a thickness mismatch is no longer a failure mode.
- A new always-on **`manufacturing.cap_supportless_verified`** (closes
  VF-7c): the ledge overhang ≤ `CAP_ROOF_OVERHANG_MAX=5` AND the nose
  reaches the bed; the old flat 14 mm cantilever → FAIL.

CAD acceptance: flush_smoke (cap without a dock) AND root_chamber (cap with
a face dock) — both strict PASS, no_interference/ribs_present/single_solid/
overhang/cap_supportless_verified green. A corbelled L-hook (a two-sided
capture+nose) and a gabled roof remain a possible evolution after a physical
print.

## Chute-cap (VF-9.2) — a visible water path, a stop for the tube

On the assembled `out/` the user saw that the cap's bore reads as a "through
tunnel": a constant Ø9.4 over the full height — the tube can be pushed all
the way THROUGH (there is no stop), and the shape does not explain the water
path. The rule (locked in by a validator): **the cap must not contain a
closed horizontal water tunnel — the water path is visible to the eye**.
Variant B (user-approved): the **chute-cap**.

The water path: `tube → a vertical SOCKET with a STOP SHOULDER (blind
bottom, Ø tube+0.4, depth 12) → a narrow DRIP ORIFICE Ø5 through the stop →
a short covered CHAMBER (a fall shaft ≤10 mm along Y) → a TOP-OPEN spout
chute (a U-trough: floor + 2 wall ribs) → the drip from the tip lands on the
floored lip-seat, DRIP_INSET = 4.5 mm INSIDE the channel` — from there the
water is carried by the channel itself under the row slope. The chute's flat
floor drains by the mount slope (like the rail channel — the canon).

- The through Ø9.4 bore and the monolithic nose are REMOVED; the roof above
  the chute is cut open "to the sky" (a sky slot) — the path is
  brush-cleanable from above and visible.
- **A paired datum shift**: the rail's `feed` and the cap's `spout` both at
  −DRIP_INSET — the row pose is byte-for-byte, the datums honestly mark the
  real drip point.
- Checks: `hose_bore_ok` (the socket MUST be blind — a through socket
  without a stop = FAIL; the orifice 4..tube−2, coaxial, meets the socket
  bottom); `spout_drop_path_ok` (floor + both walls, the tip = the spout
  datum, width within the channel budget); the **new
  `form.cap_water_path_visible`** (chamber ≤10 mm, the sky opening reaching
  the top, no horizontal bores in the wet zone); `no_standing_water_ir` —
  an exemption "a blind bore is drained by a coaxial orifice below" (a
  plugged socket without an orifice remains FAIL);
  **`topology.fluid_path_open` is rewritten** — the cap is probed with ONE
  composite polyline (socket→orifice→chamber→along the chute→past the
  edge), never demanding a void below the stop; the **new assembly
  `cap_chute_drains_under_mount`** — virtual heights of both chute ends IN
  THE POSE of the mounted row (the slope carries water to the spout; without
  mount_context — an honest FAIL).
- The archetype invariant: `orifice_d <= tube_od - 2` (the stop is real).
- Gotcha: ribs are welded AFTER the cuts and in list order — the chute floor
  (z<0) must be welded AFTER the legs/walls (otherwise WeldError
  "2 solids"); U-legs around the chamber (a solid foot would fill it back
  in).

## Overflow honesty (VF-4.2, before VF-5 Root Chamber)

Nominally water leaves through the contact window into the channel. But with
top watering the EXCESS drips down through the through skeleton under the
slope — there is no containment. This is EXPLICIT in the water report:
`overflow_containment {status: absent, path: drains_through_skeleton,
user_action: keep a tray under the row, planned_fix: VF-5 root_chamber}`.
The full solution is the VF-5 root chamber (a blind bottom + cells + a
passive drain return to the collector).

## Printing (PETG prototype notes)

- All printable parts print flat, without supports; the wet path faces up.
- The ceilings of the lightweight windows are ~37–43 mm bridges: the slicer
  builds them, sagging in a dry invisible zone is acceptable; the check
  reports span > 45 as a note.
- Bed 250×250 for the 248 module (`manufacturing.bed_fit`).
- PETG for the prototype; food-grade PP — MVP-5. Magnets preferably
  coated/epoxy-sealed (BOM note).

## CAD acceptance (two-level)

- In the suite: `vertical_farm_flush_smoke` (cap + 2 rails with ONE real
  lap seam + cassette + collector + 1 profile) — the lap geometry is real on
  solids (no_interference, a through cutout), the reports are written; plus
  a single-part rail smoke (mass with lightweight on/off, the lip/cutout/
  pockets by probes).
- The full row: `uv run forge build
  catalog/examples/vertical_farm/vertical_farm_row_3x1.yaml`.

## Honest remainder

- **VF-4.2**: anti-slide retention of the row on the profile MOUNTED at a
  slope (clips/stops) — the seating is full, but there is no longitudinal
  lock;
- `lightweight_dry_shell_v1` — a generic lightweighting modifier;
- `dry_endcap_v1`; `vertical_farm_shelf_row_v1` (MVP-4); VF-5 Cassette
  Family;
- sealed inter-module joints — **never** (anti-goal);
- CFD — never in v1; verification is a sampled centerline + probe geometry;
- section/exploded renders — a shared output layer, not a pack concern.

## History: the superseded cascade (VF-3/VF-4)

The cascade (a 1.25° slope in the channel, an inlet datum with FALL_ENTRY,
7.91 mm steps, a chamfered 1.827° profile surrogate, span_gap 7.91 of
upstream-edge contact) was implemented and verified in the VF-3/VF-4
commits — if archaeology is ever needed, it is in git. What survived the
cascade: the `fluid_joint` mechanism (drip at the adapters), FALL_ENTRY
(only the `feed` datum), process:reference, saddle_hang, profile_perch and
the whole Cassette Interface Standard.
