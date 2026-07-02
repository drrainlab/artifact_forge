"""Semantic edit: intents, preserve contract, negatives — tier-1."""

from pathlib import Path

import pytest

from artifact_forge_ng.catalog.loader import load_catalog, load_instance, validate_instance
from artifact_forge_ng.repair.edit import BuildSnapshot, verify_preserve
from artifact_forge_ng.repair.intents import INTENTS, IntentNotApplicable
from artifact_forge_ng.repair.patch import Patch, PatchError, apply_patch

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = EXAMPLES / "desk_cable_clip_20mm.yaml"


@pytest.fixture(scope="module")
def env():
    catalog = load_catalog()
    instance = load_instance(GOLDEN)
    archetype = validate_instance(instance, catalog)
    return catalog, instance, archetype


class TestIntents:
    def test_make_support_free_patch(self, env):
        catalog, instance, archetype = env
        patch = INTENTS["make_support_free"].build_patch(instance, archetype)
        assert patch.type == "manufacturing"
        assert patch.params == {"cavity_roof": "teardrop"}
        assert patch.manufacturing == {"support_policy": "none"}
        assert "bundle_d" in patch.preserve
        assert "asymmetric_side_hook" in patch.preserve

    def test_apply_produces_teardrop_instance(self, env):
        catalog, instance, archetype = env
        patch = INTENTS["make_support_free"].build_patch(instance, archetype)
        edited = apply_patch(instance, patch, archetype, catalog)
        assert edited.params["cavity_roof"] == "teardrop"
        assert edited.manufacturing.support_policy == "none"
        # the original untouched
        assert "cavity_roof" not in instance.params

    def test_not_applicable_refuses(self, env):
        catalog, _, _ = env
        plate_inst = load_instance(EXAMPLES / "adapter_plate_router_mount.yaml")
        plate_arch = catalog.archetypes[plate_inst.archetype_id]
        with pytest.raises(IntentNotApplicable, match="cavity_roof"):
            INTENTS["make_support_free"].build_patch(plate_inst, plate_arch)

    def test_make_biomorphic_preserves_function(self, env):
        catalog, _, _ = env
        stand = load_instance(EXAMPLES / "phone_stand_std.yaml")
        arch = catalog.archetypes[stand.archetype_id]
        patch = INTENTS["make_biomorphic"].build_patch(stand, arch)
        assert patch.style["surface"] == "biomorphic_utility_part"
        assert "device_thickness" in patch.preserve
        edited = apply_patch(stand, patch, arch, catalog)
        assert edited.style["surface"] == "biomorphic_utility_part"

    def test_remove_perforation_needs_fields(self, env):
        catalog, _, _ = env
        stand = load_instance(EXAMPLES / "phone_stand_std.yaml")
        arch = catalog.archetypes[stand.archetype_id]
        with pytest.raises(IntentNotApplicable, match="no field modifiers"):
            INTENTS["remove_perforation"].build_patch(stand, arch)
        clip = load_instance(GOLDEN)
        clip_arch = catalog.archetypes[clip.archetype_id]
        patch = INTENTS["remove_perforation"].build_patch(clip, clip_arch)
        edited = apply_patch(clip, patch, clip_arch, catalog)
        assert all(m.id != "add_hex_perforation" for m in edited.modifiers)

    def test_make_stronger_bumps_walls(self, env):
        catalog, instance, archetype = env
        patch = INTENTS["make_stronger"].build_patch(instance, archetype)
        edited = apply_patch(instance, patch, archetype, catalog)
        assert edited.params["wall"] == "4mm"  # 3.2 + 0.8
        assert edited.params["flange_t"] == "6mm"


class TestPreserveContract:
    def _snap(self, params, features, choices=None):
        return BuildSnapshot(
            params=params, choices=choices or {}, built_features=features,
            manufacturing={}, style={}, findings=[], status="pass", grade="A",
        )

    def test_verified_when_unchanged(self):
        patch = Patch(schema="patch/v1", preserve=["bundle_d", "asymmetric_side_hook"])
        before = self._snap({"bundle_d": 20.0}, ["asymmetric_side_hook"])
        after = self._snap({"bundle_d": 20.0}, ["asymmetric_side_hook"])
        verified, violations = verify_preserve(patch, before, after)
        assert len(verified) == 2 and violations == []

    def test_param_drift_violates(self):
        patch = Patch(schema="patch/v1", preserve=["bundle_d"])
        before = self._snap({"bundle_d": 20.0}, [])
        after = self._snap({"bundle_d": 19.5}, [])
        _, violations = verify_preserve(patch, before, after)
        assert violations and "bundle_d" in violations[0]

    def test_unbuilt_feature_violates(self):
        patch = Patch(schema="patch/v1", preserve=["asymmetric_side_hook"])
        before = self._snap({}, ["asymmetric_side_hook"])
        after = self._snap({}, [])
        _, violations = verify_preserve(patch, before, after)
        assert violations and "no longer validator-built" in violations[0]

    def test_unknown_preserve_name_rejected_at_apply(self, env):
        catalog, instance, archetype = env
        patch = Patch(schema="patch/v1", preserve=["warp_core_integrity"])
        with pytest.raises(PatchError, match="warp_core_integrity"):
            apply_patch(instance, patch, archetype, catalog)
