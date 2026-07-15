"""prompt -> assembly/v1 intent core (wave W2).

Mock discipline: ``llm.complete`` is monkeypatched at the module level —
the intent code must treat a mocked answer exactly like a live one
(grounded, expanded, validated; never trusted raw). The canonical compact
mirrors catalog/examples/esp32_box_with_lid.yaml, which validates pass.
"""

from __future__ import annotations

import copy
import json

import pytest
import yaml

from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.product.assembly import AssemblyInstance
from artifact_forge_ng.web import assembly_intent

PROMPT = "коробка под ESP32 с крышкой на винтах M3"

CANON = {
    "id": "esp32_station", "root": "box", "confidence": "high",
    "notes": "box+lid per the worked example",
    "parts": [
        {"ref": "box", "archetype_id": "enclosure_base_v1",
         "params": {"box_l": "82mm", "box_w": "52mm", "box_h": "26mm",
                    "floor_t": "3mm", "boss_h": "19mm", "pilot_d": "4mm",
                    "port": "usb_c", "port_z": "12mm"}},
        {"ref": "lid", "archetype_id": "enclosure_lid_v1",
         "params": {"lid_l": "82mm", "lid_w": "52mm", "lid_t": "3mm",
                    "seat_clearance": "0.3mm", "plug_depth": "3.5mm",
                    "screw": "M3", "pin_d": "4.1mm", "pin_len": "4mm"}},
    ],
    "joints": [
        {"type": "lid_seat",
         "a": {"ref": "box", "kind": "datum", "id": "rim"},
         "b": {"ref": "lid", "kind": "datum", "id": "seat"},
         "rotate": [180, 0, 0], "params": {"clearance": 0.3}},
        {"type": "screw_joint",
         "a": {"ref": "box", "kind": "datum", "id": "rim"},
         "b": {"ref": "lid", "kind": "datum", "id": "seat"},
         "rotate": [180, 0, 0],
         "params": {"screw": "M3", "count": 2, "pilots": "bosses_pilot"}},
    ],
    "shared": [
        {"param": "wall", "value": "2.4mm", "parts": ["box", "lid"]},
        {"param": "boss_sx", "value": "61.2mm", "parts": ["box", "lid"]},
        {"param": "boss_sy", "value": "31.2mm", "parts": ["box", "lid"]},
    ],
    "contract_must_have": ["seated_lid", "bolted_interface"],
}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def canon() -> dict:
    return copy.deepcopy(CANON)


def _mock_llm(monkeypatch, answers: list[dict]) -> list[str]:
    """Sequential mocked answers; returns the captured user messages."""
    from artifact_forge_ng.web import llm
    it = iter(answers)
    calls: list[str] = []

    def fake_complete(system, user, schema, cache_system=True,
                      max_tokens=2000):
        calls.append(user)
        return copy.deepcopy(next(it))

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete", fake_complete)
    return calls


def _run(monkeypatch, catalog, answers, prompt=PROMPT, max_repairs=2):
    """max_repairs pinned to 2 here: the tests assert exact call counts,
    independent of the production default budget."""
    calls = _mock_llm(monkeypatch, answers)
    out = assembly_intent.llm_assembly(prompt, catalog,
                                       max_repairs=max_repairs)
    return out, calls


# -- 1. grounding ---------------------------------------------------------------


def test_valid_answer_passes_in_one_call(monkeypatch, catalog):
    out, calls = _run(monkeypatch, catalog, [canon()])
    assert len(calls) == 1
    assert out["valid"] and out["pre_cad_valid"]
    assert out["verification_state"] == "pre_cad_pass"
    assert out["can_build"]
    assert out["iterations"] == 1 and out["selected_iteration"] == 1
    assert out["validation"]["status"] == "pass"
    doc = yaml.safe_load(out["yaml"])
    AssemblyInstance.model_validate(doc)          # LLM answer == YAML


def test_hallucinated_archetype_triggers_repair(monkeypatch, catalog):
    bad = canon()
    bad["parts"][0]["archetype_id"] = "warp_core_enclosure_xx"
    out, calls = _run(monkeypatch, catalog, [bad, canon()])
    assert len(calls) == 2
    assert out["valid"]
    assert out["iterations"] == 2 and out["selected_iteration"] == 2
    assert "unknown archetype" in calls[1] or "grounded parts" in calls[1]


def test_unknown_joint_type_is_a_fail_finding(monkeypatch, catalog):
    bad = canon()
    bad["joints"][0]["type"] = "quantum_weld"
    out, _ = _run(monkeypatch, catalog, [bad, bad])
    assert not out["valid"]
    assert any("unknown joint type" in f["message"]
               for f in out["grounding_findings"])


def test_unknown_optional_param_is_dropped_with_note(monkeypatch, catalog):
    loose = canon()
    loose["parts"][0]["params"]["swagger_level"] = "11mm"
    out, calls = _run(monkeypatch, catalog, [loose])
    assert len(calls) == 1
    assert out["valid"], "an unknown optional param must not sink validity"
    assert "swagger_level" in out["notes"]


def test_rotate_snaps_to_quarter_turn_with_note(monkeypatch, catalog):
    tilted = canon()
    tilted["joints"][0]["rotate"] = [179, 0, 1]
    out, _ = _run(monkeypatch, catalog, [tilted])
    assert out["valid"]
    assert "snapped" in out["notes"]


def test_undeclared_datum_is_a_fail_finding(monkeypatch, catalog):
    bad = canon()
    bad["joints"][0]["a"]["id"] = "top_hat"
    out, _ = _run(monkeypatch, catalog, [bad, bad])
    assert not out["valid"]
    assert any("declares no datum 'top_hat'" in f["message"]
               for f in out["grounding_findings"])


def test_port_endpoint_resolves_to_canonical_datum(monkeypatch, catalog):
    """kind=port resolves at grounding time — the document carries the
    canonical datum anchor, kind never reaches assembly/v1."""
    ported = canon()
    ported["parts"].append(
        {"ref": "board", "archetype_id": "pegboard_mount_base_v1",
         "params": {}})
    ported["joints"].append({
        "type": "screw_joint",
        "a": {"ref": "box", "kind": "datum", "id": "rim"},
        "b": {"ref": "board", "kind": "port", "id": "board_pegs"},
        "rotate": [0, 0, 0], "params": {}})
    out, _ = _run(monkeypatch, catalog, [ported, ported])
    # the port resolved to its declared datum in the emitted YAML
    assert "board.board_face" in out["yaml"]


# -- 2. repair loop --------------------------------------------------------------


def test_repair_budget_returns_best_draft(monkeypatch, catalog):
    b1 = canon()
    b1["joints"][1]["params"]["screw"] = "M8"      # validate fail (1 joint)
    b2 = canon()
    b2["joints"][0]["a"]["id"] = "nowhere"          # grounding fail
    b2["joints"][1]["params"]["screw"] = "M8"
    b3 = {"id": "x", "root": "box", "confidence": "low",
          "parts": [{"ref": "box", "archetype_id": "enclosure_base_v1"}],
          "joints": []}                              # too few parts
    out, calls = _run(monkeypatch, catalog, [b1, b2, b3])
    assert len(calls) == 3                           # 1 + max_repairs
    assert out["ok"] and not out["valid"]
    assert out["iterations"] == 3
    assert out["selected_iteration"] == 1            # best by _draft_score
    assert out["yaml"]                               # draft still delivered


def test_no_progress_stops_early(monkeypatch, catalog):
    bad = canon()
    bad["joints"][0]["a"]["id"] = "nowhere"
    out, calls = _run(monkeypatch, catalog, [bad, bad, bad])
    assert len(calls) == 2, "identical failure digest must stop the loop"
    assert not out["valid"]


def test_repair_user_message_carries_findings_and_compact(
        monkeypatch, catalog):
    bad = canon()
    bad["joints"][0]["a"]["id"] = "nowhere"
    _, calls = _run(monkeypatch, catalog, [bad, canon()])
    assert "PREVIOUS ASSEMBLY" in calls[1]
    assert "nowhere" in calls[1]
    assert PROMPT in calls[1]


# -- 3. modifiers -----------------------------------------------------------------


def test_modifier_grounds_into_document(monkeypatch, catalog):
    modded = canon()
    modded["parts"][0]["modifiers"] = [
        {"id": "add_hex_perforation", "target": "floor",
         "params": {"cell": "7mm"}}]
    out, _ = _run(monkeypatch, catalog, [modded])
    doc = yaml.safe_load(out["yaml"])
    mods = doc["parts"][0]["product"].get("modifiers", [])
    assert mods and mods[0]["id"] == "add_hex_perforation"


def test_incompatible_modifier_target_fails(monkeypatch, catalog):
    modded = canon()
    modded["parts"][0]["modifiers"] = [
        {"id": "add_hex_perforation", "target": "shell"}]
    out, _ = _run(monkeypatch, catalog, [modded, modded])
    assert any("not a legal target" in f["message"]
               for f in out["grounding_findings"])


def test_duplicate_and_excess_modifiers_fail(monkeypatch, catalog):
    dup = canon()
    dup["parts"][0]["modifiers"] = [
        {"id": "add_hex_perforation", "target": "floor"},
        {"id": "add_hex_perforation", "target": "floor"}]
    out, _ = _run(monkeypatch, catalog, [dup, dup])
    assert any("duplicate modifier" in f["message"]
               for f in out["grounding_findings"])

    много = canon()
    много["parts"][0]["modifiers"] = [
        {"id": "add_hex_perforation", "target": "floor"}] * 5
    out2, _ = _run(monkeypatch, catalog, [много, много])
    assert any("per-part max" in f["message"]
               for f in out2["grounding_findings"])


# -- 3b. wiring + constraints ------------------------------------------------------


def test_wiring_survives_expansion_and_defers_to_build(monkeypatch, catalog):
    wired = canon()
    wired["wiring"] = {"from_part": "box", "to_part": "lid", "d": "6mm"}
    out, _ = _run(monkeypatch, catalog, [wired])
    doc = yaml.safe_load(out["yaml"])
    assert doc["wiring"] == {"from_part": "box", "to_part": "lid",
                             "d": "6mm"}
    assert "assembly.channel_continuous_across" in out["deferred_checks"]
    assert out["verification_state"] == "build_required"
    assert out["can_build"]


def test_wiring_unknown_ref_fails(monkeypatch, catalog):
    wired = canon()
    wired["wiring"] = {"from_part": "box", "to_part": "ghost", "d": "6mm"}
    out, _ = _run(monkeypatch, catalog, [wired, wired])
    assert any("unknown part ref 'ghost'" in f["message"]
               for f in out["grounding_findings"])


def test_ambiguous_wiring_path_fails_without_via(monkeypatch, catalog):
    tri = canon()
    tri["parts"].append({"ref": "lid2",
                         "archetype_id": "enclosure_lid_v1",
                         "params": dict(tri["parts"][1]["params"])})
    tri["joints"].append({
        "type": "lid_seat",
        "a": {"ref": "box", "kind": "datum", "id": "rim"},
        "b": {"ref": "lid2", "kind": "datum", "id": "seat"},
        "rotate": [180, 0, 0], "params": {}})
    tri["joints"].append({
        "type": "screw_joint",
        "a": {"ref": "lid", "kind": "datum", "id": "seat"},
        "b": {"ref": "lid2", "kind": "datum", "id": "seat"},
        "rotate": [0, 0, 0], "params": {}})
    tri["wiring"] = {"from_part": "box", "to_part": "lid2"}
    out, _ = _run(monkeypatch, catalog, [tri, tri])
    assert any("ambiguous wiring path" in f["message"]
               for f in out["grounding_findings"])


def test_hard_constraint_loss_is_a_fail(monkeypatch, catalog):
    """E27 in the prompt, nothing lamp-ish in the draft — hard fail."""
    out, _ = _run(monkeypatch, catalog, [canon(), canon()],
                  prompt="коробка под контроллер и патрон E27")
    assert any("hard prompt constraint 'E27'" in f["message"]
               for f in out["grounding_findings"])
    assert not out["valid"]


def test_spaced_dimension_matches_canonical_param(monkeypatch, catalog):
    """«82 мм» in the prompt normalizes to the value-grammar "82mm" the
    draft actually carries — a reflected dimension must NOT fail."""
    out, _ = _run(monkeypatch, catalog, [canon()],
                  prompt="коробка под ESP32 длиной 82 мм с крышкой на винтах M3")
    assert not any("hard prompt constraint '82" in f["message"]
                   for f in out["grounding_findings"])
    assert out["valid"]


def test_soft_preference_is_a_note(monkeypatch, catalog):
    out, _ = _run(monkeypatch, catalog, [canon()],
                  prompt="красивая коробка под ESP32 с винтами M3")
    assert out["valid"]
    assert "soft preference" in out["notes"]


# -- 3c. graph / shared / pose ------------------------------------------------------


def test_isolated_part_fails(monkeypatch, catalog):
    lonely = canon()
    lonely["parts"].append({"ref": "orphan",
                            "archetype_id": "enclosure_lid_v1",
                            "params": {}})
    out, _ = _run(monkeypatch, catalog, [lonely, lonely])
    assert any("isolated" in f["message"]
               for f in out["grounding_findings"])


def test_verify_before_establish_is_reordered_with_note(
        monkeypatch, catalog):
    swapped = canon()
    swapped["joints"] = [swapped["joints"][1], swapped["joints"][0]]
    out, _ = _run(monkeypatch, catalog, [swapped])
    assert out["valid"]
    assert "reordered" in out["notes"]
    doc = yaml.safe_load(out["yaml"])
    assert doc["joints"][0]["type"] == "lid_seat"


def test_only_verify_joints_cannot_pose_a_part(monkeypatch, catalog):
    weak = canon()
    weak["joints"] = [{
        "type": "press_fit_pin_pair",
        "a": {"ref": "box", "kind": "datum", "id": "rim"},
        "b": {"ref": "lid", "kind": "datum", "id": "seat"},
        "rotate": [180, 0, 0],
        "params": {"interference": 0.1, "receivers": "bosses_pilot"}}]
    out, _ = _run(monkeypatch, catalog, [weak, weak])
    assert any("verify" in f["message"] and "pose" in f["message"].lower()
               for f in out["grounding_findings"])


def test_two_establish_joints_on_one_part_is_ambiguous(monkeypatch, catalog):
    twice = canon()
    twice["joints"].append({
        "type": "dovetail_joint",
        "a": {"ref": "box", "kind": "datum", "id": "rim"},
        "b": {"ref": "lid", "kind": "datum", "id": "seat"},
        "rotate": [0, 0, 0], "params": {}})
    out, _ = _run(monkeypatch, catalog, [twice, twice])
    assert any("ambiguous pose establishment" in f["message"]
               for f in out["grounding_findings"])


def test_shared_conflict_with_explicit_value_fails(monkeypatch, catalog):
    clash = canon()
    clash["parts"][0]["params"]["wall"] = "3mm"    # explicit 3mm
    # shared says 2.4mm for the same part -> silent override forbidden
    out, _ = _run(monkeypatch, catalog, [clash, clash])
    assert any("silently override" in f["message"]
               for f in out["grounding_findings"])


def test_scoped_shared_materializes_into_params(monkeypatch, catalog):
    scoped = canon()
    # wall stated only for the box — lid also declares wall, so the
    # binding is scoped, must land in box params, NOT in kernel shared
    scoped["shared"][0]["parts"] = ["box"]
    out, _ = _run(monkeypatch, catalog, [scoped])
    doc = yaml.safe_load(out["yaml"])
    assert doc["parts"][0]["product"]["params"]["wall"] == "2.4mm"
    assert "wall" not in doc.get("shared", {})
    # full-coverage bindings stay kernel-level
    assert doc["shared"]["boss_sx"] == "61.2mm"


def test_resource_limits_fail_fast(monkeypatch, catalog):
    huge = canon()
    huge["parts"] = [
        {"ref": f"p{i}", "archetype_id": "enclosure_base_v1", "params": {}}
        for i in range(20)
    ]
    out, _ = _run(monkeypatch, catalog, [huge, huge])
    assert any("resource limits" in f["message"]
               for f in out["grounding_findings"])


# -- 5. deterministic fallback -------------------------------------------------------


def test_deterministic_fallback_suggests_examples(catalog):
    out = assembly_intent.deterministic_assembly(
        "коробка esp32 с крышкой", catalog)
    assert out["source"] == "deterministic"
    assert not out["ok"]
    files = [s["file"] for s in out["suggestions"]]
    assert "esp32_box_with_lid.yaml" in files
    assert out["verification_state"] == "failed"


# -- 8. end-to-end contract -----------------------------------------------------------


def test_intent_yaml_validates_like_handwritten(monkeypatch, catalog):
    from artifact_forge_ng.assembly.pipeline import validate_assembly_doc
    out, _ = _run(monkeypatch, catalog, [canon()])
    doc = yaml.safe_load(out["yaml"])
    asm = AssemblyInstance.model_validate(doc)
    report = validate_assembly_doc(asm, catalog, False)
    assert report["status"] == "pass"
    assert json.dumps(report["assembly_pose"])   # poses serialized


# -- W3: the route (async job, polling) ----------------------------------------------


def _wait_job(client, job_id: str, timeout: float = 15.0) -> dict:
    """Poll /api/jobs/{id} until the job leaves 'running' — the first
    real-thread polling test in this suite, so the timeout is mandatory
    (a hung mock must fail the test, not the CI)."""
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        data = r.json()
        if data.get("status") != "running":
            return data
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} still running after {timeout}s")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from artifact_forge_ng.web.app import app
    return TestClient(app)


def test_route_composes_via_job(monkeypatch, catalog, client):
    _mock_llm(monkeypatch, [canon()])
    r = client.post("/api/assembly/intent", json={"prompt": PROMPT})
    assert r.status_code == 200
    job_id = r.json()["job"]
    done = _wait_job(client, job_id)
    assert done["status"] == "done"
    result = done["result"]
    assert result["ok"] and result["valid"]
    assert result["verification_state"] == "pre_cad_pass"
    assert result["validation"]["assembly_pose"]
    assert any("candidates:" in line for line in done.get("log", []))


def test_route_yaml_flows_through_api_validate(monkeypatch, catalog, client):
    _mock_llm(monkeypatch, [canon()])
    r = client.post("/api/assembly/intent", json={"prompt": PROMPT})
    done = _wait_job(client, r.json()["job"])
    draft_yaml = done["result"]["yaml"]
    v = client.post("/api/validate", json={"yaml": draft_yaml})
    assert v.status_code == 200
    body = v.json()
    assert body.get("ok") is True, body


def test_route_empty_prompt_fails_structured(client):
    r = client.post("/api/assembly/intent", json={"prompt": "  "})
    body = r.json()
    assert body["ok"] is False
    assert body["findings"][0]["check"] == "assembly.intent.input"


def test_route_deterministic_without_key(monkeypatch, client):
    from artifact_forge_ng.web import llm
    monkeypatch.setattr(llm, "available", lambda: False)
    r = client.post("/api/assembly/intent",
                    json={"prompt": "коробка esp32 с крышкой"})
    done = _wait_job(client, r.json()["job"])
    assert done["status"] == "done"
    result = done["result"]
    assert result["source"] == "deterministic"
    assert result["ok"] is False
    assert result["suggestions"]
    assert "Traceback" not in json.dumps(done)


def test_route_llm_runtime_error_falls_back(monkeypatch, client):
    from artifact_forge_ng.web import llm

    def boom(*a, **k):
        raise RuntimeError("LLM call failed: socket")

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "complete", boom)
    r = client.post("/api/assembly/intent",
                    json={"prompt": "коробка esp32 с крышкой"})
    done = _wait_job(client, r.json()["job"])
    assert done["status"] == "done"
    result = done["result"]
    assert result["source"] == "deterministic"
    assert "deterministic fallback" in result["notes"]


def test_non_object_items_are_findings_not_crashes(monkeypatch, catalog):
    """Live-run regression: the model once emitted list items as strings —
    that must surface as schema findings feeding the repair loop, never a
    traceback."""
    mangled = canon()
    mangled["parts"] = ["box", "lid"]                 # strings, not objects
    mangled["shared"] = "wall=2.4mm"
    mangled["wiring"] = "box->lid"          # junk string -> finding
    out, _ = _run(monkeypatch, catalog, [mangled, canon()])
    assert out["valid"], "repair with a good answer must recover"
    assert out["iterations"] == 2


def test_none_marker_wiring_string_is_absence(monkeypatch, catalog):
    """Live-run regression: forced tool calls stuff optional objects with
    "none" strings — an explicit absence marker is absence, not a fail."""
    marked = canon()
    marked["wiring"] = "none"
    out, calls = _run(monkeypatch, catalog, [marked])
    assert len(calls) == 1
    assert out["valid"]
    assert "wiring" not in yaml.safe_load(out["yaml"])


# -- svg asset ("@svg" reference, server-side substitution) --------------------------

#: a printable ring: 40mm square with a 20mm square counter
SQUARE_RING = ("M 0 0 L 40 0 L 40 40 L 0 40 Z "
               "M 10 10 L 30 10 L 30 30 L 10 30 Z")

LAMP_SVG = {
    "id": "svg_lamp", "root": "body", "confidence": "high",
    "notes": "contour lamp with the attached art",
    "parts": [
        {"ref": "body", "archetype_id": "contour_lamp_body_v1", "params": {}},
        {"ref": "face", "archetype_id": "contour_lamp_face_v1",
         "params": {"svg_path": "@svg", "motif_w": "60mm"}},
    ],
    "joints": [
        {"type": "lid_seat",
         "a": {"ref": "body", "kind": "datum", "id": "rim"},
         "b": {"ref": "face", "kind": "datum", "id": "seat"},
         "rotate": [180, 0, 0], "params": {"clearance": 0.3}},
        {"type": "snap_joint",
         "a": {"ref": "body", "kind": "datum", "id": "rim"},
         "b": {"ref": "face", "kind": "datum", "id": "seat"},
         "rotate": [180, 0, 0], "params": {"hooks": "snap"}},
    ],
    "contract_must_have": ["led_light_chamber", "glowing_svg_membrane"],
}


def lamp_svg() -> dict:
    return copy.deepcopy(LAMP_SVG)


def test_svg_marker_substitutes_attached_asset(monkeypatch, catalog):
    """"@svg" in an svg_path_data param resolves to the ATTACHED path in
    the final document; the compact keeps the marker (repair echoes stay
    small, the model never retypes asset data)."""
    _mock_llm(monkeypatch, [lamp_svg()])
    out = assembly_intent.llm_assembly(
        "лампа с моим логотипом", catalog,
        svg_asset=SQUARE_RING, svg_summary="1 outline(s), 1 hole(s)")
    assert out["valid"], out["grounding_findings"]
    doc = yaml.safe_load(out["yaml"])
    face = next(p for p in doc["parts"] if p["ref"] == "face")
    assert face["product"]["params"]["svg_path"] == SQUARE_RING
    assert "@svg" not in out["yaml"]


def test_svg_marker_without_attachment_is_a_fail(monkeypatch, catalog):
    out, _ = _run(monkeypatch, catalog, [lamp_svg(), lamp_svg()],
                  prompt="лампа с логотипом")
    assert any("no SVG asset is attached" in f["message"]
               for f in out["grounding_findings"])
    assert not out["valid"]


def test_svg_marker_on_non_svg_param_is_a_fail(monkeypatch, catalog):
    bad = lamp_svg()
    bad["parts"][1]["params"]["motif_w"] = "@svg"
    _mock_llm(monkeypatch, [bad, bad])
    out = assembly_intent.llm_assembly(
        "лампа", catalog, svg_asset=SQUARE_RING, max_repairs=1)
    assert any("not svg_path_data" in f["message"]
               for f in out["grounding_findings"])


def test_prepare_svg_asset_extracts_and_summarizes():
    svg_doc = f'<svg xmlns="http://www.w3.org/2000/svg"><path d="{SQUARE_RING}"/></svg>'
    path, summary = assembly_intent.prepare_svg_asset(svg_doc)
    outlines, holes, mw = __import__(
        "artifact_forge_ng.form.svg_path", fromlist=["svg_path_to_polygons"]
    ).svg_path_to_polygons(path, 100.0)
    assert len(outlines) == 1 and len(holes) == 1
    assert "1 outline(s)" in summary and "min feature" in summary


def test_route_rejects_broken_svg_up_front(client):
    r = client.post("/api/assembly/intent",
                    json={"prompt": "лампа", "svg": "<svg>no paths</svg>"})
    body = r.json()
    assert body["ok"] is False
    assert any("path" in f["message"] for f in body["findings"])


# -- history: every structured outcome is kept, failed drafts too --------------------


@pytest.fixture(autouse=True)
def tmp_history(monkeypatch, tmp_path):
    """EVERY test writes history into a throwaway file — route tests
    must never pollute the developer's real out/assembly_history.json."""
    from artifact_forge_ng.web import assembly_history
    monkeypatch.setattr(assembly_history, "HISTORY_PATH",
                        tmp_path / "assembly_history.json")
    return assembly_history


def test_history_records_and_lists(tmp_history):
    hid = tmp_history.record("коробка", {
        "yaml": "schema: assembly/v1\nid: box_asm\nparts: [{ref: a}, {ref: b}]",
        "valid": True, "verification_state": "pre_cad_pass",
        "iterations": 1, "source": "llm"})
    metas = tmp_history.list_entries()
    assert [m["id"] for m in metas] == [hid]
    m = metas[0]
    assert m["assembly_id"] == "box_asm" and m["parts"] == 2
    assert m["verification_state"] == "pre_cad_pass" and m["valid"]
    assert "result" not in m                      # metas stay light
    full = tmp_history.get_entry(hid)
    assert full["result"]["yaml"].startswith("schema:")
    assert tmp_history.get_entry("nope") is None


def test_history_keeps_failures_and_caps(tmp_history):
    tmp_history.record("плохой промпт", {"valid": False,
                                         "verification_state": "failed"})
    monkeypatch_cap = 5
    import artifact_forge_ng.web.assembly_history as ah
    old_cap = ah.MAX_ENTRIES
    ah.MAX_ENTRIES = monkeypatch_cap
    try:
        for i in range(8):
            tmp_history.record(f"p{i}", {"valid": False,
                                         "verification_state": "failed"})
    finally:
        ah.MAX_ENTRIES = old_cap
    metas = tmp_history.list_entries()
    assert len(metas) == monkeypatch_cap
    assert metas[0]["prompt"] == "p7"             # newest first
    assert not metas[0]["valid"]                  # failures ARE history


def test_route_records_history(monkeypatch, catalog, client, tmp_history):
    _mock_llm(monkeypatch, [canon()])
    r = client.post("/api/assembly/intent", json={"prompt": PROMPT})
    done = _wait_job(client, r.json()["job"])
    hid = done["result"]["history_id"]
    lst = client.get("/api/assembly/history").json()
    assert lst["ok"] and any(e["id"] == hid for e in lst["entries"])
    entry = client.get(f"/api/assembly/history/{hid}").json()
    assert entry["ok"] and entry["result"]["yaml"] == done["result"]["yaml"]
    missing = client.get("/api/assembly/history/nope").json()
    assert missing["ok"] is False
