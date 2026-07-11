# Geometry Builders — the canonical registry

The heart of the system. A well-chosen set of builders lets most new
archetypes be assembled from YAML/Recipe without new Python code.

```text
archetype = "what we make"          (product semantics, contract, invariants)
builder   = "how we build it"       (geometry + regions + frame + validators)
modifier  = "how we adapt locally"  (region-bound fields/interfaces on top)
style     = "which skin"            (controlled form passes, engineering untouched)
```

## The builder contract (non-negotiable)

A builder that merely builds geometry is useless. Every builder must
deliver all four:

1. **Geometry** — a contribution to the PartForm (profile/plate/feature), never direct CAD calls.
2. **Semantic regions** — so modifiers know where they may act, and keepouts are derived automatically.
3. **Frame keys** — the single source of truth: probes measure exactly the numbers the geometry was built from.
4. **Validators** — the names of the form/topology checks it signs off on.
   A named feature without validator-backed geometry = a hallucination → missing/engine_gap.

A recipe op with no engine implementation = an honest engine-gap WARN and
unbuildable — the same mechanism as for validators and applicators. New
builders are born as a draft/coding-agent task, never as arbitrary Python
at runtime.

## The four kinds of builders

- **base** — create the primary body (one per part): profile sections,
  plates, revolve, sweep, loft.
- **feature** — attach to the body: holes, pockets, bosses, cutouts.
- **field** — region-bound arrays = MODIFIERS (already structured that way;
  do not move them into the recipe layer, composition via keepouts is already solved).
- **interface/joint** — fits, snaps, hinges, connections.

---

## Registry (status as of 2026-07-03)

✅ = implemented · 🔶 = partially implemented / lives in another layer · ⬜ = planned

### base — primary bodies

| builder | status | where / wave |
|---|---|---|
| `section_extrude` | ✅ | core (PartForm.kind) |
| `profile_revolve` | ✅ | core; lamp_socket_cup — cups, bushings, washers, knobs |
| `revolve_band` | ✅ | recipe op: ring/bushing/washer/bracelet + cylindrical canvas for fields (finger_ring_v1, catalog/local) |
| `rounded_plate` | ✅ | profiles_plate.rounded_rect_loop + PlateFeature (adapter_plate) |
| `molded_side_hook_profile` | ✅ | flagship; + teardrop roof; + `tongue_side_hook` (sideprint) |
| `j_hook_profile` | ✅ | wall_hook / headphone_hook |
| `cable_comb_profile` | ✅ | cable_comb |
| `omega_anchor_profile` | ✅ | zip_tie_anchor |
| `device_slot_profile` | ✅ | phone_stand (slot = f(tilt), COM gate) |
| `open_c_channel_profile` | ✅ | cable_raceway_v1 (raceway_200): U-channel, constant section, wall is measured |
| `snap_c_clip_profile` | ✅ | snap_c_tongue (pipe_clip_v1_sideprint): arc retention + beam in the profile, sideprint |
| `cylindrical_cradle` | ✅ | first client: payload snap-C cuffs (mouth up, arc 210–268) inside `forearm_cuff_body` |
| `forearm_cuff_body` | ✅ | wearable P2: body_fit C-ring with a chordal mouth + strap tabs + TPU lands + payload snap-C, sideprint (profiles_wearable.py) |
| `device_cradle` | 🔶 | covered by device_slot_profile (parametric phone_stand) |
| `rounded_box_shell` | ✅ | recipe op: outer body + interior cut, form.shell_walls_ok |
| `sweep_profile_along_path` | ✅ | kind section_sweep: arc through 3 points + topology.bar_follows_arc (grab_handle_v1) |
| `loft_between_sections` | ✅ | rect→rect (LoftFeature/tapered_beam) + POLYGON sections (PolyLoftFeature, kind section_loft): additive body + subtractive cavities — superellipse_pot_body is the first client |
| `tapered_beam` | ✅ | LoftFeature (taper by construction) + topology.arm_reaches_tip (shelf_bracket_v1) |
| `truss_beam` | ✅ | truss_web_cutouts op: warren triangles, ligament = strut by construction (truss_beam_180) |
| `rail_slider_body` | ✅ | recipe op (R2.12): female dovetail shoe on the clamp-family rail — constant section sideprint, rail-parameterized, dovetail_rail female port |
| `hinge_leaf` | ✅ | recipe op (R2.11): plate + interleaved knuckle barrel + axial teardrop pin bore — side a/b mesh by construction; mode bolt = friction hinge via preload; printed-in-place refused (a fused pin is a broken hinge) |
| `hose_adapter_body` | ✅ | recipe op (promoted from showcase): barbed two-spigot revolve polyline + Spare Fit checks (recipe_ops_spare.py) |
| `knob_body` | ✅ | recipe op (promoted from showcase): revolved grip + blind square socket + optional lobed scallops (recipe_ops_spare.py) |
| `angle_bracket_body` | ✅ | recipe op: L-section + optional diagonal gusset web, holes in BOTH legs, side-profile print (recipe_ops_mount.py) |
| `spool_body` | ✅ | recipe op: H-profile flanged spool + axial bore (recipe_ops_revolve.py) |
| `pot_body` | ✅ | recipe op: tapered vessel + RAISED drainage floor over a foot ring; superellipse plan waits on loft (recipe_ops_revolve.py) |
| `net_pot_body` | ✅ | recipe op: thin tapered cup + hanging rim flange (recipe_ops_revolve.py) |
| `multi_socket_hub` | ✅ | recipe op: revolved connector hub the socket arms weld into (recipe_ops_connector.py) |
| `superellipse_pot_body` | ✅ | recipe op on the section_loft kernel: squircle vessel, raised drainage floor, MEASURED min wall (an offset superellipse is not a superellipse) |
| `tee_body` | ✅ | recipe op: barbed tube tee/cross/ELBOW — wraps hose_adapter_body (through) or builds a capped-run profile (elbow, form.tube_run_open); smooth X branch spigots rooted in the flange |

### feature — fasteners, pockets, cutouts

| builder | status | where / wave |
|---|---|---|
| `hole_pattern` (line/grid/bolt-circle) | ✅ | form/patterns.py + min_web/outline checks |
| `countersunk_hole_pattern` | ✅ | HoleFeature.countersink_face (a printing lesson: countersink on the bottom) |
| `counterbore_hole_pattern` | ✅ | HoleFeature.head_style=cylinder + recipe op (fastener_plate_v1) |
| `rounded_rect_cutout` | ✅ | recipe op (square corners in v1) |
| `port_cutout` (usb_c/audio/…) | ✅ | recipe op, typed PORT_SIZES table |
| `wire_exit` | ✅ | recipe op: drop-in U-notch in the shell rim (cable_junction_box_v1) |
| `nut_trap` | ✅ | recipe op: hex pocket (flat-to-flat!) above a clearance bore |
| `heatset_insert_pocket` | ✅ | recipe op from the fasteners heatset table |
| `boss_pattern` | ✅ | recipe op: 4 bosses + blind pilot bores, keepout in the floor layer |
| `standoff_pattern` | ✅ | recipe op: PCB standoffs on a plate + blind pilots |
| `lid_seat` | ✅ | inset_plug op + lid_seat joint: dimensional chain + pose probe (esp32_box_with_lid) |
| `bore_pattern` (line/grid/bolt-circle) | ✅ | recipe op: plain vertical bores, no screw semantics (drainage / finger holes / vents) |
| `square_post_sleeve` | ✅ | recipe op (R2.10): collar on a square post welded to a vessel wall — arc-front PolyLoft rides the taper, channel opens toward the vessel, teardrop set screw |
| `bin_dividers` | ✅ | recipe op: interior walls welded wall-to-wall + floor, cells measured (recipe_ops_organizer.py) |
| `finger_scoop` | ✅ | recipe op: rounded cove through a shell wall, open through the rim by construction |
| `stacking_lip` | ✅ | recipe op: inner-rim lip + bottom rebate plug — the classic stacking-box joint; lip_h bounded by floor_t |
| `flange_slot_pattern` | ✅ | recipe op: radial tie slots as rotated field polygons (probe measures true cell width, not bbox) |
| `grid_floor` | ✅ | recipe op: square through-mesh across a circular floor disc, open-area ratio measured |
| `wall_slot_ring` | ✅ | recipe op: vertical slot ring on a TAPERED wall via cylindrical field mapping (radial cutters overshoot the taper) |
| `cell_pocket_grid` | ✅ | recipe op: blind battery pockets (CELLS table) + retaining mouth lips + floor contact slots — the bearing-seat inset-span pattern |
| `peg_pattern` | ✅ | recipe op: board-standard pegs, L-hook = two axis-aligned pins, anti-lift row; `pegboard_peg` interface type (recipe_ops_pegboard.py) |
| `socket_arm` | ✅ | recipe op: blind rod socket on a hub, ±X/±Y/+Z only; barrel = PinFeature with declared `bore_d` (the tube-wall probe) |
| `text_emboss` | ✅ | recipe op: TextReliefFeature — glyphs from ONE bundled font (cad/text.py, DejaVu Sans), emboss/engrave, mirrored stamp duty, top/bottom faces; first `string` op param |
| `bushing_seat_line` | ✅ | recipe op (promoted from showcase): press-fit steel bushing seats, frame keys NAMESPACED per op id — several rows/diameters per guide, the fit check measures every row (recipe_ops_jig.py) |
| `stop_fence` | ✅ | recipe op (promoted from showcase): registration fence under a plate edge (recipe_ops_jig.py) |

### field — modifiers (already region-bound, composition via keepouts)

Window mappings: planar, tilted (inclined faces), **cylindrical_z_mapping_v1**
(the side wall of revolve bodies: Z axis, full 360°, a single explicit seam_keepout;
cells are built in the tangent plane and cut radially; support-free is a
measured `manufacturing.max_opening_span`, not a promise).

| builder | status |
|---|---|
| `honeycomb_field` | ✅ add_hex_perforation (flat-to-flat 30°, min_ligament is measured) |
| `grid_slot_field` | ✅ add_grid_slot_field |
| `voronoi_field` | ✅ add_voronoi_field (stable seed, Lloyd, Chaikin, ligament guaranteed) |
| `magnet_pocket_pattern` | ✅ add_magnet_pockets (blind, skin is verified) |
| `strap_slot_pair` | ✅ add_zip_tie_slots (zip ties ≤10mm) + add_strap_slots (straps 15–40mm, skin-guard; wearable P2) + strap_slot_pair_plate recipe op (plate slots + strap_center datum/port) |
| `rib_field` | ✅ add_ribs (additive, topology.ribs_present) |
| `phyllotaxis_field` | ✅ add_phyllotaxis_field (Vogel spiral, ligament by construction + measured) |
| `vein_rib_field` | ✅ | add_vein_ribs (standalone, seeded rhythm, additive) + biomorphic veins in style |
| `space_colonization_branching` | ⬜ R5 |

### style — not builders, a separate layer (settled)

`biomorphic_surface_deform` = SurfaceStyle biomorphic_utility_part (sliders →
controlled passes, preserve by construction). Do not mix with recipe.

### assembly joints (the assembly/joints.py registry — verified in pose)

| joint | status |
|---|---|
| `screw_joint` | ✅ R1: bolt circles coincide in pose, clear↔tap, axes void, interference |
| `lid_seat` | ✅ R2: the plug↔interior−2·clearance chain down to CAD + assembly.lid_seats in pose |
| `press_fit_pin_pair` | ✅ R2: PinFeature + interference contract (the pin is THICKER than the socket, overlap measured and bounded) |
| `split_plane_with_alignment` | ✅ in essence: butt_pin_joint (sections identical + end-face pins; PinFeature.axis) — raceway_400_split. An auto-generator from ONE instance = the next iteration's edit-intent |
| `snap_joint` | ✅ compliant: undercut + insertion strain 1.5·δ·t/L² ≤ 5% (esp32_box_snap_lid) |
| `dovetail_joint` | ✅ A1: undercut retention + clearance band + flank angle + full engagement; friction-only axial retention (declared) |

### interface / joint / mechanics

| builder | status / wave |
|---|---|
| `gusset_pair` | ✅ shelf_bracket_v1 (web gussets as ribs) |
| `snap_hook` / `snap_receiver` | ✅ | ops snap_hook_pair / snap_window_pair + snap_joint (the strain physics caught the first design: a 9mm beam was breaking) |
| `press_fit_pin_pair` | ✅ (see assembly joints) |
| `dovetail_joint` | ✅ A1: the cuff's socket crown + the adapters' male leg (forearm_cuff_body payload_mount=dovetail_socket / dovetail_adapter_body) |
| `split_plane_with_alignment` | ✅ (see assembly joints: butt_pin_joint) |
| `pin_hinge` | ⬜ R4 |
| `rail_slider` | ⬜ R5 |
| `living_hinge` | ⬜ R5 (material/fatigue — its own validators) |
| `thread_external` / `thread_internal_clearance` | ⬜ R5 |
| `bearing_seat` | ✅ recipe op (608/625/6001 table, the lip is probe-verified) |
| `shaft_coupler`, `ratchet_teeth`, `friction_hinge` | ⬜ |

---

## Implementation waves

- **R1 — Recipe kernel**: `form: {type: recipe}` in the archetype schema; a
  registry of recipe ops with fail-fast names at catalog load; promotion of
  already existing features into composable ops (`rounded_plate`, `hole_pattern`,
  `countersunk_hole_pattern`, `counterbore_hole_pattern`,
  `rounded_rect_cutout`); a demo archetype built ENTIRELY from YAML with no Python.
  Criterion: a new useful archetype (panel/grommet) is assembled as a recipe and
  passes the full honesty pipeline.
- **R2 — Enclosure core** ✅ COMPLETE (2026-07-03): shell/boss/port +
  lid_seat/standoff/nut_trap/heatset/wire_exit/counterbore; examples:
  esp32_box_base, esp32_box_with_lid (an assembly!), fastener_plate_demo,
  junction_box_60.
- **R3 — Maker profiles** ✅: snap_c_tongue (broom_clip_25mm) +
  open_c_channel (raceway_200). Remainder: cradles (generalization).
- **R4 — Strength & assembly** ✅ core: LoftFeature/tapered_beam +
  gusset webs (shelf_bracket_150). Remainder: sweep, joints/split_plane —
  waiting for the multi-part pipeline.
- **R5 — Wow & mechanics** ✅ core: bearing_seat + phyllotaxis_field
  (bearing_turntable_base). Remainder: threads, ratchet, branching,
  friction hinge.

## The honest remainder (deep mechanics — one iteration per item)

The wave leftovers are consolidated into a master plan: dovetail →
wave A1 (ports/interfaces), rail_slider and hinges/threads/ratchet →
later waves.

`dovetail`/`tongue_groove` and `rail_slider` are sliding fits (friction,
direction-of-travel tolerances); `pin_hinge` and `friction_hinge` are moving
assemblies (axis clearance, torque); `living_hinge` is material fatigue;
`thread_external/internal` is a helix sweep in OCC + a thread profile;
`shaft_coupler`, `ratchet_teeth` are torque transmission;
`space_colonization_branching` needs oriented additive geometry (diagonal
branches; Box3 ribs are not enough). Each of these has its own physics and
validators; a feature without them would be a hallucination, which is why they
are not "finished off" but planned as separate iterations on the completed
foundation (recipe + joints + pose probes).

Core-expansion wave (R2.x) deliberate deferrals — each is one bounded
iteration, none is a bug. R2.5 closed the S/M half of this ledger:

- ~~tube ELBOW config on `tee_body`~~ ✅ R2.5 — capped-run profile, the
  blind run bore provably swallows the branch junction (form.tube_run_open);
- ~~multiple bushing rows on one `drill_guide_v1`~~ ✅ R2.5 —
  bushing_seat_line frame keys namespaced by op id, `enabled` row toggle,
  the fit check discovers and measures every row;
- ~~interfaces for `pcb_tray_v1` / `strap_mount_base_v1`~~ ✅ R2.5 —
  boss_pattern publishes the boss-top datum (heatset_insert_pattern port);
  new `strap_slot_pair_plate` op publishes strap_center (strap_slot_pair port);
- ~~TPU pad recess + revolved press-fit body~~ ✅ R2.5 — `foot_body` op +
  furniture_foot_press_v1 (spigot presses INTO the tube, TPU disc recess);

R2.6–R2.9 closed the rest of the ledger:

- ~~SVG relief~~ ✅ R2.6 — svgelements (core dep), svg_relief op, TRUE
  narrowest-feature measurement (inward-normal ray casting), holes
  (nested subpaths) refused loudly until the hole-subtraction iteration;
- ~~rod_socket interface type~~ ✅ R2.7 — the "conditional declarations"
  blocker dissolved: interface.frame_exists already treats an OPTIONAL
  port with an absent datum as honestly un-built; trellis declares all
  four arm ports, tube_connector its hose branches;
- ~~superellipse plant pot~~ ✅ R2.8 — PolyLoftFeature + kind
  section_loft (additive body + subtractive cavities), min wall MEASURED
  (an offset superellipse is not a superellipse);
- ~~non-90° branches~~ ✅ R2.9 (bounded) — AngledPin/AngledBore
  (cylinders along an arbitrary unit vector) + path-based probes;
  angled_socket_arm banded to the printable 30–80° elevation. Still
  axis-aligned by contract: interface FRAMES (diagonal ports publish a
  datum, no port declaration) and barbs (a barb is a revolve).

## Print orientation — a cross-cutting concern

Every base builder must declare `print_orientation` (or honestly say
`as_modeled`), and the overhang validator must know about it. The lesson of
the sideprint clip: a constant extrusion with the profile on the bed = zero
overhangs by construction; this property is VERIFIED (`form.constant_section`),
not postulated.

## Interfaces (wave A1)

A connection = a DECLARED port: `interfaces:` on the archetype (id, type,
gender, datum, clearance, region, keepouts, accepts, assembly_role) drawn from
the registry of 11 types (`product/interfaces.py`). A joint implements a port
type; a mate is legal only with a matching type + complementary gender +
mutual accepts (`assembly/mates.py`); `forge compat` derives the catalog's
compatibility matrix; `assembly/swap.py` verifies a part swap
(interface.swap_part_builds). A builder that publishes a port must emit its
datum and the type's frame keys — `interface.frame_exists` measures this.
