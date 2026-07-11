# Pack anatomy

This pack is the reference implementation of an Artifact Forge pack —
copy it (or `community/templates/`) to build your own.

```
pack.yaml                      # metadata: id, tier, license, domains, claims
pyproject.toml                 # installable package + the entry point:
                               #   [project.entry-points."artifact_forge_ng.packs"]
                               #   showcase = "artifact_forge_showcase:register"
src/artifact_forge_showcase/
  __init__.py                  # register(ctx): declare checks, import check
                               # modules, ctx.add_data_dir(data)
  declarations.py              # KNOWN_CHECKS declarations (fail-fast vocabulary)
  data/
    features.yaml              # feature ids with verified_by bindings
    archetypes/<domain>/*.yaml # recipe archetypes on the core op registry
  checks/                      # register_probe implementations
examples/<domain>/*.yaml       # product instances; each must validate
tests/                         # validate-every-example + PASS/FAIL check tests
docs/PACK.md CLAIMS.md GALLERY.md
```

The engine discovers the pack through the entry point at
`load_catalog()` time; registration is deterministic, idempotent and
fail-fast on any name collision with core or other packs. Set
`ARTIFACT_FORGE_DISABLE_PACKS=1` to run the bare core.
