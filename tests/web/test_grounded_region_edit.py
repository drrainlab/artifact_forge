"""E1 — grounded region edit: a modifier target is a Form IR region, never
free text. The catalog computes which regions each modifier may land on,
nl_edit enum-grounds targets (aliases canonicalized, unambiguous targets
auto-filled with a note), and an illegal target fails the preview with a
did-you-mean — the pipeline proposes, the user confirms, nothing is fixed
silently."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from artifact_forge_ng.catalog.loader import (  # noqa: E402
    compatible_regions,
    load_catalog,
    resolve_region_name,
    suggest_region,
)
from artifact_forge_ng.web import llm  # noqa: E402
from artifact_forge_ng.web.app import app  # noqa: E402

client = TestClient(app)

RING_YAML = """\
schema: product/v1
id: ring_test
archetype: finger_ring_v1@1
strict: true
params: {}
"""


@pytest.fixture()
def ring():
    return load_catalog().archetypes["finger_ring_v1"]


def test_region_spec_carries_labels_and_aliases(ring):
    r = ring.region("band_outer_surface")
    assert r.label == "outer ring band"
    assert "ring band" in r.aliases


def test_compatible_regions_respect_roles_and_editability(ring):
    catalog = load_catalog()
    voronoi = catalog.modifiers["add_voronoi_field"]
    ids = [r.id for r in compatible_regions(ring, voronoi)]
    assert ids == ["band_outer_surface"]  # bore/seam are protected roles


def test_resolve_region_name_matches_id_label_and_aliases(ring):
    # 'ring_band' was the original LLM miss: alias "ring band" normalizes to it
    assert resolve_region_name(ring, "ring_band").id == "band_outer_surface"
    assert resolve_region_name(ring, "Outer Wall").id == "band_outer_surface"
    assert resolve_region_name(ring, "band_outer_surface").id == "band_outer_surface"
    assert resolve_region_name(ring, "warp_core") is None


def test_suggest_region_fuzzy_matches_typos(ring):
    assert suggest_region(ring, "band_outter_surfce").id == "band_outer_surface"


def test_catalog_cards_carry_region_targets():
    c = client.get("/api/catalog").json()
    card = next(a for a in c["archetypes"] if a["id"] == "finger_ring_v1")
    regions = {r["id"]: r for r in card["regions"]}
    band = regions["band_outer_surface"]
    assert band["editable"] and band["label"] == "outer ring band"
    assert {"add_voronoi_field", "add_hex_perforation"} <= set(
        band["compatible_modifiers"])
    assert regions["bore_contact"]["compatible_modifiers"] == []


def _fake_llm(monkeypatch, answer):
    """LLM ON with a canned answer; captures the schema the model saw."""
    seen = {}

    def fake_complete(system, user, schema, cache_system=True):
        seen["system"], seen["schema"] = system, schema
        return answer

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(llm, "complete", fake_complete)
    return seen


def test_nl_edit_canonicalizes_alias_targets(monkeypatch):
    seen = _fake_llm(monkeypatch, {"intent": None, "patch": {
        "type": "style", "reason": "voronoi",
        "modifiers": {"add": [
            {"id": "add_voronoi_field", "target": "ring_band", "params": {}},
        ]},
    }})
    out = client.post("/api/nl_edit", json={
        "yaml": RING_YAML, "text": "add voronoi pattern"}).json()
    assert out["ok"]
    assert out["patch"]["modifiers"]["add"][0]["target"] == "band_outer_surface"
    assert "canonical" in out["notes"]
    # the schema itself only offers legal targets
    add_schema = (seen["schema"]["properties"]["patch"]["properties"]
                  ["modifiers"]["properties"]["add"]["items"])
    assert add_schema["properties"]["target"]["enum"] == ["band_outer_surface"]
    assert "band_outer_surface" in seen["system"]
    assert "Protected regions" in seen["system"]


def test_nl_edit_auto_targets_missing_target(monkeypatch):
    _fake_llm(monkeypatch, {"intent": None, "patch": {
        "type": "style",
        "modifiers": {"add": [
            {"id": "add_hex_perforation", "target": "", "params": {}},
        ]},
    }})
    out = client.post("/api/nl_edit", json={
        "yaml": RING_YAML, "text": "add hex holes"}).json()
    assert out["patch"]["modifiers"]["add"][0]["target"] == "band_outer_surface"
    assert "auto-targeted" in out["notes"]


def test_nl_edit_selected_region_pins_the_enum(monkeypatch):
    seen = _fake_llm(monkeypatch, {"intent": None, "patch": {
        "type": "style",
        "modifiers": {"add": [
            {"id": "add_voronoi_field", "target": "band_outer_surface",
             "params": {}},
        ]},
    }})
    out = client.post("/api/nl_edit", json={
        "yaml": RING_YAML, "text": "add voronoi",
        "selected_region": "outer wall"}).json()  # alias resolves too
    assert out["ok"]
    assert "selected region" in seen["system"] or "selected" in seen["system"]
    add_schema = (seen["schema"]["properties"]["patch"]["properties"]
                  ["modifiers"]["properties"]["add"]["items"])
    assert add_schema["properties"]["target"]["enum"] == ["band_outer_surface"]


def test_edit_preview_fails_with_did_you_mean():
    p = client.post("/api/edit/preview", json={"yaml": RING_YAML, "patch": {
        "type": "style",
        "modifiers": {"add": [
            {"id": "add_voronoi_field", "target": "ring_band", "params": {}},
        ]},
    }}).json()
    assert p["ok"] is False
    dym = p["did_you_mean"]
    assert dym and dym[0]["suggestion"] == "band_outer_surface"
    assert dym[0]["given"] == "ring_band"
    assert "did you mean" in p["findings"][0]["suggestion"]


RING_WITH_VORONOI = RING_YAML + """\
modifiers:
  - id: add_voronoi_field
    target: band_outer_surface
    params: {sites: 12}
"""


def test_nl_edit_converts_duplicate_add_to_update(monkeypatch):
    """'add voronoi' on a ring that already has it must not become a
    silent no-op add — it turns into an update on the existing use."""
    _fake_llm(monkeypatch, {"intent": None, "patch": {
        "type": "style",
        "modifiers": {"add": [
            {"id": "add_voronoi_field", "target": "band_outer_surface",
             "params": {"sites": "24"}},
        ]},
    }})
    out = client.post("/api/nl_edit", json={
        "yaml": RING_WITH_VORONOI, "text": "add voronoi pattern"}).json()
    mods = out["patch"]["modifiers"]
    assert mods["add"] == []
    assert mods["update"][0]["id"] == "add_voronoi_field"
    assert "converted add to update" in out["notes"]


def test_edit_preview_reports_noop():
    """A duplicate add is skipped by apply_patch — the preview must call
    the patch a NO-OP instead of pretending something will change."""
    p = client.post("/api/edit/preview", json={
        "yaml": RING_WITH_VORONOI, "patch": {
            "type": "style",
            "modifiers": {"add": [
                {"id": "add_voronoi_field", "target": "band_outer_surface",
                 "params": {}},
            ]},
        }}).json()
    assert p["ok"] and p["noop"] is True


def test_nl_edit_survives_llm_shape_drift(monkeypatch):
    """The forced tool call keeps the top-level shape, but nested objects
    sometimes arrive as JSON strings (real crash: 'str' object has no
    attribute 'get'). nl_edit must decode or drop with a note — never 500."""
    import json as _json

    _fake_llm(monkeypatch, {"intent": None, "patch": _json.dumps({
        "type": "style",
        "modifiers": {"add": [
            "garbage-entry",
            {"id": "add_voronoi_field", "target": "ring_band", "params": {}},
        ]},
    })})
    out = client.post("/api/nl_edit", json={
        "yaml": RING_YAML, "text": "add voronoi pattern"}).json()
    assert out["ok"], out
    adds = out["patch"]["modifiers"]["add"]
    assert len(adds) == 1
    assert adds[0]["target"] == "band_outer_surface"
    assert "decoded JSON-string" in out["notes"]
    assert "malformed" in out["notes"]

    # a patch that is not an object at all -> nothing actionable remains;
    # that is an HONEST failure carrying the drop notes, not ok:true that
    # the preview then rejects as 'edit needs intent or patch'
    _fake_llm(monkeypatch, {"intent": None, "patch": "not json at all"})
    out = client.post("/api/nl_edit", json={
        "yaml": RING_YAML, "text": "add voronoi pattern"}).json()
    assert out["ok"] is False
    assert out["findings"][0]["check"] == "edit.nl"
    assert "dropped" in out["findings"][0]["message"]

    # a completely empty answer fails the same way, with the raw dump
    _fake_llm(monkeypatch, {"intent": None, "patch": None})
    out = client.post("/api/nl_edit", json={
        "yaml": RING_YAML, "text": "add voronoi pattern"}).json()
    assert out["ok"] is False
    assert "neither a known intent nor a patch" in out["findings"][0]["message"]


def test_edit_preview_catches_dead_field_before_build():
    """Default voronoi params (edge_margin 3mm) kill every cell on a narrow
    band — the preview must FAIL at validate (form.field_cells_present),
    not let the user apply and hit topology.hex_field_present after a full
    CAD build."""
    yaml8 = RING_YAML.replace("params: {}", "params: {band_h: 8mm}")
    p = client.post("/api/edit/preview", json={"yaml": yaml8, "patch": {
        "type": "style",
        "modifiers": {"add": [
            {"id": "add_voronoi_field", "target": "band_outer_surface",
             "params": {}},
        ]},
    }}).json()
    assert p["ok"]
    assert p["validation"]["status"] == "fail"
    checks = {f["check"]: f for f in p["validation"]["findings"]}
    dead = checks["form.field_cells_present"]
    assert dead["status"] == "fail" and "edge_margin" in dead["suggestion"]


def test_edit_preview_passes_with_the_canonical_target():
    p = client.post("/api/edit/preview", json={"yaml": RING_YAML, "patch": {
        "type": "style",
        "modifiers": {"add": [
            {"id": "add_voronoi_field", "target": "band_outer_surface",
             "params": {"sites": 22, "min_ligament": "1.2mm",
                        "edge_margin": "0.5mm"}},
        ]},
    }}).json()
    assert p["ok"], p
    assert p["validation"]["status"] in ("pass", "warn")
