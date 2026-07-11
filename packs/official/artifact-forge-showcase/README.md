# Artifact Forge — Showcase Pack (free, official)

The first official pack: useful, validator-backed parts across four
domains, built entirely from the core engine's existing recipe ops — no
new kernel geometry. It doubles as the reference implementation of the
pack architecture: copy its layout (or `community/templates/`) to build
your own.

| Domain | Archetypes |
|---|---|
| studio | under-desk audio interface mount, patch cable comb |
| repair | hose adapter (vacuum/drain/garden presets), replacement knob |
| jigs | drilling jig with press-fit steel bushings |
| education | tolerance ladder (clearance-band probes) |

Every archetype ships with examples that `forge validate` and
`forge build` at grade pass, and with honest non-claims
(see [docs/CLAIMS.md](docs/CLAIMS.md)).

```bash
uv pip install -e . -e packs/official/artifact-forge-showcase
uv run forge validate packs/official/artifact-forge-showcase/examples/repair/vacuum_hose_32_to_35.yaml
```

License: Apache-2.0 (same as the core).
