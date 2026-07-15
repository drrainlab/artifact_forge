# Shared domain capabilities — the demand map

The domain plans exposed recurring capability gaps. This file is their
ONLY registry: a domain does not implement "its own little hinge" or its own
ladder validator — it becomes a client of the shared capability. The domain
map thereby turns from a set of plans into **a demand matrix for AF's
future capabilities**.

## The matrix: gap → client domains → owner wave

| Capability gap | Client domains | Owner wave |
|---|---|---|
| environment profile (carrier on the instance) | Mobility, Electronics, Pet, Repair, Craft | PK / E2 |
| manufacturing.material_env_ok | Mobility, Electronics, Repair, Pet | E2 |
| contact safety registry | Accessibility, Craft, Pet, Repair | PK / E2 |
| text embossing (G0) | Jigs, Repair, Education, Electronics, Studio | ✅ shipped (`text_emboss`, `svg_relief`) |
| threads | Repair, Electronics, Education | ✅ shipped (`threaded_plug_body`, `thread_internal_clearance`) |
| hinge / slide | Repair, Pet, Accessibility, Education | ✅ shipped (`hinge_leaf`, `living_hinge_groove`, `rail_slider_body`) |
| fit / gauge / tolerance ladder | Repair, Jigs, Education | shared Form |
| texture op | Craft, Accessibility, Biomorphic | Bio-4M / Form |
| seal / gasket continuity | Electronics, Pet-adjacent, VF-adjacent | Fluid/Seal |
| family / preset mechanism | Repair, Jigs, Electronics, Mobility, Pet | A4 (extends/family) |

## Centralized blocks

### 1. Fit / Gauge / Tolerance Ladder — one capability, three roles

Repair (fit workflow), Jigs (gauge / go-no-go), Education (lesson
object) want THE SAME ladder of fits:

```text
core capability: fit_ladder / tolerance_ladder / gauge_ladder
shared validators:
  form.ladder_steps_ok          — monotonicity and nominal of each step
  form.gauge_tolerance_ok       — go/no-go band
  form.fit_template_ladder_ok   — try-on workflow
domain roles:
  Repair    → fit workflow (measure the assembly → pick a step → part in band)
  Jigs      → workshop gauge / go-no-go probes
  Education → teaching object (feel the clearance band with your hands)
```

The rule: three domains do NOT create three similar validators with
different semantics — one core, different roles.

### 2. Environment & Material Profile Layer

Mobility ("PLA is not for the interior" must be a gate, not a note),
Electronics (outdoor/wet/high-heat, mains/IP warnings), Pet (wet/humid +
toxicity), Repair (appliance/high-heat), Craft (casting materials):

```text
environment profiles:
  indoor · outdoor · wet · humid · high_heat · vehicle · UV · vibration
material claims (defaults):
  not_food_safe_by_default · not_animal_safe_tested · not_IP_rated ·
  not_UL94 · not_high_heat_safe_with_PLA
shared validator:  manufacturing.material_env_ok
warning generator: report.environment_warning_block
```

The carrier is a future instance field (PK line, E2); until it appears,
the warnings live as text notes in reports, but the vocabulary is already
unified.

### 3. Contact Safety Claims Registry

Food-safe/toxicity/contact claims are scattered across Accessibility, Craft,
Repair, Pet — they get collected into one vocabulary (this is NOT a mode,
it's a shared claims/material registry):

```text
contact_kind:
  skin_short · skin_long · food · animal_water · aquarium · wet_general
default:
  no certified contact claim unless explicit tested profile exists
```

### 4. G0 — Label / Text Embossing

A small global building block with the broadest demand (Jigs — a
version/number blocker; Education — step labels; Repair — part numbers;
Electronics/Studio — enclosure marking; everywhere — "NOT FOR SAFETY USE"):

```text
G0 backlog:
  add_label() / add_embossed_text() / add_debossed_text()
  roles: version_tag · step_label · part_number · safety_label
```

### 5. Shared mechanics blocks — shipped (R2 core expansion)

Domains do NOT implement their own hinges/threads — the shared building
blocks landed with the R2 core-expansion wave and are now reusable:

```text
threads      → repair caps · electronics glands    ✅ threaded_plug_body /
                                                      thread_internal_clearance
hinge        → repair lids · accessibility openers ·
               education hinge lesson               ✅ hinge_leaf ·
                                                      living_hinge_groove
slide        → pet feeders · rail mechanisms        ✅ rail_slider_body (dovetail)
```

### 6. Seal / Wet / Leak — three different contracts on a shared topology

Validators may reuse the water topology, but the claims differ; Electronics
does NOT become Fluid/Grow (it's Engineering/Utility + wet environment):

```text
Fluid/Grow water path : water as the working medium — overflow, drain,
                        no orphan fluid ports
Electronics seal      : external rain/splashes — gasket continuity,
                        "rain-shielded, not rated", NO IP ratings
Pet wet               : wet zone + animal/toxicity warnings +
                        cleanability
```

### 7. Mounting Grid / Rail Standard

2020/grid/rail show up in Electronics, Mobility, Jigs, Studio, VF —
one system layer instead of "its own rails" in every domain:

```text
Mounting Grid / Rail Standard (owner: A4 Wall System):
  2020 profile · wall grid · workshop rail · camper/cargo rail ·
  fixture grid_pitch
```

## How to read this together with the plans

Every PLAN.md references this file in sections 3 (gaps ⬜) and 9
(connections); when a capability is implemented, the owner wave closes the
matrix row, and ALL client domains get it at once. The appearance of a new
shared gap in two or more domains = an obligation to add a row to this
matrix, not to implement it locally.
