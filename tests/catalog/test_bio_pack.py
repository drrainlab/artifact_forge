"""Bio-0 catalog layer: the biomorphic pack's vocabulary loads, forbidden
targeting is unrepresentable, load_paths/maturity bind fail-fast, and the
no-applicator modifiers stay honest engine gaps (docs/BIOMORPHIC.md)."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.catalog.loader import (
    CatalogError,
    compatible_regions,
    load_catalog,
    validate_instance,
)
from artifact_forge_ng.product.archetype import ArchetypeSpec, RegionRole
from artifact_forge_ng.product.instance import ProductInstance

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"

BIO_MODIFIERS = (
    "apply_biomorphic_exoskeleton", "add_bone_windows",
    "organic_taper_outer_shell", "biomech_surface_texture",
)
BIO_FEATURES = (
    "biomorphic_exoskeleton", "organic_windows", "load_path_ribs",
    "split_branch_clamp", "branch_saddle", "three_point_tpu_contact",
    "axial_cable_channel", "dovetail_rail", "compression_clamp_interface",
)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_bio_pack_loads(catalog):
    for mod in BIO_MODIFIERS:
        assert mod in catalog.modifiers, mod
    for feat in BIO_FEATURES:
        assert feat in catalog.features, feat
    assert "branch_clamp_lower_v1" in catalog.archetypes
    assert "branch_clamp_upper_v1" in catalog.archetypes
    # add_vein_ribs gained the panel target without duplication
    assert RegionRole.EXOSKELETON_PANEL in catalog.modifiers["add_vein_ribs"].applies_to
    assert "add_vein_rib_field" not in catalog.modifiers


def test_bio_modifier_rejected_on_protected_regions(catalog):
    """The DoD guarantee: exoskeleton on a saddle/bolt zone is a LOAD error."""
    inst = ProductInstance.model_validate({
        "schema": "product/v1", "id": "x",
        "archetype": "branch_clamp_lower_v1@1", "strict": True,
        "modifiers": [{"id": "apply_biomorphic_exoskeleton",
                       "target": "saddle_contact", "params": {}}],
    })
    with pytest.raises(CatalogError, match="saddle_contact"):
        validate_instance(inst, catalog)


def test_compatible_regions_offer_only_the_panel(catalog):
    arch = catalog.archetypes["branch_clamp_lower_v1"]
    exo = catalog.modifiers["apply_biomorphic_exoskeleton"]
    assert [r.id for r in compatible_regions(arch, exo)] == ["outer_shell"]


def test_maturity_is_informational_and_validated(catalog):
    assert catalog.archetypes["branch_clamp_lower_v1"].maturity == "sandbox_buildable"
    with pytest.raises(Exception, match="maturity"):
        ArchetypeSpec.model_validate({
            "schema": "archetype/v1", "id": "x", "object_class": "x",
            "form": {"type": "plate", "section": "x"},
            "maturity": "totally_done_trust_me",
        })


def test_load_paths_bind_fail_fast(catalog, tmp_path):
    """from/to must name declared regions — unknown names are load errors."""
    import shutil

    from artifact_forge_ng.catalog.loader import DATA_DIR

    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    p = data / "archetypes" / "branch_clamp_lower_v1.yaml"
    doc = yaml.safe_load(p.read_text())
    doc["load_paths"] = [{"from": "outer_shell", "to": "warp_core"}]
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    with pytest.raises(CatalogError, match="warp_core"):
        load_catalog(data)
    # valid region pair loads fine
    doc["load_paths"] = [{"from": "outer_shell", "to": "saddle_contact",
                          "priority": "primary"}]
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    spec = load_catalog(data).archetypes["branch_clamp_lower_v1"]
    assert spec.load_paths[0].from_ == "outer_shell"


def test_no_applicator_bio_modifiers_are_honest_engine_gaps(catalog):
    """organic_taper/biomech_texture are declared ahead of their applicators:
    applying them WARNs as engine gap and claims nothing (Bio-3 fills them)."""
    from artifact_forge_ng.core.findings import Status
    from artifact_forge_ng.modifiers import apply_modifiers
    from artifact_forge_ng.pipeline import pre_cad_from_instance
    from artifact_forge_ng.product.instance import ModifierUse

    demo = (EXAMPLES / "biomorphic_exoskeleton_demo_plate.yaml").read_text()
    inst = ProductInstance.model_validate(yaml.safe_load(demo))
    state = pre_cad_from_instance(inst, catalog, strict=False)
    for mod_id in ("organic_taper_outer_shell", "biomech_surface_texture"):
        mdef = catalog.modifiers[mod_id]
        assert mdef.provides_features == [] and mdef.validators == []
        use = ModifierUse(id=mod_id, target="lightening_zone", params={})
        findings = apply_modifiers(
            state.form, [use], {mod_id: mdef}, state.archetype)
        gap = [f for f in findings if f.status is Status.WARN
               and "engine gap" in f.message]
        assert gap, f"{mod_id}: expected an engine-gap WARN, got {findings}"