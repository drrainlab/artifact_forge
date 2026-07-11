# Pack review checklist

What a reviewer verifies before a community pack is listed:

## Structure
- [ ] `pack.yaml` present: id, version, tier, license, author, claims.
- [ ] Entry point resolves; `register(ctx)` is idempotent and fail-fast.
- [ ] Layout follows a template (data/, examples/, tests/, docs/).

## Honesty
- [ ] Every archetype has ≥1 example; every example validates in strict
      mode with the pack installed.
- [ ] Every new check name is declared before registration and carries
      PASS / FAIL / n-a tests on op-built forms.
- [ ] No feature without a `verified_by` binding; no validator the
      archetypes don't subscribe to.
- [ ] `ARTIFACT_FORGE_DISABLE_PACKS=1` leaves core registries untouched.

## Catalog metadata
- [ ] Every archetype carries a `catalog:` block (domain, modes, tier,
      tags); `pack.yaml` is registered via `add_pack_manifest`.
- [ ] All `catalog.featured` ids exist in the pack.
- [ ] Reference/primitive geometry is marked `kind`/`audience` so the
      default view stays a product shelf, not a registry dump.

## Claims & safety
- [ ] `docs/CLAIMS.md` states the non-claims; no medical /
      safety-critical / mains / pressure / IP / food-safe / animal-safe
      wording anywhere unless externally certified.
- [ ] Descriptions don't oversell ("verify fit", "shop probe", "not
      OEM" where applicable).

## Level gates
- [ ] L2+: checks reviewed for measured semantics (bands, frame keys).
- [ ] L3: prior maintainer discussion, golden examples build at grade
      pass, CAD smoke test included.

## Licensing
- [ ] License declared and compatible with redistribution; third-party
      assets attributed.
