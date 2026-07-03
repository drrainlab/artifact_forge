"""Recipe kernel, tier-1: archetypes composed from registered ops in pure
YAML — with the same fail-fast and honesty guarantees as Python builders."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.catalog.loader import CatalogError, load_catalog
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS
from artifact_forge_ng.form.checks_cuts import check_cuts_respect_keepouts
from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GROMMET = EXAMPLES / "desk_grommet_90x40.yaml"


@pytest.fixture(scope="module")
def state():
    return run_pre_cad(GROMMET, None)


def test_grommet_form_builds_from_yaml_only(state):
    form = state.form
    assert form is not None
    assert [c.name for c in form.cutboxes] == ["cable_pass"]
    assert len(form.holes) == 2
    assert all(h.countersink for h in form.holes)
    # frame keys per the builder contract — probes measure these
    assert form.frame["screws_0_x"] == pytest.approx(-35.0)
    assert form.frame["screws_1_x"] == pytest.approx(35.0)
    assert form.frame["outline_u1"] == pytest.approx(45.0)
    fails = [f for f in state.report.findings if f.status.value == "fail"]
    assert fails == []


def test_ops_emit_regions(state):
    names = {r.name for r in state.form.regions}
    assert {"plate", "screws_0", "screws_1"} <= names


def test_cutout_into_screw_keepout_fails(state):
    """The composition is safe because keepouts are real: widen the cutout
    until it eats a screw zone and the IR check must fail before any CAD."""
    from artifact_forge_ng.form.part import CutBoxFeature
    from artifact_forge_ng.form.regions import Box3

    form = state.form
    rogue = CutBoxFeature(name="greedy", box=Box3(-40, -7, -1, 40, 7, 5))
    form.cutboxes.append(rogue)
    try:
        assert check_cuts_respect_keepouts(form).status.value == "fail"
    finally:
        form.cutboxes.remove(rogue)


def _load_catalog_with(tmp_path, archetype_doc):
    """Clone the real catalog data dir with one extra archetype."""
    import shutil
    from artifact_forge_ng.catalog import loader

    clone = tmp_path / "data"
    shutil.copytree(Path(loader.DATA_DIR), clone)
    (clone / "archetypes" / "zz_test.yaml").write_text(yaml.safe_dump(archetype_doc))
    return load_catalog(clone)


def _minimal_recipe_doc(ops, validators):
    return {
        "schema": "archetype/v1",
        "id": "zz_test_recipe",
        "object_class": "test_plate",
        "provides_features": ["mounting_plate_body"],
        "parameters": {"plate_l": {"type": "length", "default": "60mm"}},
        "form": {"type": "recipe", "section": "recipe", "plane": "XY",
                 "width_axis": "Z", "ops": ops},
        "regions": [{"id": "plate", "role": "mounting_surface"}],
        "validators": validators,
        "contract": {"must_have": ["mounting_plate_body"]},
    }


def test_unknown_op_is_a_load_error(tmp_path):
    doc = _minimal_recipe_doc(
        [{"op": "warp_field_generator", "params": {}}], []
    )
    with pytest.raises(CatalogError, match="unknown recipe op"):
        _load_catalog_with(tmp_path, doc)


def test_unsubscribed_op_validators_are_a_load_error(tmp_path):
    """An op's validators are mandatory: geometry without its checks is a
    hallucination, and the loader refuses it up front."""
    doc = _minimal_recipe_doc(
        [{"op": "rounded_plate", "id": "plate",
          "params": {"l": "plate_l", "w": "40mm", "t": "4mm"}}],
        [],  # rounded_plate requires form.holes_within_outline
    )
    with pytest.raises(CatalogError, match="requires validators"):
        _load_catalog_with(tmp_path, doc)


def test_every_op_declares_the_full_contract():
    """Registry-wide: no op may ship without validators (the contract) —
    except pure base ops would still carry at least the outline check."""
    for name, decl in RECIPE_OPS.items():
        assert decl.validators, f"op {name!r} declares no validators"
        assert decl.kind in ("base", "feature")


def test_recipe_archetype_loads_in_real_catalog():
    catalog = load_catalog()
    spec = catalog.archetypes["cable_grommet_plate_v1"]
    assert spec.form.type == "recipe"
    assert [o.op for o in spec.form.ops] == [
        "rounded_plate", "rounded_rect_cutout", "countersunk_hole_pattern"
    ]
