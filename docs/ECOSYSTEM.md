# Artifact Forge — ecosystem: open-core, packs, modes

The canon of the platform's commercial, licensing and pack model. The
technical master plan is [ROADMAP.md](ROADMAP.md); this document answers
"what is open, what is sold and why" without changing a line of code.

The formula:

```text
AF = open-source parametric manufacturing engine
     + certified product packs
     + honest validators
     + product modes
     + future Web Studio
```

The market formula: **a parametric app store for useful 3D-printable
objects**. What monetizes is not the act of generating an STL but the
catalog, pack quality, validators, golden examples, reports, a
comfortable UI, the Web Studio, print-farm/B2B workflow, premium styles
and custom archetype development.

**The trust thesis**: open validators, golden tests and honesty reports
prove that AF is not a prompt-to-STL toy. Examples of contracts that are
already measured rather than postulated: `min_wall`, keepouts,
`no_orphan_ports`, `mate_frames_opposed`, water path + overflow honesty,
BOM, print notes, donning window / body-contact for wearable, and
"functional core owns safety; skin owns style" for biomorphic.

---

## The five axes of the ecosystem

The system does not sprawl across markets (`household_mode`, `auto_mode`,
`garden_mode`…) — instead, five orthogonal axes:

```text
Modes        = verification (what makes the artifact dangerous/complex and how to validate it).
Packs        = product/commercial packaging (who it is sold to).
Environments = operating conditions (household, vehicle, wet, high-heat…).
Styles       = the visual language (biomorphic, minimalist, cinematic…).
Tiers        = free / certified / pro.
```

One pack may contain artifacts of different modes; every artifact
explicitly knows its mode.

**The prime rule for creating a mode:**

```text
A new market ≠ a new mode.
A new validator contract = a new mode.
```

Applying the rule:

| Direction | What it is | Why |
|---|---|---|
| Household / Home | domain / pack | no unique checks — Utility/Engineering suffice |
| Desk / Studio | domain / pack | same |
| Auto / Vehicle | environment profile; possibly a mode later | for now: base mode + warnings (heat/vibration/visibility/airbag); a separate Mobility mode ONLY once the corresponding validators exist |
| Garden | domain | no contract of its own |
| Plant / Grow | **mode** | water/light/plants/maintenance — its own contract |
| Workshop | **mode** | loads/wall/tooling |
| Wearable | **mode** | body/straps/comfort/donning |
| Eyewear | **sub-mode of Wearable** | face/bridge/lenses/temples — its own constraints |
| Cinema / Prop | **mode** | props/actor-fit/visual continuity |
| Biomorphic | **overlay** | changes the form, does not own the function |

The compact final list of modes:

```text
Core validation mode:   1. Engineering
Product modes:          2. Utility   3. Workshop/Load-bearing   4. Fluid/Grow
                        5. Wearable/Body-fit   6. Eyewear/Face-fit (a sub-mode
                        of Wearable, split out for its complexity)   7. Cinema/Prop
Cross-cutting overlay:  8. Biomorphic/Bioform (a style overlay, not a market)
```

Environment Profiles (the starting vocabulary): household, desk/studio,
vehicle, outdoor, garden, wet/humid, high-heat, child-visible (but NOT
child-safe unless tested). Style Overlays: biomorphic, minimalist,
retro-futurist, industrial, cinematic.

Combination examples:

```text
household cable organizer: mode Utility · env household/desk · style minimalist
car phone cable clip:      mode Utility · env vehicle/high-heat/vibration
vertical farm cassette:    mode Fluid/Grow · env indoor/wet · style functional
parametric glasses:        mode Eyewear · env wearable/face-fit · style minimalist|cinematic
alien wrist computer:      mode Cinema/Prop · secondary Wearable · style Biomorphic
biomorphic tool holder:    mode Workshop · env workshop · style Biomorphic
```

In this iteration Environments and Styles are a DOCUMENT vocabulary, not
schema fields; the technical carriers (an environment profile on the
instance, extending the style registry) are future waves (see the PK
line, honestly ⬜).

---

## Mode Contract Matrix

| Mode | Meaning | Quality contract | Commercial angle | Status |
|---|---|---|---|---|
| Engineering | AF's baseline engineering rigor | dimensions, min_wall, ports, frames, keepouts, printability | the foundation of every pack | ✅ |
| Utility | useful household parts | clips, hooks, organizers, screw zones | Free Starter / the showcase | ✅ |
| Workshop | the workshop and its tools | heavy-duty, wall mounts, ribs, screw patterns, tolerance presets | Workshop Pro | 🔶 |
| Grow / VF | plants, water, phytolamps | water path, collector, rail, carrier, BOM, overflow honesty | free bundled flagship (the VF pack); future advanced grow families may be Pro | ✅/🔶 |
| Wearable | body, straps, cuffs; sub-modes: Body-mounted utility / **Eyewear (face-fit)** / Costume-prop | body_fit, donning window, strap slots, contact zones, face-fit dims for eyewear, no medical claims | Starter/Pro, cosplay/outdoor/maker; **Eyewear Generator Pro — the flagship** | 🔶 |
| Cinema / Prop | props | visual continuity, safe props, modular assembly, actor-fit | Prop Studio / Cinema Pro | ⬜ |
| Biomorphic | the organic style | functional core owns safety; skin owns style; keepouts protected | premium style layer / Bioform Pro | 🔶 |

Clarifications: Engineering is not a separate domain but the baseline
rigor every other mode builds on. Biomorphic is a cross-cutting style
overlay, not a market of its own. Eyewear is a sub-mode of Wearable,
split out because it carries its own validator contract.
Household/Auto/Garden do not appear in the matrix — they are
domains/environments: their artifacts live in
Utility/Engineering/Workshop with environment tags.

---

## The layered open-core model

| Layer | Model | Current code / status |
|---|---|---|
| Core engine | open source | `core/`, `form/`, `product/`, `catalog/`, `validators/`, `compiler/`, `cad/`, `assembly/`, `repair/`, `review/`, `cli.py` — the entire honesty pipeline |
| Basic builders / ops | open source | `form/profiles_*`, `recipe_ops.py`, the base archetypes |
| Free packs | open / free | a showcase of genuinely useful artifacts — includes the complete **Vertical Farm pack** |
| Certified packs | curated | `maturity=production_buildable` + golden tests + print confirmation |
| Pro packs | paid | archetypes + parameters + validators + golden examples + reports + families |
| Cockpit web | open / local / debug | an engineering visual debugger, not a consumer studio |
| Web Studio | paid / future | accounts, presets, exports, ordering, private catalogs |
| B2B / custom / print-farm | paid / future | outside the core repository |

**Pro packs exist only where there is substantial engineering,
parametric or manufacturing added value.**

**The Printables test** for the Free/Pro boundary:

```text
If a comparable object is easy to find on Printables/MakerWorld
and AF adds no substantial parametrization/validation —
it is Free or Certified Free, not Pro.
```

The paid-pack formula:

```text
Paid pack ≠ paid STL.

Paid pack = archetypes + parameters + validators + golden examples
          + reports + BOM/print notes + supported families + updates.
```

---

## Architecture readiness

Every row verifiably corresponds to the code (the honesty canon extends
to the business document too).

### Already there

| Capability | Status | Where / comment |
|---|---|---|
| Multi-source catalog loader | ✅ | `catalog/loader.py`: builtin + `catalog/local/`, `Catalog.origins` (id→source), fail-fast on id collisions |
| Pure-YAML packs | ✅ | recipe archetypes reference ops by registry name — a Python-free pack is possible today |
| Python-pack precedent | ✅ | the VF pattern: water recipe ops + water checks auto-register |
| VF as a structural pack | ✅ | its own canon doc (VERTICAL_FARM_PACK.md), its own ops/checks, archetypes, examples, tests, reports (water/carrier/frame/BOM) — **now bundled as a free pack** |
| Pack manifests (`pack.yaml`) | ✅ | id/name/tier/license/version/author; feeds the cockpit catalog facets |
| Packs as a catalog source | ✅ | packs register through the `artifact_forge_ng.packs` entry point and contribute archetypes/examples/ops/checks/joints |
| Plugin discovery | ✅ | `importlib.metadata` entry points, deterministic load order |
| Maturity ladder | 🔶 | draft→production_buildable on ArchetypeSpec — informational, not enforced anywhere; a ready certification gate |
| Cockpit separable from core | ✅ | the `[web]` extra; imports only web→core |
| Ports/frames as the load-bearing standard | ✅ | after A1/A1.5 — the backbone of the Certified compatibility narrative |

### Still missing

| Capability | Status | Comment |
|---|---|---|
| license / author notices in reports & BOM | ⬜ | pack.yaml carries the metadata; surfacing it in honesty reports / BOM / build packages is future work |
| entitlement | ⬜ | ONLY a cloud layer, never core |
| pack tier enforcement | ⬜ | tier is presentation metadata today; a future PK wave |

---

## Pack structure (the VF precedent)

```text
packs/<name>/
  README.md          # what the pack is
  pack.yaml          # manifest (id, name, tier, license, version, author)
  data/
    archetypes/
    examples/
  src/               # its own recipe ops / checks / joints (if needed)
  tests/
  docs/              # the pack's canon doc
```

The real manifest of the bundled VF pack:

```yaml
id: artifact-forge-vf
name: Artifact Forge Vertical Farm Pack
tier: free
license: Apache-2.0
version: 0.1.0
author: Artifact Forge
```

---

## Product Map by mode

Free is everywhere WIDER than a "crippled demo" — it is a genuinely
useful showcase. The summary Free/Paid boundary:

| Direction | Free | Paid |
|---|---|---|
| Utility | almost everything basic | large families / batch / commercial workflow |
| Workshop | simple holders/brackets | heavy-duty families, BOM, anchors, tolerance presets |
| Grow / VF | **the complete Vertical Farm system (bundled pack)** | future advanced grow families / B2B grow systems |
| Wearable | simple cuffs/straps | body-fit families, eyewear, complex mounts |
| Eyewear | demo frame / fit-test template | the parametric frame generator |
| Cinema / Prop | simple panels/greebles | continuity packs, actor-fit, production workflow |
| Biomorphic | demo style | premium bioform/exoskeleton skins |
| B2B | none | private catalogs, custom archetypes |

### Utility Starter on the engineering core

Engineering is the foundational validation mode; Utility is the product
mode on top of it. The free showcase: cable clip, wall hanger, cable
comb, zip-tie anchor, grommet, phone stand, small tray, pipe clip, screw
flange, adapter plates, pegboard/Skådis/2020 adapters. Its role: prove
usefulness and parametrization as the key difference from STL
marketplaces. Tier: Free Starter + a Certified Free subset.

### Workshop Starter / Pro

Starter: simple tool holders, wall hooks, pipe/hose clips, shelf
brackets, pegboard/2020 adapters. Pro: heavy-duty wall mounts, tool
families, handle/screw/anchor presets, tolerance presets,
ribs/buttresses, BOM, print-orientation reports. Modes: Engineering +
Workshop. Audience: workshops, garages, DIY, print farms.

### Grow / Vertical Farm — the bundled flagship pack (free)

Contents: water rails, cassettes (coco/sprout/…), collector, caps,
frame/carrier, inlet/outlet adapters, hose mounts, phytolamp brackets,
sensor mounts. It was built to pro-pack quality — dedicated reports
(water path, carrier/frame report, BOM), its own pack structure
(ops/checks/tests/doc), an engineering SYSTEM rather than a lone part —
and ships **free, bundled with the core**, as both the proof of the pack
mechanism and the flagship demonstration of what an AF pack is. Domain
risks: water, overflow, maintenance, leaks, roots, light/electricity.
The principle: **VF never promises more than it verifies; overflow
honesty is part of the product, not a defect**. Future advanced grow
families and B2B grow systems may become a separate Pro line.

### Wearable / Face-fit Mode

Three sub-modes: Body-mounted utility / Eyewear (face-fit frames) /
Costume-prop wearable. Positioning: maker / outdoor / workshop /
cosplay. NOT medical, NOT orthopedic, NOT safety-critical PPE.

Free: basic forearm cuff, simple strap mount, flashlight mount, basic
action-cam adapter, simple costume cuff, basic eyewear frame template +
measurement guide (non-prescription/costume).

Pro: body-fit cuff families, modular wrist/forearm device platforms,
advanced strap routing, TPU pad systems, left/right mirrored sizing,
the Eyewear Generator (below), sizing presets, comfort/contact reports.

The wearable-mode contract: contact zones protected, donning/removal
window, strap path valid, no sharp edges on contact zones, no medical /
orthopedic / certified eye-protection claims, no prescription/optical
correctness claims unless externally validated.

### Eyewear — the commercial flagship

A dual representation: in the Mode Contract Matrix, Eyewear is a
SUB-MODE of Wearable (one family of validator contracts); in the Product
Map it gets its own subsection with its own Free/Paid boundary, because
the frame generator is a standalone paid flagship.

```text
Eyewear Free:
  basic frame template · measurement guide · simple non-prescription/costume frame

Eyewear Pro (parametric face-fit generator):
  face width · bridge width · lens width/height · temple length ·
  pantoscopic angle · nose pads · hinge blocks · rim thickness ·
  lens groove · screw/insert options · left/right symmetry ·
  style families · print orientation · printable fit-test strips ·
  multi-size export · commercial frame output license
```

Why it is paid: not "one frame" but a family system — hard to replicate
with ordinary STLs, passes the Printables test. Lenses, prescriptions,
certification and eye protection are out of scope — separate and
handled cautiously.

### Cinema / Prop — honestly ⬜

A future line (wave P4), not current readiness. Possible contents:
sci-fi panels, greebles, fake vents, prop devices, wrist computers,
modular masks, creature costume plates, control panels, safe
non-functional props. The prop-mode contract: visual continuity,
multi-part assembly, actor-fit, non-functional safety, no real weapon
functionality, print/sand/paint workflow, scale variants. Bridges from
the current architecture: dovetail adapters, cuffs, biomorphic modifiers.

### Biomorphic — the premium style layer

"Biomorphic never breaks function": the functional core owns
safety/function, the biomorphic skin owns style/adaptation. Contents:
biomorphic shells, exoskeleton ribs, bone/vein/tendon fields, organic
buttresses, branch clamps, lamp brackets, mask/cuff shells,
creature/prop surfaces. The commercial boundary is legally and
technically clean:

```text
Free core function:  bracket / clamp / cuff / holder.
Paid premium style:  biomorphic skin / exoskeleton / creature language /
                     cinematic detailing.
```

Functional zones, screw zones, channels, body-contact, ports and
keepouts do NOT belong to the style layer — the style layer must respect
them.

---

## The Free / Certified / Pro ladder

| Tier | Meaning | What is inside |
|---|---|---|
| Free | growth, trust, community | useful starter packs + the bundled VF flagship |
| Certified Free | the quality showcase | maturity + golden + print confirmation |
| Pro | the paid catalog | families, reports, BOM, advanced validators, updates |
| Studio | the paid web product | UI, cloud preview, presets, project saving, ordering |
| Business | B2B / custom | private catalogs, API, white-label, print-farm |

The paid flagships:

```text
1. Eyewear Generator Pro
2. Workshop Heavy-Duty Families
3. Wearable Body-Fit Utility Pro
4. Biomorphic Premium Style Layer
5. Cinema/Prop Studio Workflow
6. Advanced Grow Families / B2B grow systems (beyond the free VF pack)
7. B2B / private catalogs / custom archetypes
```

## Studio licenses

| License | For whom | Capabilities |
|---|---|---|
| Indie Maker | personal use | Pro packs personal, cloud exports |
| Print Farm | small-scale production | commercial output license, batch generation |
| Prop Studio | film/music-video/cosplay | prop packs, continuity, actor-fit variants |
| Education / FabLab | teaching | classes, local presets, free/certified packs |
| B2B Custom | companies | private archetypes, custom validators, API |

---

## Licenses

### Core license — Apache-2.0 (decided)

The core engine ships under **Apache-2.0** ([LICENSE](../LICENSE)) — the
column that won on maker-community trust, vendor integration and
contributor friction. The bundled free packs (showcase, Vertical Farm)
are Apache-2.0 as well. The criteria the decision was weighed against
stay recorded:

| Criterion | Apache-2.0 | AGPL-3.0 | BSL / FSL |
|---|---|---|---|
| maker-community trust | high | medium/high | contested |
| integration by printer vendors | high | lower | lower |
| protection from cloud clones | low | high | high |
| contributor friction | low | higher | higher |
| compatibility with the pack business | high | high | medium |
| ease of understanding | high | medium | lower |

### Code license ≠ generated model license

```text
Generated outputs belong to the user,
subject to the license of the pack/archetype used.
```

For Pro packs:

```text
Personal license:   print for yourself · gift · home/workshop ·
                    no mass sale of physical prints.
Commercial license: sell prints · print farm · made-to-order
                    production · you may NOT resell the
                    pack/archetype/source data itself.
```

### The license carrier in the architecture — 🔶 (PK-1/PK-3)

`pack.yaml` already carries `license`, `author`, `tier`, `version`.
Still missing: per-archetype `usage_rights` and surfacing the notices on
ArchetypeSpec, ProductInstance, honesty_report, BOM, build package and
the Web Studio export.

---

## The PK line — Pack Economy

### PK-1 — Pack Mechanism v1 — ✅ (shipped)

Packs are a first-class source: the `artifact_forge_ng.packs` entry
point registers ops/checks/joints and contributes archetypes and
examples; `pack.yaml` manifests (id/tier/license/author) feed the
cockpit; origin=`pack:<id>`; the VF system extracted into
`packs/artifact-forge-vf/` with its own tests — and bundled as a free
pack. Remaining from the original scope: license/author notices inside
reports/BOM (moved to PK-3).

### PK-2 — Free Starters + Certified Criteria

Utility / Workshop / Wearable Starter, Bioform Demo. Certified criteria:
maturity=production_buildable, golden examples, passing validators,
print confirmation, documented material/orientation, an honesty report
with no hidden warnings. A repo-boundary map before publication.

### PK-3 — Commercial Layer — ⬜

Personal/commercial marking, build-package notices, Pro metadata,
commercial output / print-farm license. **No DRM in core** — entitlement
lives only in the cloud/Web Studio.

### PK-4 — Web Studio — ⬜

Accounts, presets, saved projects, cloud preview, guided configuration,
exports, order-a-print, private catalogs, B2B/white-label. The boundary:
**Cockpit = the open local engineering debugger; Web Studio = the paid
consumer/pro product.**

---

## Community Operating Model

The pack structure, tiers and the PK line answer "what"; this section
answers "how": who publishes a pack, how it gets reviewed, who owns
safety, how it becomes Certified, how disputes are resolved and how the
ecosystem avoids turning into a junkyard.

### The CP line — Community Packs (all waves ⬜)

```text
CP-1 Community Pack Template   — a pack template + the PACK_AUTHORING guide
CP-2 Community Registry        — a registry/index of community packs
CP-3 Certification Review      — the review process toward Certified
CP-4 Maintainer / Governance   — maintainers, disputes, blocking
```

### The community-pack lifecycle

```text
community_draft → community_validated → community_featured →
certified_free → official_pack

side states: deprecated · blocked
```

Relation to maturity: pack states are the catalog status of the
PACKAGING; `maturity` on an archetype is the status of the artifact
itself. A pack in `community_featured` may contain archetypes of mixed
maturity; `certified_free` requires production_buildable across the
board.

**The prime rule:**

```text
Community pack can be useful without being certified.
Certified pack must be boringly reliable.
```

The community experiments freely; the Certified badge goes only to what
passed the validators, golden examples, print confirmation and carries
honest warnings — the same criteria as Certified Free.

### Pack Trust Badges

Not "pretty badges" but a short packaging of the honesty report:

```text
validated · printed · multi-printer-tested · supportless ·
commercial-output-ready · wet-safe-tested · body-contact-reviewed ·
vehicle-environment-warning · no-medical-claims
```

Every badge must reduce to measurable checks/confirmations — a badge
without a validator-backed basis does not exist (the same canon as for
features).

### Contributor economy — a reserved seat

Not implemented now, but recorded so the path "a person with a YAML →
the author of a certified/pro pack" never has to be explained after the
fact:

```text
author · license · donation link · commercial upgrade path ·
official certification request · revenue share for Pro/Studio
(if a marketplace appears)
```

### Open-source launch checklist

Before the repository goes public:

```text
OS-1 License decision        OS-5 SECURITY.md / safety policy
OS-2 Repo cleanup            OS-6 Good first packs
OS-3 CONTRIBUTING.md         OS-7 Example gallery
OS-4 PACK_AUTHORING.md       OS-8 Public roadmap
```

The principle: publish not "just code" but "how to make packs" from day
one. Market context: Printables already has free/paid mechanics and
brand/community scenarios (official brand profiles, replacement parts,
accessories, cosplay props, a paid Store) — an ecosystem without a clear
authoring path loses to them by default.

---

## Future Domains to Watch

The additive-manufacturing market keeps growing ($30.6B in 2025 → $37.6B
in 2026 → a projected $168.9B by 2033, Grand View Research; drivers —
on-demand production, mass customization, rapid prototyping, digital
manufacturing). AF is therefore sold not as "another model site" but as
parametric infrastructure for custom parts and small production
workflows.

The domains below do NOT become modes (the five-axes rule: a new market
≠ a new mode) — they are domains/packs on top of the existing modes and
environment profiles.

```text
Future Domains to Watch:
- Repair / Spare Parts / Right-to-Repair
- Manufacturing Aids / Jigs / Fixtures
- Electronics / IoT / Smart Home
- Accessibility / Adaptive Utility
- Mobility / Bike / Vehicle Accessories
- Music / Studio / Creator Tools
- Craft / Mold / Ceramics
- Pet / Aquarium / Terrarium
- Education / FabLab
- Medical/Dental — explicitly out of public scope until certification
  path exists
```

Detailed domain plans: [docs/domains/INDEX.md](domains/INDEX.md).

### Repair / Spare Parts / Right-to-Repair

Plan: [domains/repair/PLAN.md](domains/repair/PLAN.md).

Possibly the most important missing domain. The EU is codifying the
consumer's right to demand repair of technically repairable goods
(washing machines, vacuum cleaners, phones — within a reasonable time
and at a reasonable price); Philips is already piloting a model of
printing replacement/accessory parts through Printables with an emphasis
on material, print orientation and safety/quality standards.

```text
Repair Pack / Replacement Parts Pack
mode: Engineering / Utility / Workshop
environment: household / appliance / high-heat / wet
tier: Free + Certified + B2B/OEM
```

Examples: handles, latches, lids, guides, housing clips, appliance feet,
hose adapters, filter holders, replacement knobs, appliance-specific fit
templates. This is a domain/pack, not a new mode.

### Jigs / Fixtures / Production Aids

Plan: [domains/jigs/PLAN.md](domains/jigs/PLAN.md).

The strongest B2B direction: the manufacturing market treats AM as a
production resource (digital twins for legacy equipment, reverse
engineering, on-demand replacement components, production tooling,
assembly/inspection fixtures, visual management aids).

```text
Manufacturing Aids Pack
mode: Engineering / Workshop
tier: Business / Pro
```

Examples: drilling jigs, soldering/assembly fixtures, inspection gauges,
spacer templates, alignment blocks, repeatable cutting guides,
small-batch fixtures. Companies care about repeatability, reports,
labels, BOM, material and versioning — exactly what AF does with
validators.

### Electronics / IoT / Smart Home

Plan: [domains/electronics/PLAN.md](domains/electronics/PLAN.md).

```text
Electronics / IoT Pack
mode: Engineering / Utility
environment: indoor / outdoor / wet / high-heat
```

Examples: ESP32/Arduino/Raspberry Pi enclosures, sensor mounts, cable
glands, DIN-rail adapters, wall boxes, camera mounts, LED channels,
ventilation grilles, snap-fit enclosures. Paid only for genuinely good
families: ventilation, multiple boards, cable entries, DIN/2020/wall,
print notes.

### Accessibility / Adaptive Utility

Plan: [domains/accessibility/PLAN.md](domains/accessibility/PLAN.md).

Promising, but phrased cautiously: NOT medical, NOT rehabilitation, NOT
a certified assistive device without external validation.

```text
Adaptive Utility Pack
mode: Wearable / Utility / Engineering
claims: daily-living accessory, no medical claims
```

Examples: thickened handles, cutlery holders, one-hand opening aids,
grip adapters, switch/button extenders, book/phone/tablet supports,
custom straps. A social-good direction: much of it should be
Free/Certified Free; Pro — for clinics/fablabs only after the legal
groundwork.

### Mobility / Bike / Vehicle Accessories

Plan: [domains/mobility/PLAN.md](domains/mobility/PLAN.md).

Auto remains an environment profile, not a mode.

```text
Mobility Pack
mode: Engineering / Utility / Workshop
environment: vehicle / outdoor / high-heat / vibration / UV
```

Examples: bicycle light mounts, handlebar adapters, cargo clips,
van/camper organizers, car cable clips, dashboard-safe non-critical
holders, action-cam mounts. Hard limits: no airbag zone, no pedal zone,
no critical road-safety parts; PLA is not for a high-heat cabin.

### Music / Studio / Creator Tools

Plan: [domains/studio/PLAN.md](domains/studio/PLAN.md).

A domain organic to the author and undervalued by the market.

```text
Studio / Music Pack
mode: Utility / Workshop / Engineering
environment: desk / studio
style: retro-futurist / minimalist / cinematic
```

Examples: synth/controller stands, MPC/MiniFreak/MiniFuse cable routing,
under-desk audio interface mounts, patch cable combs, headphone hooks,
mic cable clips, acoustic panel spacers, LED/neon strip mounts, desktop
risers. An excellent Free/Certified showcase: photographs beautifully,
is useful, sits close to the audience, and carries no heavy liability.

### Craft / Mold / Ceramics

Plan: [domains/craft/PLAN.md](domains/craft/PLAN.md).

```text
Craft / Mold Pack
mode: Engineering / Utility
environment: workshop
```

Examples: plaster/silicone molds, ceramics templates, stamp tools,
texture rollers, casting funnels, jigs for repeatable pieces,
soap/candle molds. The AF value is parametrization: size, shrinkage,
draft angle, split lines, keys, vents.

### Pet / Aquarium / Terrarium

Plan: [domains/pet/PLAN.md](domains/pet/PLAN.md).

A domain + environments, not a separate mode.

```text
Pet / Aquarium Pack
mode: Utility / Fluid-Grow / Engineering
environment: wet / humid
```

Examples: tube holders, feeders, sensor holders, aquarium cable clips,
terrarium plant mounts, misting nozzle mounts. Mandatory warnings:
materials, water, animals, cleaning, toxicity. Free/Certified Free;
Pro — only if a serious system emerges.

### Education / FabLab

Plan: [domains/education/PLAN.md](domains/education/PLAN.md).

Gives the already-existing Education/FabLab license its product content.

```text
Education Pack
mode: Utility / Engineering / Cinema
tier: Free / Edu
```

Examples: teaching mechanisms, cutaway models, printable validator
demos, bridge/overhang test objects, parametric lesson kits, simple
robotics chassis, classroom-safe construction kits. The strategic role:
people learn on AF and start making community packs.

### Medical / Dental — explicitly excluded

The boundary is written down:
[domains/medical/EXCLUDED.md](domains/medical/EXCLUDED.md).

The market is huge (dental 3D printing: $4.9B in 2025 → $6.2B in 2026 →
a projected $26.7B by 2033, GVR; driven by digital dentistry and
customized high-precision solutions), but regulation, materials,
biocompatibility and liability make it unfit for an early consumer
domain:

```text
Medical/Dental:
  excluded from public packs for now;
  research/B2B only;
  no patient-specific medical claims;
  requires external certification path.
```

---

## Risks and principles

1. **Pro packs are technically copyable** (YAML/data). The answer is not
   DRM: license, updates, certified status, support, Studio convenience,
   B2B services, print-farm workflow, trust in official packs.
2. **Honesty is not for sale**: Pro does NOT get more lenient
   validators — the opposite: stricter reports, more golden examples,
   better documented constraints.
3. **Mode claims stay honest**: Wearable is an accessory, not medical;
   Grow is water-path/overflow honesty, never "no leaks" without tests;
   Prop is safe and non-functional, never a weapon; Biomorphic is a
   style shell that never breaks the functional core.
4. **Namespace/id**: the loader's fail-fast on collisions is enough; the
   prefix convention `utility_/workshop_/grow_/wearable_/prop_/bio_` is
   human-readable, not a security mechanism.

The architectural backbone of the whole model: most new artifacts are
assembled as YAML / Form Recipe / Validators; new Python is needed only
for genuine building blocks and capability gaps — which is exactly what
makes data packs the natural unit of product.
