"""Wave A1: the compat matrix is DERIVED — no hand-written table exists."""

import pytest

from artifact_forge_ng.catalog.compat import compat_matrix, render_compat
from artifact_forge_ng.catalog.loader import load_catalog


@pytest.fixture(scope="module")
def matrix():
    return compat_matrix(load_catalog())


def _mates(matrix):
    return {(m["a"], m["b"]) for m in matrix["mates"] if m["compatible"]}


def test_both_swap_families_are_in_the_matrix(matrix):
    mates = _mates(matrix)
    assert ("coco_cassette_v1.seat", "water_rail_v1.cassette_seat") in mates
    assert ("sprout_cassette_v1.seat", "water_rail_v1.cassette_seat") in mates
    assert (
        "flashlight_adapter_25_v1.mount_foot",
        "forearm_cuff_socket_v1.payload_socket",
    ) in mates
    assert (
        "forearm_cuff_socket_v1.payload_socket",
        "rail_plate_adapter_v1.mount_foot",
    ) in mates


def test_rail_self_mates_across_instances(matrix):
    assert ("water_rail_v1.line_east", "water_rail_v1.line_west") in _mates(matrix)


def test_same_gender_ports_do_not_mate(matrix):
    same_seat = [m for m in matrix["mates"]
                 if {m["a"], m["b"]} == {"coco_cassette_v1.seat",
                                         "sprout_cassette_v1.seat"}]
    assert same_seat and not same_seat[0]["compatible"]
    assert any("complement" in p for p in same_seat[0]["problems"])


def test_render_is_human_readable(matrix):
    text = render_compat(matrix)
    assert "compatible mates" in text
    assert "dovetail_rail" in text
