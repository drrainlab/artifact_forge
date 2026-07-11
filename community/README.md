# Community packs

Artifact Forge is open-core: the engine loads *packs* through the
`artifact_forge_ng.packs` entry-point group. A pack bundles archetypes,
examples, optionally checks and recipe ops — installable, versioned,
validator-backed. The official [showcase pack](../packs/official/artifact-forge-showcase)
is the reference implementation; the templates here are your starting
point.

The path: **download → run the showcase → copy a template → build your
pack → send a PR** (or publish it yourself — packs are just Python
packages).

## Contribution levels

Not all packs are equal; start small:

| Level | What it adds | Requirements |
|---|---|---|
| **L0 — Preset pack** | only examples/presets for existing archetypes | every example validates |
| **L1 — YAML archetype pack** | new YAML archetypes on existing recipe ops, no Python | + one example per archetype, claims documented |
| **L2 — Validator pack** | + new form checks | + PASS/FAIL/n-a tests per check |
| **L3 — Builder pack** | + new recipe ops / geometry | maintainer discussion first, golden examples, CAD smoke |

L0–L1 are ideal first contributions. See
[PACK_AUTHORING.md](PACK_AUTHORING.md) for the walkthrough and
[PACK_REVIEW_CHECKLIST.md](PACK_REVIEW_CHECKLIST.md) for what review
looks at.

Community packs live in their own repositories (or a future
community-packs index) — this repo hosts the engine, the official packs
and these templates.
