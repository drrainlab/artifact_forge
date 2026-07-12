"""Datum declarations (wave G3): honesty audit + flagship mate pairs.

The declared ``datums:`` blocks are the assembly anchor vocabulary the
LLM digest is grounded in. Truth is the built Form IR — the audit builds
every declared archetype pre-CAD and compares. Archetypes that PUBLISH
datums while declaring none live on a SHRINK-ONLY allowlist (adding a
name is forbidden; wave G3-full empties it).

The mate-pair tests pin the flagship "bench station" composition rows at
the joint-IR level, with defaults or coordinated params. Pairs that
honestly do NOT mate today are pinned as failures with the catalog gap
named — fixing the gap flips the test, which is the point.
"""

from __future__ import annotations

import pytest

from artifact_forge_ng.assembly.joints import JOINT_TYPES, compute_pose
from artifact_forge_ng.catalog.audit import audit_catalog_datums
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.pipeline import pre_cad_from_instance
from artifact_forge_ng.product.assembly import JointUse
from artifact_forge_ng.product.instance import ProductInstance


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


#: Archetypes that publish Form IR datums but declare none yet.
#: SHRINK-ONLY: adding a name here is forbidden; wave G3-full emptied the
#: real catalog — only the test-only local-catalog fixture remains
#: (present under pytest because conftest sets ARTIFACT_FORGE_LOCAL_CATALOG).
UNDECLARED_ARCHETYPES = {
    "test_local_ring_v1",
}


def test_declared_datums_are_honest(catalog):
    """Every archetype with a datums: block builds and matches it —
    including the audit_params variants of conditional datums."""
    audits = audit_catalog_datums(catalog, only_declared=True)
    assert audits, "no archetype declares datums — wave G3 not landed?"
    problems = [f"{a.archetype}: {p}" for a in audits for p in a.problems]
    assert problems == [], "\n".join(problems)
    # conditional without audit_params must not sneak in silently
    lazy = [w for a in audits for w in a.warnings if "no audit_params" in w]
    assert lazy == [], "\n".join(lazy)


def test_undeclared_publisher_allowlist_is_current(catalog):
    audits = audit_catalog_datums(catalog, only_declared=False)
    undeclared = {
        a.archetype for a in audits
        if any("declares none" in w for w in a.warnings)
    }
    assert undeclared == (UNDECLARED_ARCHETYPES & set(catalog.archetypes)), (
        "undeclared-publisher set drifted; declare datums for new archetypes "
        f"instead of growing the allowlist: {sorted(undeclared)}"
    )


# -- flagship mate pairs (joint IR level, no CAD) --------------------------------


def _form(catalog, archetype_id, params=None):
    spec = catalog.archetypes[archetype_id]
    inst = ProductInstance.model_validate({
        "schema": "product/v1", "id": f"pair_{archetype_id}",
        "archetype": spec.ref,
        "params": {k: str(v) for k, v in (params or {}).items()},
        "strict": False,
    })
    form = pre_cad_from_instance(inst, catalog, strict=False).form
    assert form is not None, f"{archetype_id}: pre-CAD produced no form"
    return form


def _probe(catalog, jtype, a, b, *, rotate=(0, 0, 0), params=None,
           pa=None, pb=None):
    a_id, a_datum = a
    b_id, b_datum = b
    fa = _form(catalog, a_id, pa)
    fb = _form(catalog, b_id, pb)
    joint = JointUse(type=jtype, a=f"A.{a_datum}", b=f"B.{b_datum}",
                     rotate=list(rotate), params=params or {})
    pose = compute_pose(joint, fa, fb)
    return JOINT_TYPES[jtype].ir_check(fa, fb, pose, joint)


def _all_pass(findings):
    return all(f.status.value == "pass" for f in findings)


def test_pair_lid_seat_snap_enclosures(catalog):
    """Flagship row: snap lid seats on the snap box — on pure defaults."""
    findings = _probe(
        catalog, "lid_seat",
        ("enclosure_base_snap_v1", "rim"), ("enclosure_lid_snap_v1", "seat"),
        rotate=(180, 0, 0),
    )
    assert _all_pass(findings), [f.message for f in findings]


def test_pair_snap_joint_with_example_params(catalog):
    """Flagship row: the snap hooks engage with the esp32_box_snap_lid
    example's coordinated params (defaults alone over-strain the beam)."""
    shared = {"wall": "2.4mm", "plug_depth": "3.5mm", "hook_len": "10mm",
              "hook_w": "8mm", "lip_h": "3mm"}
    box = {k: v for k, v in shared.items()}
    lid = {**shared, "beam_t": "1.8mm", "lip_d": "1.6mm",
           "lid_l": "82mm", "lid_w": "52mm"}
    box.update({"box_l": "82mm", "box_w": "52mm"})
    findings = _probe(
        catalog, "snap_joint",
        ("enclosure_base_snap_v1", "rim"), ("enclosure_lid_snap_v1", "seat"),
        rotate=(180, 0, 0),
        pa={k: v for k, v in box.items()
            if k in catalog.archetypes["enclosure_base_snap_v1"].parameters},
        pb={k: v for k, v in lid.items()
            if k in catalog.archetypes["enclosure_lid_snap_v1"].parameters},
    )
    assert _all_pass(findings), [f.message for f in findings]


def test_pair_lamp_bracket_to_socket_cup(catalog):
    """Flagship row: the E27 socket cup screws to the bracket bolt circle
    (mount_bc stated on both sides — the assembly.shared discipline)."""
    findings = _probe(
        catalog, "screw_joint",
        ("lamp_bracket_v1", "mount_bc"), ("lamp_socket_cup_v1", "mount_face"),
        rotate=(180, 0, 0),
        params={"screw": "M4", "count": 4},
        pa={"arm_len": "160mm", "arm_w": "36mm", "arm_h": "36mm",
            "channel_d": "8mm", "mount_screw": "M4", "mount_screw_count": 4,
            "mount_inset": "26mm", "screw": "M4", "mount_bc": "24mm"},
        pb={"mount_bc": "24mm", "screw_count": 4, "screw": "M4",
            "exit_d": "9mm"},
    )
    assert _all_pass(findings), [f.message for f in findings]


def test_pair_rail_slider_accepts_adapter_foot(catalog):
    """Flagship row slider<->adapter (gap CLOSED): the shoe's slot is a
    legitimate short socket — rail_slider_body publishes the socket-
    convention frame keys (groove_top_w = the opening, socket_top_v = the
    mouth plane) and the adapter's male foot rides it when the slider is
    parameterized by the same socket numbers (12/17/6 here). The adapter
    enters the downward-opening slot from below: rotate [180, 0, 0]."""
    findings = _probe(
        catalog, "dovetail_joint",
        ("rail_slider_v1", "rail_slot"), ("rail_plate_adapter_v1", "mount_foot"),
        rotate=(180, 0, 0),
        pa={"rail_top_w": "16.65mm", "rail_h": "5.7mm", "rail_angle": 23.68,
            "travel": "40mm"},
        pb={"adapter_l": "30mm"},
    )
    assert _all_pass(findings), [f.message for f in findings]


def test_pair_pegboard_bosses_receive_box_floor(catalog):
    """Flagship row carrier<->box (gap CLOSED): the pegboard face plate
    grows a mount boss pattern (mount_pilot_*, boss_pattern now works on
    plate bases) and the enclosure opts into a countersunk floor-hole
    stack (mount_holes: 2) anchored on its published `base` datum — the
    box screws down onto the carrier's boss tops."""
    findings = _probe(
        catalog, "screw_joint",
        ("pegboard_mount_base_v1", "mount_top"), ("enclosure_base_v1", "base"),
        params={"screw": "M3", "count": 2, "pilots": "mount_pilot"},
        pa={"plate_l": "80mm", "plate_w": "80mm"},
        pb={"mount_holes": 2, "mount_span": "30mm", "mount_cy": "10mm",
            "mount_screw": "M3"},
    )
    assert _all_pass(findings), [f.message for f in findings]


def test_default_enclosure_still_has_no_floor_holes(catalog):
    """The mount stack is an OPT-IN: a default box floor stays solid."""
    form = _form(catalog, "enclosure_base_v1")
    assert len(form.holes) == 0
    assert "base" in form.datums
