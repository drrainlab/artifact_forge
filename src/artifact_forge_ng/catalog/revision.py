"""Content-based catalog fingerprint for the build library.

``catalog_snapshot`` hashes archetypes, modifiers, features and packs
SEPARATELY — a modifier change must not mark unrelated archetypes as
changed, and a device's rebuild-drift chip keys only on the hashes of
the dependencies it actually used.

Deliberately NO caching (and certainly none keyed by ``id(catalog)`` —
a monkeypatched archetype on the same object would return stale hashes):
compute one snapshot per build / per library request and pass it into
every ``drift()`` call. Cost is ~60 pydantic model_dumps, well under
50 ms.
"""
from __future__ import annotations

from typing import Any

from ..util.hashing import stable_hash


def catalog_snapshot(catalog: Any) -> dict[str, Any]:
    """Per-kind content hashes + one combined revision hash."""
    archetypes = {
        aid: stable_hash(spec.model_dump(mode="json"))
        for aid, spec in catalog.archetypes.items()
    }
    modifiers = {
        mid: stable_hash(mod.model_dump(mode="json"))
        for mid, mod in catalog.modifiers.items()
    }
    features = {
        fid: stable_hash(feat.model_dump(mode="json"))
        for fid, feat in catalog.features.items()
    }
    from ..packs import pack_manifests

    packs = {pid: stable_hash(manifest)
             for pid, manifest in pack_manifests().items()}
    body = {"archetypes": archetypes, "modifiers": modifiers,
            "features": features, "packs": packs}
    return {"revision": stable_hash(body), **body}
