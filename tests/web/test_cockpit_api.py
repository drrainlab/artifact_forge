"""Cockpit API, tier-1: view-model contract, structured errors, and the
parity rule — the cockpit is a WINDOW into the same engine, never a mode."""

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from artifact_forge_ng.web.app import app  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = (EXAMPLES / "desk_cable_clip_20mm.yaml").read_text()

client = TestClient(app)


def test_status_is_honest():
    s = client.get("/api/status").json()
    assert s["archetypes"]["buildable"], "no buildable archetypes?"
    assert "screw_joint" in s["joints"]
    assert isinstance(s["llm"], bool) and isinstance(s["cad"], bool)


def test_catalog_cards_carry_the_contract():
    c = client.get("/api/catalog").json()
    clip = next(a for a in c["archetypes"] if a["id"] == "underdesk_cable_clip_v2_molded")
    assert clip["status"] == "buildable"
    assert "asymmetric_side_hook" in clip["contract"]["must_have"]
    assert any(p["name"] == "mouth_gap" and p["exposed"] for p in clip["parameters"])
    assert c["examples"], "examples index empty"


def test_validate_view_model_contract():
    v = client.post("/api/validate", json={"yaml": GOLDEN}).json()
    assert v["ok"] and v["status"] == "pass"
    segs = v["form"]["section"]["segments"]
    assert len(segs) == 22  # the golden profile, exact
    assert {s["type"] for s in segs} == {"line", "arc"}
    assert any("cavity_inner" in s["tags"] for s in segs)
    names = {r["name"] for r in v["form"]["regions"]}
    assert {"flange", "screw_zones", "cable_contact"} <= names
    mg = next(p for p in v["params"] if p["name"] == "mouth_gap")
    assert mg["value"] == 10.0 and mg["max"] == pytest.approx(14.0)
    assert v["form"]["frame"]["mouth_gap"] == pytest.approx(10.0)


def test_cli_cockpit_parity():
    """DoD #11: the same YAML gives the SAME summary via CLI and cockpit."""
    from artifact_forge_ng.pipeline import run_pre_cad

    state = run_pre_cad(EXAMPLES / "desk_cable_clip_20mm.yaml", None)
    cli_summary = state.summary()
    api_summary = client.post(
        "/api/validate", json={"yaml": GOLDEN}
    ).json()["cli_summary"]
    assert api_summary == cli_summary


def test_errors_are_structured_findings_never_tracebacks():
    for bad in (
        "schema: product/v1\nid: x\narchetype: warp_drive@1\n",
        "not: [valid",
        "schema: product/v1\nid: x\n",  # missing archetype
    ):
        v = client.post("/api/validate", json={"yaml": bad}).json()
        assert v["ok"] is False
        assert v["findings"], bad
        assert v["findings"][0]["level"] == "schema"
        assert "Traceback" not in str(v)


def test_assembly_validate_reports_poses_and_joints():
    asm = (EXAMPLES / "desk_lamp_e27.yaml").read_text()
    v = client.post("/api/validate", json={"yaml": asm}).json()
    assert v["ok"]
    assert {p["part"] for p in v["assembly_pose"]} == {"bracket", "cup"}
    checks = {j["check"] for j in v["joints"]}
    assert "assembly.screw_joint_ir" in checks


def test_edit_preview_shows_the_migration():
    p = client.post(
        "/api/edit/preview", json={"yaml": GOLDEN, "intent": "make_support_free"}
    ).json()
    assert p["ok"]
    assert p["patch"]["archetype"] == "underdesk_cable_clip_v3_sideprint"
    assert p["validation"]["status"] == "pass"
    assert "underdesk_cable_clip_v3_sideprint" in p["edited_yaml"]


def test_deterministic_intent_finds_the_clip():
    out = client.post("/api/intent", json={
        "prompt": "клипса под столом для пучка кабеля 20мм, 2 самореза M4"
    }).json()
    assert out["ok"] and out["source"] == "deterministic"
    ids = [c["archetype_id"] for c in out["candidates"]]
    assert "underdesk_cable_clip_v2_molded" in ids
    assert out["params"].get("bundle_d") == "20mm"
    assert out["params"].get("screw") == "M4"


def test_nl_edit_fallback_maps_known_intents():
    out = client.post("/api/nl_edit", json={
        "yaml": GOLDEN, "text": "сделай без поддержек"
    }).json()
    assert out.get("intent") == "make_support_free"


def test_index_and_static_serve():
    assert client.get("/").status_code == 200
    assert client.get("/static/js/main.js").status_code == 200
    assert client.get("/static/vendor/three.module.js").status_code == 200
