"""VF compat-matrix goldens (moved from core at the R0.5 extraction —
they exercise the pack's rail/cassette interfaces)."""

import pytest

from artifact_forge_ng.catalog.compat import compat_matrix
from artifact_forge_ng.catalog.loader import load_catalog


@pytest.fixture(scope="module")
def matrix():
    return compat_matrix(load_catalog())


def _mates(matrix):
    return {(m["a"], m["b"]) for m in matrix["mates"] if m["compatible"]}


def test_vf_swap_family_is_in_the_matrix(matrix):
    mates = _mates(matrix)
    assert ("coco_cassette_v1.seat", "water_rail_v1.cassette_seat") in mates
    assert ("sprout_cassette_v1.seat", "water_rail_v1.cassette_seat") in mates


def test_rail_self_mates_across_instances(matrix):
    assert ("water_rail_v1.line_east", "water_rail_v1.line_west") in _mates(matrix)


def test_same_gender_ports_do_not_mate(matrix):
    same_seat = [m for m in matrix["mates"]
                 if {m["a"], m["b"]} == {"coco_cassette_v1.seat",
                                         "sprout_cassette_v1.seat"}]
    assert same_seat and not same_seat[0]["compatible"]
    assert any("complement" in p for p in same_seat[0]["problems"])
