"""Vertical Farm Pack catalog integrity: the three archetypes load with
every name bound fail-fast (features, checks, forbidden forms, recipe ops,
op-mandated validators), and the loader really rejects a recipe that skips
an op's mandatory validators."""

import pytest

from artifact_forge_ng.catalog.loader import CatalogError, load_catalog
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS
from artifact_forge_ng.validators.probes import FORBIDDEN_FORM_DETECTORS, KNOWN_CHECKS

PACK = ("water_rail_v1", "coco_cassette_v1", "substrate_retainer_frame_v1")

PACK_FEATURES = (
    "constant_depth_water_channel", "lap_flow_handover", "lightweight_dry_shell",
    "cassette_seat", "module_alignment_edges", "aluminum_profile_seat",
    "substrate_mesh_floor", "pulse_contact_window", "tool_free_removal",
    "cleanable_snap_interface", "vertical_farm_cassette_interface",
    "module_line_interface", "snapped_retainer",
)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def test_pack_archetypes_load(catalog):
    for aid in PACK:
        assert aid in catalog.archetypes


def test_pack_features_in_vocabulary(catalog):
    for fid in PACK_FEATURES:
        assert fid in catalog.features, fid
        for check in catalog.features[fid].verified_by:
            assert check in KNOWN_CHECKS, (fid, check)


def test_forbidden_forms_have_detectors(catalog):
    for aid in PACK:
        for form_id in catalog.archetypes[aid].contract.must_not_have:
            assert form_id in FORBIDDEN_FORM_DETECTORS, (aid, form_id)
            detector = FORBIDDEN_FORM_DETECTORS[form_id]
            # the detector must actually RUN: manufacturing checks are
            # always-on, everything else must be subscribed
            subscribed = detector in catalog.archetypes[aid].validators
            always_on = detector.startswith("manufacturing.")
            assert subscribed or always_on, (aid, form_id, detector)


def test_ops_validators_subscribed(catalog):
    """The loader enforces this at load time — assert the invariant holds
    so a future edit that drops a validator fails HERE with a name."""
    for aid in PACK:
        spec = catalog.archetypes[aid]
        subscribed = set(spec.validators)
        for use in spec.form.ops:
            for check in RECIPE_OPS[use.op].validators:
                assert check in subscribed, (aid, use.op, check)


def test_loader_rejects_recipe_missing_op_validators(tmp_path):
    import shutil

    from artifact_forge_ng.catalog import loader

    # Self-contained catalog: core data overlaid with the pack's features
    # and archetypes (an explicit data_dir never merges packs).
    import artifact_forge_vf

    data = tmp_path / "data"
    shutil.copytree(loader.DATA_DIR, data)
    pack_data = artifact_forge_vf._DATA_DIR
    pack_feats = (pack_data / "features.yaml").read_text().split("features:\n", 1)[1]
    feats = data / "features.yaml"
    feats.write_text(feats.read_text() + pack_feats)
    for y in (pack_data / "archetypes").glob("*.yaml"):
        shutil.copy(y, data / "archetypes" / y.name)
    rail = data / "archetypes" / "water_rail_v1.yaml"
    text = rail.read_text().replace("  - form.water_channel_constant_depth_ok\n", "")
    assert text != rail.read_text()
    rail.write_text(text)
    with pytest.raises(CatalogError, match="water_channel_constant_depth_ok"):
        load_catalog(data)
