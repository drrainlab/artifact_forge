"""catalog_snapshot: content-based, per-kind isolated, uncached."""
from __future__ import annotations

import pytest

from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.catalog.revision import catalog_snapshot


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_snapshot_is_deterministic_and_complete(catalog):
    a = catalog_snapshot(catalog)
    b = catalog_snapshot(catalog)
    assert a == b
    assert set(a["archetypes"]) == set(catalog.archetypes)
    assert set(a["modifiers"]) == set(catalog.modifiers)
    assert set(a["features"]) == set(catalog.features)
    assert a["revision"]


def test_archetype_change_isolated_no_stale_cache(catalog):
    """The same catalog OBJECT with a mutated archetype must produce a
    fresh snapshot (this is exactly why there is no id(catalog) cache)."""
    before = catalog_snapshot(catalog)
    spec = catalog.archetypes["enclosure_base_v1"]
    old = spec.description
    try:
        object.__setattr__(spec, "description", old + " CHANGED")
        after = catalog_snapshot(catalog)
    finally:
        object.__setattr__(spec, "description", old)
    assert after["revision"] != before["revision"]
    assert after["archetypes"]["enclosure_base_v1"] \
        != before["archetypes"]["enclosure_base_v1"]
    # every OTHER archetype hash is untouched — per-kind precision
    same = {k: v for k, v in after["archetypes"].items()
            if k != "enclosure_base_v1"}
    assert same == {k: v for k, v in before["archetypes"].items()
                    if k != "enclosure_base_v1"}
    assert after["modifiers"] == before["modifiers"]


def test_modifier_change_does_not_mark_archetypes(catalog):
    before = catalog_snapshot(catalog)
    mod = next(iter(catalog.modifiers.values()))
    old = mod.description
    try:
        object.__setattr__(mod, "description", old + " CHANGED")
        after = catalog_snapshot(catalog)
    finally:
        object.__setattr__(mod, "description", old)
    assert after["revision"] != before["revision"]
    assert after["archetypes"] == before["archetypes"]
    assert after["modifiers"] != before["modifiers"]
