# Medical / Dental — explicitly excluded

The domain is excluded from public packs — written down explicitly so the
boundary is a decision, not a default.

## Why it is out of scope

- **Regulation**: medical devices (EU MDR, FDA) require
  certification, clinical evaluation, and post-market surveillance — this is
  incompatible with the community/self-serve pack model.
- **Materials and biocompatibility**: FDM plastics and home printing do not
  provide controlled biocompatibility, sterilizability, or fatigue
  guarantees.
- **Liability**: a defective patient-specific device means harm to a
  person, not a broken clip. AF's honesty validators measure
  geometry, not clinical outcome.

The market is nonetheless huge (dental 3DP: $4.9B in 2025 → forecast $26.7B by
2033, GVR) — the exclusion deliberately leaves money on the table for the
sake of trust in the rest of the platform.

## What is NOT allowed even in research/B2B packs

```text
- patient-specific medical claims (orthoses, prostheses, patient-fitted splints);
- implants and anything invasive;
- prescription optics / vision correction (the Eyewear boundary!);
- PPE/protection with certification claims (masks, helmets, protective eyewear);
- sterility / wound contact / long-term skin-contact claims.
```

## Conditions for revisiting (all three simultaneously)

1. An external **certification path** (a partner or customer who carries
   the regulatory certification of the device as their own product).
2. A partner with **regulatory expertise** (MDR/FDA) inside the project's
   perimeter.
3. A **B2B contract** where AF is the supplier's engineering tool, not
   the manufacturer of a medical device; no public packs whatsoever.

## Boundaries with neighboring domains

- [Accessibility](../accessibility/PLAN.md): a daily-living accessory is
  legitimate; anything that treats/rehabilitates/compensates for a diagnosis
  belongs here, i.e. excluded.
- Eyewear ([ECOSYSTEM.md](../../ECOSYSTEM.md)): frames as
  maker/costume/non-prescription frames are legitimate; lenses, prescriptions,
  optical correction, certified eye protection — excluded.
- Wearable (the P line): comfort contracts (body-contact, donning) are
  engineering honesty, NOT a medical claim; report wording
  must not sound therapeutic.
