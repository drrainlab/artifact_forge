"""Persistent history of prompt->assembly runs — EVERY structured
outcome is kept, failed drafts included: a draft that lost to validation
is still the user's work (and the repair findings that killed it are
part of the story). One JSON file under out/, atomic writes, bounded.

The stored ``result`` is the exact object the intent job returned, so
reopening a history entry rebuilds the draft screen with no extra
server work — the UI re-validates only when the user edits.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
HISTORY_PATH = REPO_ROOT / "out" / "assembly_history.json"

#: bounded: the newest MAX_ENTRIES survive, the tail is dropped on write
MAX_ENTRIES = 100

_lock = threading.Lock()


def _load() -> list[dict[str, Any]]:
    try:
        data = json.loads(HISTORY_PATH.read_text())
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _store(entries: list[dict[str, Any]]) -> None:
    HISTORY_PATH.parent.mkdir(exist_ok=True)
    tmp = HISTORY_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False))
    tmp.replace(HISTORY_PATH)


def _meta(entry: dict[str, Any]) -> dict[str, Any]:
    """The list view: everything the picker needs, no draft bodies."""
    result = entry.get("result") or {}
    return {
        "id": entry.get("id"),
        "ts": entry.get("ts"),
        "prompt": entry.get("prompt", ""),
        "svg_attached": bool(entry.get("svg_attached")),
        "source": result.get("source"),
        "verification_state": result.get("verification_state", "failed"),
        "valid": bool(result.get("valid")),
        "iterations": result.get("iterations"),
        "assembly_id": entry.get("assembly_id"),
        "parts": entry.get("parts"),
    }


def _draft_shape(result: dict[str, Any]) -> tuple[str | None, int | None]:
    """(assembly id, part count) parsed once at record time — the list
    endpoint must not re-parse fifty drafts on every poll."""
    text = result.get("yaml")
    if not text:
        return None, None
    try:
        import yaml as _yaml

        doc = _yaml.safe_load(text)
        return doc.get("id"), len(doc.get("parts", []) or [])
    except Exception:  # noqa: BLE001 — a broken draft is still history
        return None, None


def record(prompt: str, result: dict[str, Any], *,
           svg_attached: bool = False) -> str:
    """Append one run (success OR failure) and return its history id."""
    assembly_id, parts = _draft_shape(result)
    entry = {
        "id": uuid.uuid4().hex[:12],
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt": prompt,
        "svg_attached": svg_attached,
        "assembly_id": assembly_id,
        "parts": parts,
        "result": result,
    }
    with _lock:
        entries = _load()
        entries.insert(0, entry)
        _store(entries[:MAX_ENTRIES])
    return entry["id"]


def list_entries(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        return [_meta(e) for e in _load()[:limit]]


def get_entry(history_id: str) -> dict[str, Any] | None:
    with _lock:
        for e in _load():
            if e.get("id") == history_id:
                return e
    return None
