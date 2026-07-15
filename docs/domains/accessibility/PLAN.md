# Accessibility / Adaptive Utility — domain plan

Statuses: ✅ implemented · 🔶 partial · ⬜ not started. Template canon —
[INDEX.md](../INDEX.md); commercial rules — [ECOSYSTEM.md](../../ECOSYSTEM.md).

## 1. Scope and positioning

Daily-living accessories that reduce everyday effort: thickened grips
for cutlery and tools, one-handed openers, button/switch
extenders, book/tablet holders, custom straps.
AF's value is at its maximum here: "one hand is not like another" is exactly
the case where a parametric fit for a specific person beats any
fixed STL. The domain is social-good and Free-centric by design.

Which claims the domain does NOT make (the boundary is hard, see
[medical/EXCLUDED.md](../medical/EXCLUDED.md)):

- NOT a medical device, NOT rehabilitation, NOT an assistive device in
  the regulatory sense, NOT orthopedic: no "treats", "corrects",
  "restores function", "patient-specific".
- NO long-term skin-contact claims and NO strength "for falls/supporting
  body weight" (grab bars, canes, lifts — out of scope forever).
- Does NOT claim food contact for cutlery grips by default (the
  food-safe metadata gap ⬜ — as in repair: an explicit material note).

The positioning formula: **a utilitarian grip that is comfortable to hold
in precisely your hand** — not therapy and not a medical device.

## 2. Mode / Environment / Tier

The domain = pack, NOT a new mode: the "body/contact/comfort" contract
already belongs to the Wearable mode; the rest is Utility/Engineering.

```text
mode:        Wearable (grip/hand contact) / Utility / Engineering
environment: household / desk (kitchen — with a material note)
tier:        Free-centric + Certified Free; Pro — narrow B2B (see §7)
```

## 3. What the engine already has — the reuse map

| Domain block | What builds it today | Status |
|---|---|---|
| Thickening grips (utensil handles) | `revolve_band` / `recipe_revolve` (body of revolution: outer grip profile + inner channel) | ✅ |
| Axial channel for the handle shaft | `axial_channel`, the `inset_plug` clearance chain as a fit exemplar | ✅ |
| Bow handles (doors, drawers, carrying) | `grab_handle_v1` (sweep arc) | ✅ |
| Soft contact zones | TPU pad lands (`clamp_half_lower/upper` — saddle with recesses), forearm_cuff TPU recesses | ✅ |
| All wearable mechanics | body_fit block on ProductInstance, MODE_PROFILES (wearable requires body_fit), P2 comfort_edge/donning/strap validators | ✅ |
| Skin protection | the `BODY_CONTACT_SURFACE` role (absolute region protection) | ✅ |
| Straps for hand/object | `add_strap_slots` (15–40 mm), the `strap_slot_pair` interface, `cord_slot_pair` | ✅ |
| Forearm mounting | `forearm_cuff_v1` + dovetail socket (wearable base for attachments) | ✅ |
| Levers/extenders — flat bodies | `rounded_plate`, `boss_pattern`, `pin_pair` | ✅ |
| body_fit region `hand`/`grip` | the body_fit vocabulary is extensible, but there are no hand/grip entries | ⬜ (AU-1) |
| Lever kinematics (openers) | no hinge/pivot op (E-stage) — AU-2 starts with monolithic levers | ⬜ |
| Grip texture (anti-slip) | texture op ⬜ (link to Bio-4M SDF) — for now ribs/grid fields via modifiers | 🔶 |
| Food-safe material metadata | no carrier exists | ⬜ |

## 4. Waves AU-1..3

### AU-1 — Grips ⬜

Golden: **`parametric_cutlery_grip_v1`** — a grip for a piece of cutlery
or a tool: an inner profile for the handle shaft (flat/oval/round,
via section parameters + a clearance band modeled on `inset_plug`), an
outer diameter for a specific person's hand. The wave's key work is
**extending the body_fit vocabulary with the `hand`/`grip` regions**
(`grip_d`, `hand_width`, optionally `finger_groove`): the outer Ø is taken
from body_fit, not out of thin air; the P2 comfort_edge validators are reused
on the edges as-is. Side-goldens on existing ops: pen/toothbrush grip (same
recipe, different preset), an enlarged-Ø bow door handle
(`grab_handle_v1` via a preset).

Closure criterion: the golden at grade A; the `hand/grip` region in body_fit
and engaged by MODE_PROFILES; `form.grip_diameter_window_ok` (§6) measures
the actual outer Ø against the body_fit window; contact edges are covered by
comfort_edge; the BODY_CONTACT_SURFACE role on the outer surface.

### AU-2 — Openers & Extenders ⬜

Lever geometry without moving parts: one-handed bottle/jar openers
(a monolithic lever + grip), turning keys for small knobs
(valves, keys, regulators), button/switch-key extenders.
Assembled from `rounded_plate` + `boss_pattern` + `revolve_band`
(gripping rings) + TPU pad lands in the object contact zone.
Golden candidate: `jar_opener_lever_v1`. The wave's validator is
`form.lever_reach_ok` (§6): the lever arm and the grip opening within the
band of the target object and hand force. Full hinged mechanisms — after
hinge ✅ shipped (`hinge_leaf`, `living_hinge_groove`); nothing blocks the wave.

### AU-3 — Straps & Supports ⬜

Book/tablet holders (desktop — reuse of the `phone_stand_v1` family),
custom object-holding straps on the hand/forearm: `add_strap_slots`
+ `strap_slot_pair` + optionally `forearm_cuff_socket_v1` as the wearable
base (the dovetail socket already handles swappable attachments — A1 swap
drivers). Criterion: one golden holder with a strap interface, P2 strap
validators green, the report free of therapeutic vocabulary (§8).

## 5. Domain interfaces and standards

**Grip Fit Standard** (modeled on the Cassette Interface Standard):

1. **Shared parameters** (the names are the contract): `handle_profile`
   (round/oval/flat), `handle_w`, `handle_t`, `grip_clearance`
   (band 0.2–0.6 — the shaft must both hold and come out for washing),
   `grip_d` (outer, from body_fit), `grip_l`.
2. **Frame keys**: `bore_axis_z`, `bore_entry_z`, `grip_od_k`,
   `pad_land_z` — published by the builder, measured by validators.
3. **Typed ports**: the shaft seat is the existing
   `cylindrical_payload_socket` (female, axis = shaft axis); straps —
   `strap_slot_pair`; the wearable base — `dovetail_rail` (the cuff socket,
   A1 swap harness reused). Wave AU-1 introduces no new port types.

## 6. Candidate validators

| Validator | What it measures |
|---|---|
| `form.grip_diameter_window_ok` | the actual outer Ø/grip section within the window from body_fit (`hand/grip`), along all of grip_l |
| `form.grip_bore_fit_ok` | the inner profile vs the declared shaft: clearance in band, depth ≥ k·handle_w |
| `form.lever_reach_ok` | the lever arm/grip opening within the target object's band (AU-2) |
| `form.comfort_edge_ok` (P2 reuse) | radii of all edges in the BODY_CONTACT_SURFACE zone |
| `form.body_contact_protected` (P2 reuse) | modifiers/features do not intrude into the contact region |
| `manufacturing.grip_orientation_declared` | print_orientation is set; layers not across the lever/arc bend |

## 7. Free / Pro boundary (the Printables test)

| Free / Certified Free | Pro |
|---|---|
| cutlery/pen/tool grips from your own measurements | — |
| openers, button extenders | — |
| holders with straps, singles | — |
| — | clinics/fablabs workflow: batch generation for a list of people, reports, versioning — **only after legal review** (§8) |

The domain is deliberately Free-centric: a social-good showcase and Certified
Free — reputational value above revenue. The only Pro candidate is a
workflow for occupational-therapy workshops/fablabs, and it is frozen ⬜
until a legal opinion that a B2B wrapper does not turn the product into a
medical one.

## 8. Risks and claims

- **Language is the main risk.** Reports and descriptions must not sound
  therapeutic: the forbidden vocabulary ("rehabilitation", "orthosis",
  "therapy", "patient", "correction", "assistive device") is pinned in a
  domain lint check of report texts; the allowed one — "easier to hold",
  "less effort", "for your hand".
- **Drift into medical**: any request "for a diagnosis/for a patient" is
  automatically [medical/EXCLUDED.md](../medical/EXCLUDED.md), no
  exceptions even for B2B.
- **Skin contact**: only BODY_CONTACT_SURFACE + comfort_edge;
  we make no long-term contact claims; TPU recesses are a recommendation.
- **Kitchen/food**: a "not food-safe by default" note in every cutlery-grip
  report until food-safe metadata ⬜ exists.
- **Lever strength**: AU-2 carries a material/orientation note; products
  that bear body weight are out of scope forever.

## 9. Connections

- **A1/A1.5 ✅**: `cylindrical_payload_socket`, `strap_slot_pair`,
  `dovetail_rail` + the swap harness — AU-3 cuff attachments reuse
  the cuff-adapter drivers as-is.
- **P2 (wearable) ✅**: body_fit, comfort/donning/strap validators,
  BODY_CONTACT_SURFACE, TPU recesses — the domain's core; AU-1 extends
  the body_fit vocabulary (`hand/grip`), not the mechanism.
- **A2 BOM ⬜**: straps/velcro as hardware items for AU-3.
- **E-stage ⬜**: hinge unlocks hinged openers (AU-2+);
  texture op ⬜ (Bio-4M SDF) — anti-slip grip.
- **PK line ⬜**: Certified Free criteria (PK-2) are the domain's target
  shelf; the Pro workflow — only with PK-3 + legal.
- **Neighboring domains**: repair (revolve fits, shared fit band),
  craft (grip texture = the same texture gap ⬜).

This domain's shared capability gaps (fit ladders, environment/material
gates, contact-safety vocabulary, text embossing, threads/hinge/slide, grid
standard) are centralized in [CAPABILITIES.md](../CAPABILITIES.md) — the
domain is their CLIENT, not their owner.
