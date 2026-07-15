"""The build library: immutable revisions, rebuildable index, integrity.

Every test runs against a tmp_path library root — the real
.artifact-forge/library must never be touched by the suite.
"""
from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import yaml

from artifact_forge_ng.store import registry
from artifact_forge_ng.util.hashing import file_sha256, stable_hash

SNAPSHOT = {
    "revision": "rev-1",
    "archetypes": {"box_v1": "a-hash", "lid_v1": "b-hash"},
    "modifiers": {"add_hex_perforation": "m-hash"},
    "features": {},
    "packs": {},
}

SOURCE = {"schema": "product/v1", "id": "clip", "archetype": "box_v1@1",
          "params": {"w": "20mm"}}


def _fake_out(tmp_path: Path, name: str = "clip") -> Path:
    out = tmp_path / "out" / name
    out.mkdir(parents=True)
    (out / "part.stl").write_bytes(b"solid fake\nendsolid\n")
    (out / "part.step").write_bytes(b"ISO-10303-21;\nEND-ISO-10303-21;\n")
    (out / "findings.yaml").write_text("status: pass\n")
    return out


def _archive(tmp_path: Path, lib: Path, *, device="clip",
             original=b"id: clip\n", out: Path | None = None) -> str:
    return registry.archive_build(
        device_id=device, kind="product", source_doc=dict(SOURCE),
        original_bytes=original,
        out_target=out if out is not None else _fake_out(tmp_path, device),
        status="pass", grade="A", snapshot=SNAPSHOT,
        used_archetypes={"box_v1": 1},
        used_modifiers=["add_hex_perforation"],
        library_root=lib)


def test_bundle_layout_and_manifest(tmp_path):
    lib = tmp_path / "lib"
    bid = _archive(tmp_path, lib, original=b"# comment\nid: clip\r\n")
    bundle = registry.bundle_dir("clip", bid, lib)
    assert (bundle / "part.stl").exists()
    assert (bundle / "source.yaml").exists()
    # exact ORIGINAL bytes — comments, CRLF preserved
    assert (bundle / "source.original.yaml").read_bytes() \
        == b"# comment\nid: clip\r\n"
    manifest = yaml.safe_load((bundle / "manifest.yaml").read_text())
    assert manifest["schema"] == "restore/v1"
    assert manifest["source_digest"] == stable_hash(SOURCE)
    assert manifest["artifact_state"] == "geometry_complete"
    # checksums certify the ARCHIVED copy
    sha, size = file_sha256(bundle / "part.stl")
    assert manifest["exports"]["stl"] == {
        "path": "part.stl", "sha256": sha, "size": size}
    assert manifest["dependencies"]["archetypes"]["box_v1"] == {
        "version": 1, "hash": "a-hash"}
    # canonical source round-trips
    assert yaml.safe_load((bundle / "source.yaml").read_text()) == SOURCE


def test_rebuild_creates_new_revision_and_never_mutates_old(tmp_path):
    lib = tmp_path / "lib"
    first = _archive(tmp_path, lib, out=_fake_out(tmp_path, "clip"))
    before = {p.name: file_sha256(p)[0] for p in
              registry.bundle_dir("clip", first, lib).iterdir()
              if p.is_file()}
    out2 = tmp_path / "out2" / "clip"
    out2.mkdir(parents=True)
    (out2 / "part.stl").write_bytes(b"solid other\nendsolid\n")
    (out2 / "part.step").write_bytes(b"ISO-10303-21;v2\n")
    second = _archive(tmp_path, lib, out=out2)
    assert second != first
    after = {p.name: file_sha256(p)[0] for p in
             registry.bundle_dir("clip", first, lib).iterdir()
             if p.is_file()}
    assert after == before, "previous immutable bundle was touched"
    assert [m["build_id"] for m in registry.revisions("clip", lib)] \
        == [second, first]
    assert registry.list_latest(library_root=lib)[0]["build_id"] == second
    assert registry.list_latest(library_root=lib)[0]["builds"] == 2


def test_build_id_collision_still_two_revisions(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    monkeypatch.setattr(registry, "new_build_id",
                        lambda digest: f"SAMETICK-{digest[:12]}")
    a = _archive(tmp_path, lib, out=_fake_out(tmp_path, "c1"), device="clip")
    out2 = tmp_path / "outB" / "clip"
    out2.mkdir(parents=True)
    (out2 / "part.stl").write_bytes(b"solid x\n")
    b = _archive(tmp_path, lib, out=out2, device="clip")
    assert a != b
    assert len(registry.revisions("clip", lib)) == 2


def test_reindex_restores_lost_registry(tmp_path):
    lib = tmp_path / "lib"
    _archive(tmp_path, lib, device="clip")
    _archive(tmp_path, lib, device="clip", out=_fake_out(tmp_path, "clip2"))
    original = json.loads((lib / "registry.json").read_text())
    (lib / "registry.json").unlink()
    data = registry.reindex_registry(lib)
    assert data["entries"].keys() == original["entries"].keys()
    assert data["latest_by_id"] == original["latest_by_id"]
    # and lazy recovery on read
    (lib / "registry.json").write_text("{broken json")
    assert len(registry.list_latest(library_root=lib)) == 1


def test_corrupt_stl_detected_source_still_opens(tmp_path):
    lib = tmp_path / "lib"
    bid = _archive(tmp_path, lib)
    bundle = registry.bundle_dir("clip", bid, lib)
    manifest = registry.get_build("clip", bid, lib)
    assert registry.verify_artifacts(manifest, bundle)["state"] == "intact"
    # flip one byte
    raw = bytearray((bundle / "part.stl").read_bytes())
    raw[3] ^= 0xFF
    (bundle / "part.stl").write_bytes(bytes(raw))
    verdict = registry.verify_artifacts(manifest, bundle)
    assert verdict["state"] == "damaged" and verdict["bad"] == ["part.stl"]
    # the source seed is untouched by geometry damage
    assert registry.read_source("clip", bid, lib).startswith("schema:")
    # cheap presence check does not catch same-size corruption — honest:
    # it only guards existence+size; sha runs on open
    assert registry.artifacts_present(manifest, bundle)["state"] == "intact"


def test_source_only_state_when_no_geometry(tmp_path):
    lib = tmp_path / "lib"
    out = tmp_path / "out" / "ghost"
    out.mkdir(parents=True)          # a failed build: no exports at all
    bid = registry.archive_build(
        device_id="ghost", kind="product", source_doc=dict(SOURCE),
        original_bytes=b"x", out_target=out, status="fail", grade="F",
        snapshot=SNAPSHOT, used_archetypes={"box_v1": 1},
        used_modifiers=[], library_root=lib)
    manifest = registry.get_build("ghost", bid, lib)
    assert manifest["artifact_state"] == "source_only"
    assert registry.verify_artifacts(
        manifest, registry.bundle_dir("ghost", bid, lib))["state"] == "none"


def test_drift_keys_only_on_used_dependencies(tmp_path):
    lib = tmp_path / "lib"
    bid = _archive(tmp_path, lib)
    manifest = registry.get_build("clip", bid, lib)
    # unrelated archetype changed -> inputs unchanged, detail notes it
    unrelated = dict(SNAPSHOT, revision="rev-2",
                     archetypes=dict(SNAPSHOT["archetypes"], lid_v1="CHANGED"))
    d = registry.drift(manifest, unrelated)
    assert not d["inputs_changed"]
    assert d["unrelated_catalog_changes"] is True
    assert d["changed_archetypes"] == []
    # the USED archetype changed -> precise input drift
    used = dict(SNAPSHOT, revision="rev-3",
                archetypes=dict(SNAPSHOT["archetypes"], box_v1="CHANGED"))
    d2 = registry.drift(manifest, used)
    assert d2["inputs_changed"] and d2["changed_archetypes"] == ["box_v1"]
    assert d2["unrelated_catalog_changes"] is False
    # used archetype REMOVED from the catalog
    gone = dict(SNAPSHOT, revision="rev-4", archetypes={"lid_v1": "b-hash"})
    assert registry.drift(manifest, gone)["missing_archetypes"] == ["box_v1"]
    # used modifier changed
    mod = dict(SNAPSHOT, revision="rev-5",
               modifiers={"add_hex_perforation": "CHANGED"})
    assert registry.drift(manifest, mod)["changed_modifiers"] \
        == ["add_hex_perforation"]


def test_drift_reports_cad_env_separately(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    bid = _archive(tmp_path, lib)
    manifest = registry.get_build("clip", bid, lib)
    newer = dict(manifest["tool"], cadquery="9.9.9", af_commit="deadbee")
    monkeypatch.setattr(registry, "tool_versions", lambda: newer)
    d = registry.drift(manifest, SNAPSHOT)
    assert list(d["cad_env_changed"]) == ["cadquery"]
    assert list(d["af_changed"]) == ["af_commit"]
    assert not d["inputs_changed"]          # axes stay independent


def _archive_in_proc(args) -> str:
    lib_str, device, out_str = args
    return registry.archive_build(
        device_id=device, kind="product", source_doc=dict(SOURCE),
        original_bytes=b"x", out_target=Path(out_str), status="pass",
        grade="A", snapshot=SNAPSHOT, used_archetypes={"box_v1": 1},
        used_modifiers=[], library_root=Path(lib_str))


def test_concurrent_processes_both_recorded(tmp_path):
    lib = tmp_path / "lib"
    outs = []
    for name in ("p1", "p2"):
        out = tmp_path / name / "dev"
        out.mkdir(parents=True)
        (out / "part.stl").write_bytes(b"solid " + name.encode())
        outs.append(str(out))
    with multiprocessing.get_context("spawn").Pool(2) as pool:
        bids = pool.map(_archive_in_proc,
                        [(str(lib), "dev", o) for o in outs])
    data = json.loads((lib / "registry.json").read_text())   # valid JSON
    assert set(bids) <= set(data["entries"])
    assert len(set(bids)) == 2
