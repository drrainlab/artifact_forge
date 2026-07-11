# Examples

Every YAML here is a golden: `forge validate` passes the pre-CAD gate and
`forge build` produces STL/STEP at grade pass.

```bash
uv run forge validate catalog/examples/desk_cable_clip_20mm.yaml
uv run forge build    catalog/examples/desk_cable_clip_20mm.yaml -o out
```

Good starting points:

- `desk_cable_clip_20mm.yaml` — the flagship single part: asymmetric
  side-entry clip with measured mouth/lip geometry and screw access.
- `desk_cable_clip_20mm_sideprint.yaml` — the same clip as a constant
  section side-print: zero overhangs by construction.
- `phone_stand_bio.yaml` — engineering core (slot trigonometry, COM
  stability gate) under a biomorphic skin.
- `esp32_box_with_lid.yaml` — an `assembly/v1`: lid seat dimension chain
  verified before CAD, screw joints and press-fit pins measured in the
  assembled pose.
- `desk_lamp_e27.yaml` — bracket + socket cup with a cable channel probed
  through BOTH parts in the pose.
- `bearing_turntable_base_v1` via `bearing_turntable_base.yaml` — a 608
  bearing seat with a verified retention lip and a phyllotaxis spiral.
