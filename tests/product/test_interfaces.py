"""Wave A1 interface layer: the type registry, InterfaceSpec validation,
the pure mate rule set, and the loader's fail-fast binding."""

import pytest
from pydantic import ValidationError

from artifact_forge_ng.product.interfaces import (
    INTERFACE_TYPES, InterfaceSpec, mate_problems,
)

USER_VOCABULARY = {
    "screw_pattern", "heatset_insert_pattern", "strap_slot_pair",
    "cylindrical_payload_socket", "dovetail_rail", "snap_joint",
    "tongue_groove", "removable_insert", "fluid_inlet", "fluid_outlet",
    "cable_pass",
    # external-hardware tube port (mates a silicone hose, not a
    # printed part — the tube lands in BOM-lite)
    "hose_port",
    # rail groove seated on an aluminum profile carrier
    "profile_seat",
}


def _spec(**kw):
    base = {"id": "p", "type": "dovetail_rail", "gender": "female",
            "datum": "d"}
    base.update(kw)
    return InterfaceSpec.model_validate(base)


def test_registry_is_exactly_the_a1_vocabulary():
    assert set(INTERFACE_TYPES) == USER_VOCABULARY


def test_unknown_type_rejected():
    with pytest.raises(ValidationError, match="unknown interface type"):
        _spec(type="magnetic_coupling")


def test_clearance_parses_quantities():
    assert _spec(clearance="0.25mm").clearance == 0.25


def test_mate_same_type_complementary_genders():
    a = _spec(id="sock", gender="female")
    b = _spec(id="foot", gender="male")
    assert mate_problems(a, b, ("cuff", "wearable_cuff"),
                         ("adapter", "payload_adapter")) == []


def test_mate_rejects_same_gender():
    a, b = _spec(gender="male"), _spec(gender="male")
    problems = mate_problems(a, b, ("x", "cx"), ("y", "cy"))
    assert any("complement" in p for p in problems)


def test_mate_rejects_type_mismatch():
    a = _spec(type="dovetail_rail", gender="male")
    b = _spec(type="tongue_groove", gender="female")
    assert any("types differ" in p
               for p in mate_problems(a, b, ("x", "cx"), ("y", "cy")))


def test_accepts_filters_both_directions():
    a = _spec(gender="female", accepts=["payload_adapter"])
    b = _spec(gender="male")
    ok = mate_problems(a, b, ("cuff", "wearable_cuff"),
                       ("ad", "payload_adapter"))
    assert ok == []
    bad = mate_problems(a, b, ("cuff", "wearable_cuff"), ("hook", "wall_hook"))
    assert any("accepts" in p for p in bad)


def test_joint_must_realize_the_type():
    a = _spec(gender="female")
    b = _spec(gender="male")
    bad = mate_problems(a, b, ("x", "cx"), ("y", "cy"),
                        joint_type="screw_joint")
    assert any("does not realize" in p for p in bad)
    ok = mate_problems(a, b, ("x", "cx"), ("y", "cy"),
                       joint_type="dovetail_joint")
    assert ok == []


def test_declared_ahead_of_joint_is_an_honest_problem():
    a = _spec(type="cable_pass", gender="neutral")
    b = _spec(type="cable_pass", gender="neutral")
    bad = mate_problems(a, b, ("x", "cx"), ("y", "cy"),
                        joint_type="screw_joint")
    assert any("no realizing joint yet" in p for p in bad)


def test_clearance_disagreement_reported():
    a = _spec(gender="female", clearance=0.25)
    b = _spec(gender="male", clearance=0.8)
    assert any("disagree" in p
               for p in mate_problems(a, b, ("x", "cx"), ("y", "cy")))


# -- loader binding ---------------------------------------------------------

def test_loader_binds_interfaces_fail_fast():
    from artifact_forge_ng.catalog.loader import load_catalog

    catalog = load_catalog()
    cuff = catalog.archetypes["forearm_cuff_socket_v1"]
    port = next(i for i in cuff.interfaces if i.id == "payload_socket")
    assert port.type == "dovetail_rail"
    assert port.gender == "female"
    assert port.region == "socket_crown"

    # gender illegal for a neutral-only type
    with pytest.raises(ValidationError):
        InterfaceSpec.model_validate(
            {"id": "s", "type": "strap_slot_pair", "gender": "banana",
             "datum": "d"})

# -- A1.5: port frames -------------------------------------------------------

def test_frame_requires_axis_tokens_and_orthogonality():
    from artifact_forge_ng.product.interfaces import FrameSpec

    f = FrameSpec.model_validate({"normal": "+Z", "up": "+Y", "axis": "+X"})
    assert f.vectors() == ((0, 0, 1), (0, 1, 0))
    with pytest.raises(ValidationError, match="axis token"):
        FrameSpec.model_validate({"normal": "up", "up": "+Y"})
    with pytest.raises(ValidationError, match="not.*orthogonal"):
        FrameSpec.model_validate({"normal": "+Z", "up": "-Z"})


def test_fluid_types_cross_mate():
    from artifact_forge_ng.product.interfaces import types_mate

    assert types_mate("fluid_outlet", "fluid_inlet")
    assert types_mate("fluid_inlet", "fluid_outlet")
    assert not types_mate("fluid_inlet", "dovetail_rail")
    out = _spec(type="fluid_outlet", gender="male",
                frame={"normal": "-Y", "up": "+Z", "axis": "-Y"})
    inl = _spec(type="fluid_inlet", gender="female",
                frame={"normal": "+Y", "up": "+Z", "axis": "+Y"})
    assert mate_problems(out, inl, ("a", "ca"), ("b", "cb"),
                         joint_type="fluid_joint") == []


def test_every_catalog_port_declares_a_frame():
    """A1.5 hardening: the deprecation window is CLOSED for the builtin
    catalog — frameless ports may only exist outside it."""
    from artifact_forge_ng.catalog.loader import load_catalog

    frameless = [
        f"{a.id}.{i.id}"
        for a in load_catalog().archetypes.values()
        for i in a.interfaces if i.frame is None
    ]
    assert frameless == []
