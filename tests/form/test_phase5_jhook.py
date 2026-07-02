"""Tier-1 for the j_hook family (wall_hook_v1 + headphone_hook_v1)."""

from pathlib import Path

import pytest

from artifact_forge_ng.archetypes import builder_for
from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.cli import run_validate
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_jhook import (
    check_bay_open_top,
    check_tip_lip_present,
)
from artifact_forge_ng.form.molded import INTENTIONAL_TAGS, joint_is_tangent
from artifact_forge_ng.form.profiles_jhook import JHookParams, build_j_hook_profile
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.product.resolve import resolve_params

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


@pytest.mark.parametrize(
    "example", ["wall_hook_coat", "underdesk_headphone_hook"]
)
def test_examples_validate_clean(example):
    out = run_validate(EXAMPLES / f"{example}.yaml", strict_flag=None)
    assert out["status"] == "pass"


@pytest.mark.parametrize("bay_w", [6.0, 14.0, 30.0])
def test_profile_tangency_and_lip_across_range(bay_w):
    p = JHookParams(bay_w=bay_w, bay_depth=bay_w / 2 + 20, wall=4.0, lip_h=8.0)
    profile, frame = build_j_hook_profile(p, MOLDED_UTILITY_PART)
    sharp = [
        (sorted(a.tags), sorted(b.tags))
        for a, b in profile.outer.joints()
        if not joint_is_tangent(a, b) and not ((a.tags | b.tags) & INTENTIONAL_TAGS)
    ]
    assert sharp == []
    # outer arc is tangent to the spine at u=0 by construction
    lo, _ = profile.outer.bbox()
    assert lo.u == pytest.approx(0.0, abs=1e-6)
    assert frame["entry_gap"] == pytest.approx(
        p.bay_depth - p.bay_w / 2 - p.lip_h, abs=1e-9
    )


def test_shared_builder_two_archetypes():
    catalog = load_catalog()
    wall = catalog.archetypes["wall_hook_v1"]
    hp = catalog.archetypes["headphone_hook_v1"]
    assert builder_for(wall) is builder_for(hp)
    assert wall.form.section == hp.form.section == "j_hook"


def _form_for(example: str):
    catalog = load_catalog()
    inst = load_instance(EXAMPLES / f"{example}.yaml")
    archetype = catalog.archetypes[inst.archetype_id]
    resolved = resolve_params(archetype, inst)
    return builder_for(archetype)(resolved, archetype, inst)


def test_lip_and_bay_checks_pass_on_golden():
    form = _form_for("wall_hook_coat")
    assert check_tip_lip_present(form).status is Status.PASS
    assert check_bay_open_top(form).status is Status.PASS


def test_negative_closing_lip_rejected():
    """A lip tall enough to close the entry is stopped twice: the frame
    itself refuses, and the YAML expr-clamp keeps resolve inside range."""
    with pytest.raises(ValueError, match="entry closes"):
        build_j_hook_profile(
            JHookParams(bay_w=14.0, bay_depth=20.0, wall=4.0, lip_h=12.0),
            MOLDED_UTILITY_PART,
        )
    catalog = load_catalog()
    inst = load_instance(EXAMPLES / "wall_hook_coat.yaml")
    data = inst.model_dump(by_alias=True)
    data["params"]["lip_h"] = "40mm"  # way past the expr ceiling
    from artifact_forge_ng.product.instance import ProductInstance

    inst = ProductInstance.model_validate(data)
    archetype = catalog.archetypes[inst.archetype_id]
    resolved = resolve_params(archetype, inst)
    # clamped to bay_depth - bay_w/2 - 6
    assert resolved.context["lip_h"] == pytest.approx(32 - 8 - 6)
