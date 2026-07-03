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
    def test_make_support_free_is_a_migration(self, env):
        catalog, instance, archetype = env
        patch = INTENTS["make_support_free"].build_patch(instance, archetype)
        assert patch.type == "manufacturing"
        assert patch.archetype == "underdesk_cable_clip_v3_sideprint"
        assert patch.manufacturing == {"support_policy": "none"}
        assert "bundle_d" in patch.preserve
        assert "asymmetric_side_hook" in patch.preserve
        # mounting_flange does not exist on the target — the intent must
        # not promise to preserve it
        assert "mounting_flange" not in patch.preserve

    def test_apply_migrates_to_sideprint(self, env):
        catalog, instance, archetype = env
        patch = INTENTS["make_support_free"].build_patch(instance, archetype)
        edited = apply_patch(instance, patch, archetype, catalog)
        assert edited.archetype_id == "underdesk_cable_clip_v3_sideprint"
        assert edited.manufacturing.support_policy == "none"
        # params the target does not know are dropped, shared ones carried
        assert "flange_l" not in edited.params
        assert edited.params["bundle_d"] == "20mm"
        # the hex modifier is not allowed on the target — dropped
        assert all(m.id != "add_hex_perforation" for m in edited.modifiers)
        assert "mounting_flange" not in edited.requested_features
        # the original untouched
        assert instance.archetype_id == "underdesk_cable_clip_v2_molded"

    def test_migration_to_unknown_archetype_rejected(self, env):
        catalog, instance, archetype = env
        patch = Patch(schema="patch/v1", archetype="warp_drive_clip_v9")
        with pytest.raises(PatchError, match="unknown archetype"):
            apply_patch(instance, patch, archetype, catalog)

    def test_migration_across_object_class_rejected(self, env):
        catalog, instance, archetype = env
        stand = load_instance(EXAMPLES / "phone_stand_std.yaml")
        target_id = stand.archetype_id
        patch = Patch(schema="patch/v1", archetype=target_id)
        with pytest.raises(PatchError, match="object class"):
            apply_patch(instance, patch, archetype, catalog)

    def test_teardrop_still_available_as_manual_patch(self, env):
        """The teardrop cavity stays a legal manufacturing patch on v2 —
        it fixes the cavity overhang for those who WANT flange-down."""
        catalog, instance, archetype = env
        patch = Patch(
            schema="patch/v1", type="manufacturing",
            params={"cavity_roof": "teardrop"},
        )
        edited = apply_patch(instance, patch, archetype, catalog)
        assert edited.params["cavity_roof"] == "teardrop"

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


class TestModifierUpdate:
    def test_update_merges_params(self, env):
        catalog, instance, archetype = env
        patch = Patch(
            schema="patch/v1", type="style",
            modifiers={"update": [{"id": "add_hex_perforation",
                                   "params": {"cell_d": "6mm"}}]},
        )
        edited = apply_patch(instance, patch, archetype, catalog)
        use = next(m for m in edited.modifiers if m.id == "add_hex_perforation")
        assert use.params["cell_d"] == "6mm"
        # untouched params survive the merge
        assert use.params["wall_gap"] == "1.5mm"

    def test_update_of_absent_modifier_refused(self, env):
        catalog, instance, archetype = env
        patch = Patch(
            schema="patch/v1",
            modifiers={"update": [{"id": "add_voronoi_field",
                                   "params": {"sites": "30"}}]},
        )
        with pytest.raises(PatchError, match="does not use"):
            apply_patch(instance, patch, archetype, catalog)
