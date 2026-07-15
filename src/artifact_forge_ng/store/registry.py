"""The build library: every device build is archived as an IMMUTABLE
revision bundle with full provenance, and can be reopened byte-exact or
rebuilt (drift-checked) later.

Storage model:

    .artifact-forge/library/
      registry.json          # accelerating index — REBUILDABLE, never
      registry.lock          # the only truth (see reindex_registry)
      <device_id>/<build_id>/
        source.yaml            canonical rebuild seed (model_dump round-trip)
        source.original.yaml   exact input BYTES as the user wrote them
        manifest.yaml          provenance + per-file integrity (truth for reindex)
        ... full copy of the build output tree (STL/STEP/reports/BOM)

Invariants:
- a bundle is never overwritten or mutated: checksums are computed on the
  ARCHIVED copy inside the tmp dir, the manifest is written there, then
  the dir is atomically renamed into place;
- ``build_id`` = UTC timestamp with microseconds + source digest prefix,
  plus an existence guard — two builds of the same source in the same
  instant still yield distinct revisions;
- registry updates run under a cross-process lockfile; a lost or corrupt
  registry.json is rebuilt from the bundle manifests.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml

from ..util.hashing import file_sha256, stable_hash

REPO_ROOT = Path(__file__).resolve().parents[3]
LIBRARY_ROOT = REPO_ROOT / ".artifact-forge" / "library"

#: files integrity-tracked in manifests (geometry + BOM); reports are
#: archived too but are not part of the byte-exact reopen contract
_PRODUCT_EXPORTS = {"stl": "part.stl", "step": "part.step"}
_ASSEMBLY_EXPORTS = {"assembled_step": "assembled.step", "bom": "bom.yaml"}

_LOCK_STALE_S = 30.0
_LOCK_WAIT_S = 10.0



def _root(library_root: Path | None) -> Path:
    """Resolve at CALL time so tests/overrides can repoint LIBRARY_ROOT."""
    return library_root if library_root is not None else LIBRARY_ROOT


# -- tool provenance ---------------------------------------------------------------


def _dist_version(name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(name)
    except Exception:  # noqa: BLE001 — absent dist is a fact, not an error
        return None


def _git_commit() -> str | None:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=3)
        return res.stdout.strip() or None if res.returncode == 0 else None
    except Exception:  # noqa: BLE001 — no git, no .git dir: best-effort
        return None


def tool_versions() -> dict[str, Any]:
    import platform as _platform

    from .. import __version__

    return {
        "af_version": __version__,
        "af_commit": _git_commit(),
        "python": _platform.python_version(),
        "cadquery": _dist_version("cadquery"),
        "cadquery_ocp": _dist_version("cadquery-ocp"),
        "platform": _platform.platform(terse=True),
    }


#: geometry-relevant tool keys: the CAD-environment chip keys on these;
#: af_version/af_commit changes are surfaced separately (dev checkouts
#: change commit constantly — that is code drift, reported as detail)
_CAD_ENV_KEYS = ("python", "cadquery", "cadquery_ocp", "platform")


# -- registry index (rebuildable) ----------------------------------------------------


@contextmanager
def _locked(library_root: Path) -> Iterator[None]:
    """Cross-process create-exclusive lockfile with stale-steal. The
    registry is a rebuildable index, so after the wait deadline we steal
    rather than fail the build."""
    library_root.mkdir(parents=True, exist_ok=True)
    lock = library_root / "registry.lock"
    deadline = time.time() + _LOCK_WAIT_S
    fd = None
    while fd is None:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                stale = time.time() - lock.stat().st_mtime > _LOCK_STALE_S
            except OSError:
                stale = False
            if stale or time.time() > deadline:
                lock.unlink(missing_ok=True)
                continue
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


def _registry_path(library_root: Path) -> Path:
    return library_root / "registry.json"


def _load_registry(library_root: Path) -> dict[str, Any]:
    try:
        data = json.loads(_registry_path(library_root).read_text())
        if isinstance(data, dict) and "entries" in data:
            return data
    except (OSError, ValueError):
        pass
    return {"entries": {}, "latest_by_id": {}}


def _store_registry(library_root: Path, data: dict[str, Any]) -> None:
    path = _registry_path(library_root)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


def _meta_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    deps = manifest.get("dependencies") or {}
    return {
        "build_id": manifest.get("build_id"),
        "id": manifest.get("id"),
        "kind": manifest.get("kind"),
        "ts": manifest.get("ts"),
        "grade": manifest.get("grade"),
        "status": manifest.get("status"),
        "source_digest": manifest.get("source_digest"),
        "catalog_revision": manifest.get("catalog_revision"),
        "artifact_state": manifest.get("artifact_state"),
        "archetypes": sorted((deps.get("archetypes") or {})),
        "parts": manifest.get("parts"),
    }


def reindex_registry(library_root: Path | None = None) -> dict[str, Any]:
    """Rebuild registry.json from the bundle manifests — the bundles are
    the source of truth; the index is only an accelerator. Invoked when
    the index is missing or corrupt, and usable as a manual recovery."""
    library_root = _root(library_root)
    entries: dict[str, Any] = {}
    latest: dict[str, str] = {}
    if library_root.exists():
        for manifest_path in sorted(library_root.glob("*/*/manifest.yaml")):
            if manifest_path.parent.name.startswith(".tmp-"):
                continue
            try:
                manifest = yaml.safe_load(manifest_path.read_text()) or {}
            except (OSError, yaml.YAMLError):
                continue
            build_id = manifest.get("build_id") or manifest_path.parent.name
            device_id = manifest.get("id") or manifest_path.parent.parent.name
            entries[build_id] = _meta_from_manifest(manifest)
            # build ids sort chronologically — the max is the latest
            if latest.get(device_id, "") < build_id:
                latest[device_id] = build_id
    data = {"entries": entries, "latest_by_id": latest}
    with _locked(library_root):
        _store_registry(library_root, data)
    return data


def _registry(library_root: Path) -> dict[str, Any]:
    """Load the index, rebuilding it from manifests when absent/corrupt."""
    path = _registry_path(library_root)
    if not path.exists():
        return reindex_registry(library_root)
    data = _load_registry(library_root)
    if not data["entries"] and any(library_root.glob("*/*/manifest.yaml")):
        return reindex_registry(library_root)   # corrupt index, real bundles
    return data


# -- archiving ------------------------------------------------------------------


def _iter_export_files(exports: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Flatten the (possibly nested per-part) exports map into file rows."""
    for value in exports.values():
        if not isinstance(value, dict):
            continue
        if "path" in value:
            yield value
        else:   # parts: {ref: {stl: {...}, step: {...}}}
            for sub in value.values():
                if isinstance(sub, dict):
                    yield from _iter_export_files(sub) if "path" not in sub \
                        else iter([sub])


def _hash_export(bundle: Path, rel: str) -> dict[str, Any] | None:
    path = bundle / rel
    if not path.exists():
        return None
    sha, size = file_sha256(path)
    return {"path": rel, "sha256": sha, "size": size}


def _collect_exports(bundle: Path, kind: str) -> tuple[dict[str, Any], str]:
    """Integrity-hash the geometry INSIDE the archived bundle (never the
    out/ source — the manifest certifies the copy) and derive the
    artifact state honestly from what actually exists."""
    exports: dict[str, Any] = {}
    expected = 0
    found = 0
    if kind == "product":
        for key, rel in _PRODUCT_EXPORTS.items():
            expected += 1
            row = _hash_export(bundle, rel)
            if row:
                exports[key] = row
                found += 1
    else:
        for key, rel in _ASSEMBLY_EXPORTS.items():
            expected += 1
            row = _hash_export(bundle, rel)
            if row:
                exports[key] = row
                found += 1
        parts: dict[str, Any] = {}
        for ref_dir in sorted(p for p in bundle.iterdir()
                              if p.is_dir() and not p.name.startswith(".")):
            part_rows: dict[str, Any] = {}
            for key, name in _PRODUCT_EXPORTS.items():
                expected += 1
                row = _hash_export(bundle, f"{ref_dir.name}/{name}")
                if row:
                    part_rows[key] = row
                    found += 1
            if part_rows:
                parts[ref_dir.name] = part_rows
        if parts:
            exports["parts"] = parts
    state = ("source_only" if found == 0
             else "geometry_complete" if found == expected
             else "geometry_partial")
    return exports, state


def new_build_id(source_digest: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{ts}-{source_digest[:12]}"


def archive_build(
    *,
    device_id: str,
    kind: str,
    source_doc: dict[str, Any],
    original_bytes: bytes,
    out_target: Path,
    status: str,
    grade: str | None,
    snapshot: dict[str, Any],
    used_archetypes: dict[str, int | None],
    used_modifiers: list[str],
    library_root: Path | None = None,
) -> str:
    """Archive one build as an immutable revision; returns the build_id.

    ``original_bytes`` are written verbatim (``write_bytes`` — BOM and
    newlines preserved); the canonical ``source.yaml`` comes from the
    already-validated ``source_doc`` dict (the edit.py round-trip)."""
    library_root = _root(library_root)
    source_digest = stable_hash(source_doc)
    build_id = new_build_id(source_digest)
    device_dir = library_root / device_id
    device_dir.mkdir(parents=True, exist_ok=True)

    tmp = device_dir / f".tmp-{build_id}-{uuid.uuid4().hex[:6]}"
    if out_target.exists():
        shutil.copytree(out_target, tmp)
    else:
        tmp.mkdir()
    (tmp / "source.yaml").write_text(
        yaml.safe_dump(source_doc, sort_keys=False, allow_unicode=True))
    (tmp / "source.original.yaml").write_bytes(original_bytes)

    exports, artifact_state = _collect_exports(tmp, kind)
    import hashlib

    manifest: dict[str, Any] = {
        "schema": "restore/v1",
        "build_id": build_id,
        "kind": kind,
        "id": device_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "grade": grade,
        "parts": (len(source_doc.get("parts") or []) or 1
                  if kind == "assembly" else 1),
        "source_digest": source_digest,
        "source_bytes_digest": hashlib.sha256(original_bytes).hexdigest(),
        "catalog_revision": snapshot["revision"],
        "dependencies": {
            "archetypes": {
                aid: {"version": ver,
                      "hash": snapshot["archetypes"].get(aid)}
                for aid, ver in sorted(used_archetypes.items())
            },
            "modifiers": {
                mid: {"hash": snapshot["modifiers"].get(mid)}
                for mid in sorted(set(used_modifiers))
            },
        },
        "tool": tool_versions(),
        "artifact_state": artifact_state,
        "exports": exports,
    }
    manifest_path = tmp / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
    try:   # fsync where practical: the manifest is the reindex truth
        with open(manifest_path, "rb+") as fh:
            os.fsync(fh.fileno())
    except OSError:
        pass

    final = device_dir / build_id
    if final.exists():
        # same source archived twice within one microsecond tick — still
        # a distinct immutable revision
        build_id = f"{build_id}-{uuid.uuid4().hex[:4]}"
        manifest["build_id"] = build_id
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
        final = device_dir / build_id
    os.rename(tmp, final)

    with _locked(library_root):
        data = _load_registry(library_root)
        data["entries"][build_id] = _meta_from_manifest(manifest)
        if data["latest_by_id"].get(device_id, "") < build_id:
            data["latest_by_id"][device_id] = build_id
        _store_registry(library_root, data)
    return build_id


# -- reading --------------------------------------------------------------------


def list_latest(limit: int = 50,
                library_root: Path | None = None) -> list[dict[str, Any]]:
    """Newest-first latest revision per device + total builds count."""
    data = _registry(_root(library_root))
    counts: dict[str, int] = {}
    for meta in data["entries"].values():
        counts[meta.get("id", "")] = counts.get(meta.get("id", ""), 0) + 1
    latest = [dict(data["entries"][bid], builds=counts.get(did, 1))
              for did, bid in data["latest_by_id"].items()
              if bid in data["entries"]]
    latest.sort(key=lambda m: m.get("build_id", ""), reverse=True)
    return latest[:limit]


def revisions(device_id: str,
              library_root: Path | None = None) -> list[dict[str, Any]]:
    data = _registry(_root(library_root))
    revs = [m for m in data["entries"].values() if m.get("id") == device_id]
    revs.sort(key=lambda m: m.get("build_id", ""), reverse=True)
    return revs


def bundle_dir(device_id: str, build_id: str,
               library_root: Path | None = None) -> Path:
    return _root(library_root) / device_id / build_id


def get_build(device_id: str, build_id: str,
              library_root: Path | None = None) -> dict[str, Any] | None:
    """Full manifest of one archived revision (truth read from the
    bundle, not the index)."""
    path = bundle_dir(device_id, build_id, library_root) / "manifest.yaml"
    try:
        manifest = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError):
        return None
    return manifest if isinstance(manifest, dict) else None


def read_source(device_id: str, build_id: str,
                library_root: Path | None = None) -> str | None:
    path = bundle_dir(device_id, build_id, library_root) / "source.yaml"
    try:
        return path.read_text()
    except OSError:
        return None


def read_original(device_id: str, build_id: str,
                  library_root: Path | None = None) -> str | None:
    path = (bundle_dir(device_id, build_id, library_root)
            / "source.original.yaml")
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


# -- the three status axes ------------------------------------------------------


def drift(manifest: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Rebuild-input + CAD-environment drift vs the CURRENT catalog.

    The rebuild verdict keys ONLY on the dependencies this device used —
    a global revision mismatch caused by an unrelated archetype is
    reported separately, never as input drift."""
    deps = manifest.get("dependencies") or {}
    changed_archetypes, missing_archetypes = [], []
    for aid, info in (deps.get("archetypes") or {}).items():
        current = snapshot["archetypes"].get(aid)
        if current is None:
            missing_archetypes.append(aid)
        elif current != (info or {}).get("hash"):
            changed_archetypes.append(aid)
    changed_modifiers = [
        mid for mid, info in (deps.get("modifiers") or {}).items()
        if snapshot["modifiers"].get(mid) != (info or {}).get("hash")
    ]
    inputs_changed = bool(changed_archetypes or missing_archetypes
                          or changed_modifiers)
    revision_changed = manifest.get("catalog_revision") != snapshot["revision"]

    tool_now = tool_versions()
    tool_was = manifest.get("tool") or {}
    tool_changed = {
        k: {"was": tool_was.get(k), "now": tool_now.get(k)}
        for k in _CAD_ENV_KEYS if tool_was.get(k) != tool_now.get(k)
    }
    af_changed = {
        k: {"was": tool_was.get(k), "now": tool_now.get(k)}
        for k in ("af_version", "af_commit")
        if tool_was.get(k) != tool_now.get(k)
    }
    return {
        "inputs_changed": inputs_changed,
        "changed_archetypes": sorted(changed_archetypes),
        "missing_archetypes": sorted(missing_archetypes),
        "changed_modifiers": sorted(changed_modifiers),
        # unrelated catalog edits: informational detail, NOT input drift
        "unrelated_catalog_changes": revision_changed and not inputs_changed,
        "cad_env_changed": tool_changed,
        "af_changed": af_changed,
    }


def export_paths(manifest: dict[str, Any]) -> set[str]:
    """The allowlist for serving bundle files over HTTP: ONLY paths the
    manifest exports — never source/manifest/reports."""
    return {row["path"]
            for row in _iter_export_files(manifest.get("exports") or {})}


def verify_artifacts(manifest: dict[str, Any],
                     bundle: Path) -> dict[str, Any]:
    """Full sha256 verification of every export in the ARCHIVED bundle."""
    rows = list(_iter_export_files(manifest.get("exports") or {}))
    if not rows:
        return {"state": "none", "bad": []}
    bad: list[str] = []
    for row in rows:
        path = bundle / row["path"]
        if not path.exists():
            bad.append(row["path"])
            continue
        sha, size = file_sha256(path)
        if sha != row.get("sha256") or size != row.get("size"):
            bad.append(row["path"])
    return {"state": "intact" if not bad else "damaged", "bad": sorted(bad)}


def artifacts_present(manifest: dict[str, Any],
                      bundle: Path) -> dict[str, Any]:
    """Cheap existence+size check for list views (full sha on open)."""
    rows = list(_iter_export_files(manifest.get("exports") or {}))
    if not rows:
        return {"state": "none", "bad": []}
    bad = [row["path"] for row in rows
           if not (bundle / row["path"]).exists()
           or (bundle / row["path"]).stat().st_size != row.get("size")]
    return {"state": "intact" if not bad else "damaged", "bad": sorted(bad)}
