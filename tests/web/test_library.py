"""Library API: list with three axes, revision detail, the controlled
artifact endpoint (allowlist + containment), reopen flow.

The suite-wide conftest fixture already redirects LIBRARY_ROOT to
tmp_path; entries here are seeded directly through registry.archive_build
(no CAD needed)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.catalog.revision import catalog_snapshot
from artifact_forge_ng.store import registry

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture(scope="module")
def snapshot():
    return catalog_snapshot(load_catalog())


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from artifact_forge_ng.web.app import app
    return TestClient(app)


def _seed(tmp_path: Path, snapshot, *, device: str | None = None
          ) -> tuple[str, str]:
    """A realistic library entry: the REAL esp32 example as source, a
    fake geometry tree (integrity math needs bytes, not CAD). The device
    id is UNIQUE per test — the suite shares one session library, so a
    fixed id would couple these asserts to whatever built earlier."""
    import uuid

    device = device or f"esp32_seed_{uuid.uuid4().hex[:8]}"
    original = (EXAMPLES / "esp32_box_with_lid.yaml").read_bytes()
    doc = yaml.safe_load(original)
    out = tmp_path / "fakeout" / device
    for ref in ("box", "lid"):
        (out / ref).mkdir(parents=True, exist_ok=True)
        (out / ref / "part.stl").write_bytes(b"solid " + ref.encode())
        (out / ref / "part.step").write_bytes(b"STEP " + ref.encode())
    (out / "assembled.step").write_bytes(b"STEP assembled")
    (out / "bom.yaml").write_text("printed_parts: []\n")
    return device, registry.archive_build(
        device_id=device, kind="assembly", source_doc=doc,
        original_bytes=original, out_target=out, status="pass", grade="A",
        snapshot=snapshot,
        used_archetypes={"enclosure_base_v1": 1, "enclosure_lid_v1": 1},
        used_modifiers=[])


def test_list_has_three_axes_and_green_state(client, tmp_path, snapshot):
    dev, bid = _seed(tmp_path, snapshot)
    body = client.get("/api/library?limit=100").json()
    assert body["ok"]
    entry = next(e for e in body["entries"] if e["build_id"] == bid)
    assert entry["kind"] == "assembly" and entry["builds"] == 1
    assert entry["artifacts"]["state"] == "intact"
    assert not entry["drift"]["inputs_changed"]
    assert entry["drift"]["cad_env_changed"] == {}


def test_device_and_build_detail_with_full_integrity(client, tmp_path,
                                                     snapshot):
    device, bid = _seed(tmp_path, snapshot)
    dev = client.get(f"/api/library/{device}").json()
    assert dev["ok"] and dev["latest"]["build_id"] == bid
    detail = client.get(f"/api/library/{device}/{bid}").json()
    assert detail["ok"]
    assert detail["integrity"]["state"] == "intact"
    assert detail["manifest"]["schema"] == "restore/v1"
    # the archived source revalidates through the ordinary pipeline
    v = client.post("/api/validate", json={"yaml": detail["source"]})
    assert v.json().get("ok") is True
    # the exact original bytes ride along
    assert detail["original"] == (
        EXAMPLES / "esp32_box_with_lid.yaml").read_text()
    assert client.get("/api/library/nope").json()["ok"] is False
    assert client.get(
        f"/api/library/{device}/nope").json()["ok"] is False


def test_artifact_route_allowlist_and_containment(client, tmp_path,
                                                  snapshot):
    device, bid = _seed(tmp_path, snapshot)
    base = f"/api/library/{device}/{bid}/artifact"
    ok = client.get(f"{base}/box/part.stl")
    assert ok.status_code == 200 and ok.content == b"solid box"
    # NOT exported -> refused (source, manifest, reports stay private)
    for private in ("source.yaml", "manifest.yaml", "source.original.yaml"):
        assert client.get(f"{base}/{private}").json()["ok"] is False
    # encoded traversal -> refused by the allowlist before any fs access
    sneak = client.get(f"{base}/%2e%2e%2f%2e%2e%2fsource.yaml")
    assert sneak.status_code in (404, 200)
    if sneak.status_code == 200:
        assert sneak.json()["ok"] is False


def test_catalog_drift_does_not_block_exact_reopen(client, tmp_path,
                                                   snapshot):
    """Axis independence end-to-end: a stale used-archetype hash makes
    the rebuild axis amber while artifacts stay intact and servable."""
    stale = dict(snapshot,
                 archetypes=dict(snapshot["archetypes"],
                                 enclosure_base_v1="STALE"))
    device, bid = _seed(tmp_path, stale)
    entry = next(e for e in
                 client.get("/api/library?limit=100").json()["entries"]
                 if e["build_id"] == bid)
    assert entry["drift"]["inputs_changed"]
    assert entry["drift"]["changed_archetypes"] == ["enclosure_base_v1"]
    assert entry["artifacts"]["state"] == "intact"
    served = client.get(
        f"/api/library/{device}/{bid}/artifact/box/part.stl")
    assert served.status_code == 200 and served.content == b"solid box"
