"""Wave G4: coverage-aware candidate retrieval + the assembly digest.

Retrieval is deterministic and role-covering — the flagship prompt must
surface at least one archetype per mandatory functional role, and the
limit is a hard cap under any prompt. The digest is a pure function of
(catalog, part_ids): registry-derived, no hand-curated prose to drift.
"""

from __future__ import annotations

import pytest

from artifact_forge_ng.catalog.grounding import (
    assembly_digest,
    select_assembly_candidates,
    shared_candidates,
)
from artifact_forge_ng.catalog.loader import load_catalog

FLAGSHIP_PROMPT = (
    "верстачная станция на перфопанель: слайдер по ласточкину хвосту, "
    "на нём площадка с snap-корпусом для контроллера диммера, рядом "
    "лампа E27 на кронштейне с обжимом стержня, кабель от контроллера "
    "к патрону; корпус облегчить"
)

#: One archetype per mandatory flagship functional role.
FLAGSHIP_ROLES = {
    "pegboard_mount_base_v1", "rail_slider_v1", "rail_plate_adapter_v1",
    "enclosure_base_snap_v1", "enclosure_lid_snap_v1",
    "lamp_bracket_v1", "lamp_socket_cup_v1",
}


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_flagship_prompt_covers_every_role(catalog):
    chosen = set(select_assembly_candidates(FLAGSHIP_PROMPT, catalog))
    missing = FLAGSHIP_ROLES - chosen
    assert not missing, (
        f"flagship roles lost by retrieval: {sorted(missing)} — per the "
        "plan, stop the wave and design assembly_roles as a schema "
        "extension instead of improvising"
    )


def test_esp32_prompt_ranks_enclosures_on_top(catalog):
    top = select_assembly_candidates(
        "коробка под ESP32 с крышкой на винтах M3", catalog)[:6]
    assert "enclosure_base_v1" in top
    assert "enclosure_lid_v1" in top


def test_retrieval_is_deterministic_and_capped(catalog):
    a = select_assembly_candidates(FLAGSHIP_PROMPT, catalog, limit=15)
    b = select_assembly_candidates(FLAGSHIP_PROMPT, catalog, limit=15)
    assert a == b
    assert len(a) <= 15
    assert len(set(a)) == len(a)
    tiny = select_assembly_candidates(FLAGSHIP_PROMPT, catalog, limit=4)
    assert len(tiny) <= 4
    for prompt in ("крышка", "", "лампа на столе у окна"):
        assert len(select_assembly_candidates(prompt, catalog)) <= 15


def test_enclosure_prompt_is_not_displaced_by_vf(catalog):
    chosen = select_assembly_candidates(
        "коробка для электроники с крышкой", catalog)
    assert "enclosure_base_v1" in chosen or "enclosure_base_snap_v1" in chosen


def test_shared_candidates_require_type_agreement(catalog):
    specs = [catalog.archetypes["enclosure_base_v1"],
             catalog.archetypes["enclosure_lid_v1"]]
    cands = shared_candidates(specs)
    # the canonical esp32 shared keys are all candidates
    for key in ("wall", "boss_sx", "boss_sy"):
        assert key in cands, f"{key} must be shareable for the esp32 pair"


def test_digest_is_deterministic_and_grounded(catalog):
    ids = select_assembly_candidates(FLAGSHIP_PROMPT, catalog)
    d1 = assembly_digest(catalog, part_ids=ids)
    d2 = assembly_digest(catalog, part_ids=ids)
    assert d1 == d2
    # registry-derived sections all present
    assert "Joint types" in d1
    assert "lid_seat" in d1 and "pose:" in d1
    assert "datums:" in d1
    # examples follow relevance now — the flagship digest carries the
    # most-overlapping worked example (the bench station), not a fixed list
    assert "Worked example" in d1 and "bench_station" in d1
    assert "untrusted declarative data" in d1     # digest safety
    assert "quarter-turns" in d1                  # rules section
    # filtering: an archetype outside part_ids gets no per-archetype block
    outside = next(a for a in catalog.archetypes if a not in ids)
    assert f"- {outside} |" not in d1


def test_digest_budget(catalog):
    ids = select_assembly_candidates(FLAGSHIP_PROMPT, catalog)
    d = assembly_digest(catalog, part_ids=ids)
    assert len(d) / 4 < 12_000, (
        "digest grew past the single-system-block budget — revisit "
        "retrieval limit or section clipping"
    )


# -- retrieval sync gates (the catalog GROWS; findability must not rot) ----------


def test_every_archetype_is_reachable_by_its_own_metadata(catalog):
    """THE sync gate: an archetype that retrieval cannot find from its own
    id/class/tags/aliases is invisible to prompt->assembly — a new pack
    entry fails HERE on merge day, not in a user's hands半 a year later."""
    unreachable = []
    for spec in catalog.archetypes.values():
        meta = spec.catalog
        prompt = " ".join(
            [spec.id.replace("_", " "), spec.object_class.replace("_", " ")]
            + list(meta.tags) + list(meta.search_aliases))
        ids = select_assembly_candidates(prompt, catalog)
        if spec.id not in ids:
            unreachable.append(spec.id)
    assert unreachable == [], (
        f"archetypes invisible to retrieval: {unreachable} — give them "
        "tags/search_aliases (CatalogMeta) instead of a global synonym"
    )


def test_search_aliases_find_without_the_global_dictionary(catalog):
    """«кондуктор» is NOT in catalog/search.SYNONYMS — the drill guide is
    found through its own search_aliases, including a case-ending form."""
    from artifact_forge_ng.catalog.search import SYNONYMS
    assert "кондуктор" not in SYNONYMS
    for prompt in ("кондуктор для сверления под шканты",
                   "нужен сверловочный кондуктор на 8мм"):
        ids = select_assembly_candidates(prompt, catalog)
        assert "drill_guide_v1" in ids, (prompt, ids)
    ids = select_assembly_candidates("катушка для гирлянды", catalog)
    assert "cord_spool_v1" in ids


def test_examples_are_selected_by_relevance(catalog):
    """The few-shot block follows the candidates: flagship candidates pull
    the bench station example in; enclosure candidates lead with esp32."""
    flagship_ids = select_assembly_candidates(FLAGSHIP_PROMPT, catalog)
    d = assembly_digest(catalog, part_ids=flagship_ids)
    assert "bench_station" in d
    box_ids = select_assembly_candidates(
        "коробка под ESP32 с крышкой", catalog)
    d2 = assembly_digest(catalog, part_ids=box_ids, max_examples=1)
    assert "esp32_box_with_lid" in d2
