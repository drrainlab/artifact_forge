"""Every showcase example must pass the pre-CAD golden gate — the pack's
contract with the gallery: nothing ships that does not validate."""
from __future__ import annotations

from pathlib import Path

import pytest

from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = sorted(
    (Path(__file__).parents[1] / "examples").rglob("*.yaml"),
    key=lambda p: p.name,
)


def test_examples_exist():
    assert EXAMPLES, "showcase pack has no examples"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_validates(path):
    state = run_pre_cad(path, strict_flag=True)
    assert state.report.status.value == "pass", path.name


def test_featured_ids_exist_in_catalog():
    import yaml

    from artifact_forge_ng.catalog.loader import load_catalog

    pack_yaml = Path(__file__).parents[1] / "pack.yaml"
    featured = (yaml.safe_load(pack_yaml.read_text()).get("catalog") or {}).get(
        "featured", [])
    assert featured, "showcase must feature its starters"
    catalog = load_catalog()
    missing = [f for f in featured if f not in catalog.archetypes]
    assert not missing, missing
