# Authoring a pack

## 1. Copy a template

- `templates/yaml-pack/` — L0/L1: archetypes + examples, zero Python
  beyond the two-line `register()`.
- `templates/python-pack/` — L2: adds self-registering form checks with
  their declarations and tests.

Rename the package dir (`af_pack_example_*` → your id), update
`pack.yaml` and `pyproject.toml` (the entry-point name must be unique).

## 2. The registration contract

The engine discovers your pack via the entry point:

```toml
[project.entry-points."artifact_forge_ng.packs"]
my_pack = "my_pack:register"
```

`register(ctx)` runs once, at `load_catalog()` time, fail-fast:

- `ctx.add_data_dir(path)` — a dir mirroring the core catalog layout:
  optional `features.yaml`, `archetypes/` (subdirs allowed),
  optional `modifiers/`.
- importing your `checks/` / `ops/` modules self-registers them into the
  shared registries (same `register_probe` / `_register` conventions as
  core — read the showcase pack's modules).
- **collisions are errors**: replacing an existing op / joint / check
  registration raises unless you explicitly `ctx.declare_override(name)`.
- new check NAMES are declared first (see the showcase
  `declarations.py` pattern — idempotent `declare()` at import).

## 3. The honesty rules (non-negotiable)

- Every archetype ships at least one example that `forge validate`
  passes in strict mode. Geometry the validators don't measure is a
  hallucination — don't ship it.
- Every new check has PASS, FAIL and n/a branch tests, built on real
  op-built forms (never hand-typed frames).
- Claims are explicit. Default non-claims: **no** medical,
  safety-critical, mains-voltage, pressure-rated, IP-rated, food-safe or
  animal-safe claims unless externally certified — put the wording in
  your `docs/CLAIMS.md`.
- A screenshot or render per archetype is strongly encouraged.

## 4. Test locally

```bash
uv pip install -e path/to/your-pack
uv run forge validate path/to/your-pack/examples/your_example.yaml
uv run pytest path/to/your-pack/tests
ARTIFACT_FORGE_DISABLE_PACKS=1 uv run python -c "import artifact_forge_ng"  # core stays clean
```
