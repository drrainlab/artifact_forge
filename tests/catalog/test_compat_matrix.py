"""Wave A1: the compat matrix is DERIVED — no hand-written table exists."""

import pytest

from artifact_forge_ng.catalog.compat import compat_matrix, render_compat
from artifact_forge_ng.catalog.loader import load_catalog


@pytest.fixture(scope="module")
def matrix():
    return compat_matrix(load_catalog())


def _mates(matrix):
    return {(m["a"], m["b"]) for m in matrix["mates"] if m["compatible"]}


def test_wearable_swap_family_is_in_the_matrix(matrix):
    mates = _mates(matrix)
    assert (
        "flashlight_adapter_25_v1.mount_foot",
        "forearm_cuff_socket_v1.payload_socket",
    ) in mates
    assert (
        "forearm_cuff_socket_v1.payload_socket",
        "rail_plate_adapter_v1.mount_foot",
    ) in mates


def test_render_is_human_readable(matrix):
    text = render_compat(matrix)
    assert "compatible mates" in text
    assert "dovetail_rail" in text
