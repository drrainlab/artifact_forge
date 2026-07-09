"""VF-8.1: the FunnelCutFeature primitive — the kernel's first floor that
slopes in BOTH X and Y (ChannelCutFeature slopes along Y only). A downward-
converging (optionally skewed) frustum, subtracted, carves a radial sump."""
import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.bores import cut_funnel  # noqa: E402
from artifact_forge_ng.form.part import FunnelCutFeature  # noqa: E402


def _box(lx, ly, lz, cy=0.0):
    return cq.Workplane("XY", origin=(0, cy, 0)).box(lx, ly, lz, centered=(True, True, False))


def test_symmetric_funnel_carves_a_valid_sump():
    box = _box(60, 60, 20)
    v0 = box.val().Volume()
    f = FunnelCutFeature(name="s", bottom_center=(0.0, 0.0), top_center=(0.0, 0.0),
                         z_top=20.0, z_bottom=8.0, top=(50.0, 50.0), bottom=(12.0, 12.0))
    out, ok = cut_funnel(box, f)
    sol = out.val()
    assert ok and sol.isValid()
    assert len(out.solids().vals()) == 1        # stays one connected solid
    assert sol.Volume() < v0                    # material was removed
    assert abs(sol.BoundingBox().zmin) < 1e-6   # base intact (didn't cut through)


def test_skewed_funnel_mouth_offset_from_opening():
    """The collector's real case: the mouth sits at a back-corner drain while
    the opening spans forward over the tray."""
    box = _box(120, 24, 14, cy=-10.0)
    f = FunnelCutFeature(name="s", bottom_center=(0.0, -12.0), top_center=(0.0, -10.0),
                         z_top=12.0, z_bottom=6.0, top=(70.0, 16.0), bottom=(26.0, 10.0))
    out, ok = cut_funnel(box, f)
    assert ok and out.val().isValid()
    assert len(out.solids().vals()) == 1


def test_non_converging_funnel_is_rejected():
    with pytest.raises(ValueError):  # mouth wider than the opening — no funnel
        FunnelCutFeature(name="s", bottom_center=(0.0, 0.0), top_center=(0.0, 0.0),
                         z_top=20.0, z_bottom=8.0, top=(20.0, 20.0), bottom=(30.0, 30.0))


def test_inverted_z_is_rejected():
    with pytest.raises(ValueError):  # z_top must sit above z_bottom
        FunnelCutFeature(name="s", bottom_center=(0.0, 0.0), top_center=(0.0, 0.0),
                         z_top=5.0, z_bottom=8.0, top=(50.0, 50.0), bottom=(12.0, 12.0))
