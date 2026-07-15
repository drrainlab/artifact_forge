"""Device-level builds land in the library as immutable revisions;
assembly sub-parts never get their own entries; the archived source
round-trips through a rebuild."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.assembly.pipeline import run_assembly_build  # noqa: E402
from artifact_forge_ng.compiler.pipeline import run_build  # noqa: E402
from artifact_forge_ng.store import registry  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture(autouse=True)
def tmp_library(monkeypatch, tmp_path):
    """NEVER touch the real .artifact-forge/library from the suite."""
    lib = tmp_path / "library"
    monkeypatch.setattr(registry, "LIBRARY_ROOT", lib)
    return lib


def test_product_build_archives_immutable_bundle(tmp_path, tmp_library):
    out = run_build(EXAMPLES / "drawer_handle_110.yaml", tmp_path / "out", None)
    bid = out["build_id"]
    assert bid
    entries = registry.list_latest(library_root=tmp_library)
    assert len(entries) == 1
    meta = entries[0]
    assert meta["kind"] == "product" and meta["build_id"] == bid
    device_id = meta["id"]
    bundle = registry.bundle_dir(device_id, bid, tmp_library)
    manifest = registry.get_build(device_id, bid, tmp_library)
    # geometry archived + integrity holds on the archived copy
    assert manifest["artifact_state"] == "geometry_complete"
    assert registry.verify_artifacts(manifest, bundle)["state"] == "intact"
    # original bytes are the exact input file
    assert (bundle / "source.original.yaml").read_bytes() \
        == (EXAMPLES / "drawer_handle_110.yaml").read_bytes()
    # used deps recorded precisely
    assert list(manifest["dependencies"]["archetypes"]) \
        == [yaml.safe_load((bundle / "source.yaml").read_text())
            ["archetype"].split("@")[0]]


def test_archived_source_rebuilds_same_grade(tmp_path, tmp_library):
    first = run_build(EXAMPLES / "drawer_handle_110.yaml",
                      tmp_path / "o1", None)
    meta = registry.list_latest(library_root=tmp_library)[0]
    src = registry.bundle_dir(meta["id"], first["build_id"],
                              tmp_library) / "source.yaml"
    second = run_build(src, tmp_path / "o2", None)
    assert second["status"] == first["status"]
    assert second["score"]["grade"] == first["score"]["grade"]
    # the rebuild archived a NEW revision; the first bundle is untouched
    revs = registry.revisions(meta["id"], library_root=tmp_library)
    assert len(revs) == 2
    assert registry.verify_artifacts(
        registry.get_build(meta["id"], first["build_id"], tmp_library),
        registry.bundle_dir(meta["id"], first["build_id"], tmp_library),
    )["state"] == "intact"


def test_assembly_archives_one_bundle_no_subpart_entries(tmp_path,
                                                         tmp_library):
    report = run_assembly_build(EXAMPLES / "esp32_box_with_lid.yaml",
                                tmp_path / "out", None)
    bid = report["build_id"]
    entries = registry.list_latest(library_root=tmp_library)
    # ONE device entry — the box/lid sub-parts live inside the bundle
    assert [e["kind"] for e in entries] == ["assembly"]
    device_id = entries[0]["id"]
    manifest = registry.get_build(device_id, bid, tmp_library)
    assert set(manifest["exports"]["parts"]) == {"box", "lid"}
    assert manifest["artifact_state"] == "geometry_complete"
    assert len(manifest["dependencies"]["archetypes"]) == 2
    bundle = registry.bundle_dir(device_id, bid, tmp_library)
    assert registry.verify_artifacts(manifest, bundle)["state"] == "intact"
    # the archived assembly source revalidates as-is
    doc = yaml.safe_load((bundle / "source.yaml").read_text())
    from artifact_forge_ng.product.assembly import AssemblyInstance
    AssemblyInstance.model_validate(doc)
