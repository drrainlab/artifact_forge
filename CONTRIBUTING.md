# Contributing

Thanks for looking at Artifact Forge. The project optimizes for one thing:
**engineering honesty** — every geometric promise is measured, and the
pipeline refuses to claim what it didn't verify. Contributions are judged
by the same rule.

## Setup

```bash
uv sync --extra cad --extra web     # full dev environment
uv run pytest -m "not cad"          # fast IR tier (~2 min, no cadquery)
uv run pytest                       # full suite including CAD probes
```

## Ground rules

- **The fast tier must stay green** (`pytest -m "not cad"`); run the full
  suite before submitting anything that touches the compiler, validators
  or assembly layers.
- **New geometry = new checks.** A builder or recipe op ships with its
  semantic regions, frame keys and validators — all four. An op whose
  archetypes are not subscribed to its validators will be refused by the
  catalog loader; that is by design.
- **Never register silently.** Ops, checks and joints bind by name,
  fail-fast at load. If you add a check, declare it in
  `validators/probes.py`; if you implement one, `register_probe` it from a
  module the registration path imports.
- **Form IR stays CAD-free.** Nothing under `form/` may import cadquery
  (there is a test for this).
- Match the existing style: type hints, dataclasses, small self-registering
  modules, docstrings that state the engineering contract rather than
  restate the code.

## Pull requests

- One logical change per PR; pure code motion separated from behavior
  changes.
- Include the check/validator story in the description: what is measured
  now that wasn't before, or why nothing new needs measuring.
- New archetypes should come with a working example under
  `catalog/examples/` that builds at grade pass.

## Domain packs

Domain-specific families (ops + checks + archetypes + tests) can live
outside this repository entirely — the engine loads packs through the
`artifact_forge_ng.packs` entry-point group. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). If your contribution is a
whole domain, a pack is usually the right shape for it.
