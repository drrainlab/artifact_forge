"""ChannelCutFeature CAD acceptance: the sloped U-channel cutter really
carves an open, monotonically deepening water path — open along the whole
sampled centerline, solid floor beneath it, open through both end faces."""

import math

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.bores import cut_channel  # noqa: E402
from artifact_forge_ng.cad.probes import channel_probe, solid_fraction  # noqa: E402
from artifact_forge_ng.form.part import ChannelCutFeature  # noqa: E402

BODY_L, BODY_W, BODY_H = 100.0, 200.0, 30.0  # X, Y, Z


def make_body():
    return (
        cq.Workplane("XY", origin=(0.0, 0.0, 0.0))
        .rect(BODY_L, BODY_W)
        .extrude(BODY_H)
    )


def make_channel(**over) -> ChannelCutFeature:
    drop = BODY_W * math.tan(math.radians(1.25))
    kw: dict = dict(
        center_x=0.0,
        y0=BODY_W / 2.0,          # inlet at the back (+Y)
        y1=-BODY_W / 2.0,         # outlet at the front (-Y)
        z_top=BODY_H,
        width=16.0,
        depth_start=5.0,          # shallow at the inlet
        depth_end=5.0 + drop,     # deepens toward the outlet
        bottom_r=1.2,
    )
    kw.update(over)
    return ChannelCutFeature(name="water", **kw)


def test_slope_math():
    ch = make_channel()
    assert ch.slope_deg == pytest.approx(1.25, abs=0.01)
    assert ch.floor_z_at(ch.y0) > ch.floor_z_at(ch.y1)  # floor falls to outlet
    mid = (ch.y0 + ch.y1) / 2.0
    assert ch.depth_at(mid) == pytest.approx(
        (ch.depth_start + ch.depth_end) / 2.0
    )


def test_channel_cut_carves_open_sloped_path():
    body = make_body()
    ch = make_channel()
    cut_body, ok = cut_channel(body, ch)
    assert ok, "channel cut must apply"
    assert cut_body.val().Volume() < body.val().Volume()

    # water path open 1mm above the floor along the whole run
    path = channel_probe(ch.centerline(lift=1.0), d=2.0)
    assert solid_fraction(cut_body, path) < 0.05

    # floor solid 1mm below — the channel does not leak into the body
    floor = channel_probe(ch.centerline(lift=-1.0), d=2.0)
    assert solid_fraction(cut_body, floor) > 0.95

    # open through both end faces (the overshoot guarantee): probe just
    # outside each face at the local floor height
    for y in (ch.y0 + 0.5, ch.y1 - 0.5):
        stub = channel_probe(
            [(0.0, y, ch.floor_z_at(y) + 1.0), (0.0, y, ch.z_top + 1.0)], d=2.0
        )
        assert solid_fraction(cut_body, stub) < 0.05, f"end face at y={y} not open"


def test_channel_cut_keeps_one_solid():
    cut_body, ok = cut_channel(make_body(), make_channel())
    assert ok
    assert len(cut_body.solids().vals()) == 1


def test_square_bottom_channel_also_cuts():
    cut_body, ok = cut_channel(make_body(), make_channel(bottom_r=0.0))
    assert ok
    path = channel_probe(make_channel(bottom_r=0.0).centerline(lift=1.0), d=2.0)
    assert solid_fraction(cut_body, path) < 0.05


def test_too_shallow_extrapolation_refuses():
    # depth at the overshot inlet would drop below the bottom radius —
    # the cutter must refuse rather than build a garbage wire
    ch = make_channel(depth_start=1.0, depth_end=1.0 + 4.4)
    body = make_body()
    cut_body, ok = cut_channel(body, ch)
    assert not ok
    assert cut_body.val().Volume() == pytest.approx(body.val().Volume())


def test_ir_validation():
    with pytest.raises(ValueError):
        make_channel(width=0.0)
    with pytest.raises(ValueError):
        make_channel(y0=0.0, y1=0.0)
    with pytest.raises(ValueError):
        make_channel(bottom_r=9.0)  # 2r > width is impossible geometry
    with pytest.raises(ValueError):
        ChannelCutFeature(
            name="x", center_x=0, y0=10, y1=-10, z_top=30,
            width=16, depth_start=5, depth_end=6, axis="X",
        )
