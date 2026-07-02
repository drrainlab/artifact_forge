"""Catalog loading: the real data dir loads; every name-binding failure is a
load error, never a silent skip."""

import shutil
from pathlib import Path

import pytest

from artifact_forge_ng.catalog.loader import (
    DATA_DIR,
    CatalogError,
    load_catalog,
    load_instance,
    validate_instance,
)

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.fixture()
def catalog():
    return load_catalog()


@pytest.fixture()
def data_copy(tmp_path):
    dst = tmp_path / "data"
    shutil.copytree(DATA_DIR, dst)
    return dst


ARCHETYPE = "archetypes/underdesk_cable_clip_v2_molded.yaml"


def test_real_catalog_loads(catalog):
    assert "underdesk_cable_clip_v2_molded" in catalog.archetypes
    assert "add_hex_perforation" in catalog.modifiers
    assert "asymmetric_side_hook" in catalog.features


def test_unknown_validator_name_is_load_error(data_copy):
    p = data_copy / ARCHETYPE
    p.write_text(p.read_text().replace("form.profile_closed", "form.does_not_exist"))
    with pytest.raises(CatalogError, match="does_not_exist"):
        load_catalog(data_copy)


def test_unknown_forbidden_form_is_load_error(data_copy):
    p = data_copy / ARCHETYPE
    p.write_text(p.read_text().replace("symmetric_c_ring", "cursed_ring"))
    with pytest.raises(CatalogError, match="cursed_ring"):
        load_catalog(data_copy)


def test_unknown_feature_in_must_have_is_load_error(data_copy):
    p = data_copy / ARCHETYPE
    p.write_text(
        p.read_text().replace("- through_cavity", "- imaginary_feature")
    )
    with pytest.raises(CatalogError, match="imaginary_feature"):
        load_catalog(data_copy)


def test_bad_unit_in_archetype_is_load_error(data_copy):
    p = data_copy / ARCHETYPE
    p.write_text(p.read_text().replace("default: 20mm", "default: 20parsec"))
    with pytest.raises(CatalogError, match="unknown unit"):
        load_catalog(data_copy)


def test_unknown_modifier_in_allowed_is_load_error(data_copy):
    p = data_copy / ARCHETYPE
    p.write_text(p.read_text().replace("- fillet_soften", "- warp_drive"))
    with pytest.raises(CatalogError, match="warp_drive"):
        load_catalog(data_copy)


def test_duplicate_region_id_is_load_error(data_copy):
    p = data_copy / ARCHETYPE
    p.write_text(
        p.read_text().replace(
            "{id: snap_root,", "{id: flange,", 1
        )
    )
    with pytest.raises(CatalogError, match="duplicate region"):
        load_catalog(data_copy)


class TestInstanceValidation:
    def test_golden_example_validates(self, catalog):
        inst = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
        archetype = validate_instance(inst, catalog)
        assert archetype.id == "underdesk_cable_clip_v2_molded"

    def test_unknown_archetype_fails(self, catalog):
        inst = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
        inst = inst.model_copy(update={"archetype": "flying_car"})
        with pytest.raises(CatalogError, match="unknown archetype"):
            validate_instance(inst, catalog)

    def test_wrong_version_pin_fails(self, catalog):
        inst = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
        inst = inst.model_copy(
            update={"archetype": "underdesk_cable_clip_v2_molded@99"}
        )
        with pytest.raises(CatalogError, match="version"):
            validate_instance(inst, catalog)

    def test_modifier_on_forbidden_region_fails(self, catalog):
        inst = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
        bad = inst.model_dump(by_alias=True)
        bad["modifiers"][0]["target"] = "snap_root"  # high-stress: forbidden
        from artifact_forge_ng.product.instance import ProductInstance

        inst = ProductInstance.model_validate(bad)
        with pytest.raises(CatalogError, match="snap_root"):
            validate_instance(inst, catalog)

    def test_modifier_param_out_of_range_fails(self, catalog):
        inst = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
        bad = inst.model_dump(by_alias=True)
        bad["modifiers"][0]["params"]["cell_d"] = "25mm"  # max is 10mm
        from artifact_forge_ng.product.instance import ProductInstance

        inst = ProductInstance.model_validate(bad)
        with pytest.raises(CatalogError, match="above max"):
            validate_instance(inst, catalog)

    def test_modifier_on_missing_region_fails(self, catalog):
        inst = load_instance(EXAMPLES / "desk_cable_clip_20mm.yaml")
        bad = inst.model_dump(by_alias=True)
        bad["modifiers"][0]["target"] = "nonexistent_region"
        from artifact_forge_ng.product.instance import ProductInstance

        inst = ProductInstance.model_validate(bad)
        with pytest.raises(CatalogError, match="does not exist"):
            validate_instance(inst, catalog)
