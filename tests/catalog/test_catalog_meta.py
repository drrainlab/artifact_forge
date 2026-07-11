"""CatalogMeta — the presentation-only shelving block: strict schema,
loader-derived domains and relative source paths."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.product.archetype import CatalogMeta


def test_defaults_are_empty_and_core():
    m = CatalogMeta()
    assert m.domain == "core" and m.tier == "free" and m.kind == "archetype"
    assert m.modes == [] and m.tags == [] and m.claims == {}


def test_domain_is_a_free_string():
    assert CatalogMeta(domain="camera-rigs").domain == "camera-rigs"


def test_invalid_mode_tier_kind_rejected():
    with pytest.raises(ValidationError):
        CatalogMeta(modes=["turbo"])
    with pytest.raises(ValidationError):
        CatalogMeta(tier="platinum")
    with pytest.raises(ValidationError):
        CatalogMeta(kind="family")
    with pytest.raises(ValidationError):
        CatalogMeta(unknown_key=1)


def test_loader_fills_domains_and_relpaths():
    c = load_catalog()
    # every archetype has a domain and a RELATIVE source path
    for aid in c.archetypes:
        assert c.domains.get(aid), aid
        rel = c.source_relpaths.get(aid, "")
        assert rel and not rel.startswith("/"), (aid, rel)
    # builtin annotation wins
    assert c.domains["cable_comb_v1"] == "studio"


def test_pack_subdir_is_the_domain_fallback():
    """A pack archetype without an explicit domain shelves under its
    archetypes/<domain>/ subdirectory (showcase files carry explicit
    domains that MATCH their subdirs — assert the invariant)."""
    c = load_catalog()
    for aid, origin in c.origins.items():
        if origin != "pack:showcase":
            continue
        rel = c.source_relpaths[aid]
        parts = rel.split("/")
        assert parts[0] == "archetypes" and len(parts) == 3, rel
        assert c.domains[aid] == parts[1], (aid, rel, c.domains[aid])
