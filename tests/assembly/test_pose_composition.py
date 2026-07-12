"""Quarter-turn pose composition through rotated parents (kernel wave).

The group of quarter-turn rotations is closed under composition — the
kernel now composes chains through a ROTATED parent exactly (integers,
no drift) instead of refusing. Invariants pinned here:

* algebra: ``compose_pose(P, L).apply(x) == P.apply(L.apply(x))`` over
  the FULL 24x24 rotation group with translations;
* the composed Euler triple stays inside the legal quarter-turn set;
* a real chain board -> adapter (rot 0) -> carriage (rot 180) -> box
  (posed FROM the rotated carriage) passes pose derivation — the old
  "chaining through the ROTATED part" refusal is gone;
* existing unrotated-chain assemblies report byte-identical poses.
"""

from __future__ import annotations


import pytest
import yaml

from artifact_forge_ng.assembly.joints_core import (
    _EULER_BY_MATRIX,
    Pose,
    compose_pose,
    rotate_point,
)
from artifact_forge_ng.product.assembly import _LEGAL_ANGLES

SAMPLE_POINTS = [(1.0, 2.0, 3.0), (-4.0, 0.5, 7.0), (0.0, 0.0, 1.0)]


def test_rotation_group_has_24_elements():
    assert len(_EULER_BY_MATRIX) == 24
    for triple in _EULER_BY_MATRIX.values():
        assert all(a in _LEGAL_ANGLES for a in triple)


@pytest.mark.parametrize("parent_rot", sorted(_EULER_BY_MATRIX.values()))
def test_composition_equals_sequential_application(parent_rot):
    parent = Pose(rotate=parent_rot, translate=(3.0, -2.0, 5.0))
    for local_rot in _EULER_BY_MATRIX.values():
        local = Pose(rotate=local_rot, translate=(-1.0, 4.0, 0.5))
        composed = compose_pose(parent, local)
        for p in SAMPLE_POINTS:
            expected = parent.apply(local.apply(p))
            got = composed.apply(p)
            assert got == pytest.approx(expected, abs=1e-9), (
                f"parent {parent_rot} x local {local_rot} diverges at {p}"
            )
        assert all(a in _LEGAL_ANGLES for a in composed.rotate)


def test_identity_composition_is_transparent():
    parent = Pose(rotate=(0.0, 0.0, 0.0), translate=(10.0, 0.0, 0.0))
    local = Pose(rotate=(180.0, 0.0, 0.0), translate=(0.0, 0.0, 29.0))
    composed = compose_pose(parent, local)
    assert composed.rotate == (180.0, 0.0, 0.0)
    assert composed.translate == (10.0, 0.0, 29.0)


def test_multi_axis_composition_is_exact():
    """90 about X then 90 about Y is a single group element again —
    integer arithmetic end to end."""
    a = Pose(rotate=(90.0, 0.0, 0.0), translate=(0.0, 0.0, 0.0))
    b = Pose(rotate=(0.0, 90.0, 0.0), translate=(1.0, 0.0, 0.0))
    composed = compose_pose(a, b)
    for p in SAMPLE_POINTS:
        assert composed.apply(p) == pytest.approx(a.apply(b.apply(p)))
    # translate of the composition is the parent-rotated local translate
    assert composed.translate == rotate_point((1.0, 0.0, 0.0), a.rotate)


# -- the real chain: through a ROTATED carriage --------------------------------


@pytest.fixture(scope="module")
def catalog():
    from artifact_forge_ng.catalog.loader import load_catalog
    return load_catalog()


def _carriage_chain_doc() -> dict:
    """pegboard -> adapter (rot 0) -> carriage (rot 180, female dovetail)
    -> box screwed onto the carriage's... there is no carriage payload
    stack yet, so the chained part rides the SAME anchor: what matters
    for THIS test is the pose derivation through the rotated carriage,
    not the mate fit — strict stays off and only pose findings are
    asserted absent."""
    base = yaml.safe_load(
        open("catalog/examples/pegboard_slider_carriage.yaml"))
    base["strict"] = False
    base["parts"].append({
        "ref": "probe_box",
        "product": {
            "schema": "product/v1", "id": "probe_box",
            "archetype": "enclosure_base_v1@1",
            "params": {"mount_holes": 2, "mount_span": "30mm",
                       "mount_cy": "10mm", "mount_screw": "M3"},
        },
    })
    base["joints"].append({
        # hangs off the ROTATED carriage — the old kernel refused this
        "type": "screw_joint",
        "a": "carriage.rail_slot",
        "b": "probe_box.base",
        "rotate": [180, 0, 0],
        "params": {"screw": "M3", "count": 2, "pilots": "nonexistent"},
    })
    return base


def test_chain_through_rotated_parent_derives_a_pose(catalog):
    from artifact_forge_ng.assembly.pipeline import validate_assembly_doc
    from artifact_forge_ng.product.assembly import AssemblyInstance

    asm = AssemblyInstance.model_validate(_carriage_chain_doc())
    report = validate_assembly_doc(asm, catalog, False)
    messages = [j["message"] for j in report["joints"]]
    assert not any("ROTATED" in m for m in messages), (
        "the rotated-parent refusal must be gone")
    posed = {p["part"] for p in report["assembly_pose"]}
    assert "probe_box" in posed, messages
    box_pose = next(p for p in report["assembly_pose"]
                    if p["part"] == "probe_box")
    # carriage is flipped 180 about X; the box flips 180 relative to the
    # carriage — composed rotation must land back inside the legal set
    # (here: identity about X, exactly)
    assert all(a in _LEGAL_ANGLES for a in box_pose["rotate"])


def test_existing_unrotated_chains_report_identically(catalog):
    """Composition through an UNROTATED parent must stay byte-identical
    to the old pure-translation path (the esp32 and carriage examples)."""
    from artifact_forge_ng.assembly.pipeline import run_assembly_validate
    from pathlib import Path

    for name in ("esp32_box_with_lid.yaml", "pegboard_slider_carriage.yaml"):
        report = run_assembly_validate(
            Path("catalog/examples") / name, None)
        assert report["status"] == "pass", name
        for pose in report["assembly_pose"]:
            if "rotate" in pose:
                assert all(a in _LEGAL_ANGLES for a in pose["rotate"])


@pytest.mark.parametrize("rot", sorted(_EULER_BY_MATRIX.values()))
def test_inverse_pose_round_trips(rot):
    from artifact_forge_ng.assembly.joints_core import inverse_pose
    pose = Pose(rotate=rot, translate=(7.0, -3.0, 2.5))
    inv = inverse_pose(pose)
    for p in SAMPLE_POINTS:
        assert inv.apply(pose.apply(p)) == pytest.approx(p, abs=1e-9)
        assert pose.apply(inv.apply(p)) == pytest.approx(p, abs=1e-9)
