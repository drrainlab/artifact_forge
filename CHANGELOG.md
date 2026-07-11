# Changelog

## 0.1.0 — first public release

The initial open-source release of the Artifact Forge core:

- Typed YAML Product Grammar: catalog of archetypes, features, modifiers
  and interfaces with fail-fast name binding.
- CAD-free Form IR with form-level validators (`forge validate` runs the
  whole golden gate without cadquery).
- CadQuery compiler with topology / region / manufacturing probes, honesty
  report and score.
- Recipe archetypes: composable registered ops directly in YAML.
- Modifier kernel: typed, region-bound, keepout-aware IR transformations.
- Biomorphic SurfaceStyle and the implicit (SDF) skin export.
- Verified assemblies (`assembly/v1`): joint registry, pose math, IR
  checks before CAD, fit probes in the assembled pose, BOM.
- Semantic edit (`forge edit`) with preserve contracts.
- Product Cockpit: local web debugger over the same pipeline.
- Pack mechanism: domain packs plug in via the `artifact_forge_ng.packs`
  entry-point group.
