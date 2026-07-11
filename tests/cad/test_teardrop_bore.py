"""BoreFeature.roof="teardrop": a horizontal bore whose ceiling
is two 45-degree chords meeting at a peak — self-supporting on FDM. The
teardrop volume is a SUPERSET of the cylinder (probes stay valid), the
peak reaches r*sqrt(2), and vertical bores ignore the roof."""

import math

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.cad.bores import cut_bore  # noqa: E402
from artifact_forge_ng.form.part import BoreFeature  # noqa: E402
from artifact_forge_ng.validators.topology import box_probe, solid_fraction  # noqa: E402

R = 5.0  # d10 test bore through a 40x40x40 box centered at origin


def _box() -> cq.Workplane:
    return cq.Workplane("XY").box(40, 40, 40, centered=(True, True, False))


def _teardrop(axis: str = "Y", roof: str = "teardrop") -> cq.Workplane:
    body, ok = cut_bore(_box(), BoreFeature(
        name="drain", axis=axis, center=(0.0, 0.0, 20.0), d=2 * R,
        span=(-20.0, 20.0), roof=roof,
    ))
    assert ok
    return body


def test_cylinder_part_is_void_and_superset():
    body = _teardrop()
    # the full cylinder volume is void (superset guarantee)
    cyl = box_probe(-R * 0.6, -15.0, 20.0 - R * 0.6, R * 0.6, 15.0, 20.0 + R * 0.6)
    assert solid_fraction(body, cyl) < 0.05
    # material removed vs round bore: teardrop cuts MORE
    round_body = _teardrop(roof="round")
    assert body.val().Volume() < round_body.val().Volume() - 10.0


def test_peak_reaches_r_sqrt2():
    body = _teardrop()
    peak_z = 20.0 + R * math.sqrt(2.0)
    # void just below the peak on the axis plane...
    below = box_probe(-0.4, -15.0, peak_z - 1.2, 0.4, 15.0, peak_z - 0.3)
    assert solid_fraction(body, below) < 0.05
    # ...and solid just above it
    above = box_probe(-0.4, -15.0, peak_z + 0.3, 0.4, 15.0, peak_z + 1.2)
    assert solid_fraction(body, above) > 0.9


def test_45_degree_flanks_are_material():
    """Outside the 45-degree chords (but inside the round ceiling's bbox
    corner region) the material SURVIVES — the roof is chords, not a box."""
    body = _teardrop()
    # a point above the 45-degree tangent point, outside the chord line:
    # at x = 0.8*R the chord height is k + (k - 0.8R) ... simpler: the
    # corner (x ~ 0.9R, z ~ center + 0.9R) lies outside the teardrop
    corner = box_probe(0.75 * R, -15.0, 20.0 + 0.75 * R, 0.95 * R, 15.0, 20.0 + 0.95 * R)
    assert solid_fraction(body, corner) > 0.9
    round_body = _teardrop(roof="round")
    assert solid_fraction(round_body, corner) > 0.9  # round also keeps it


def test_vertical_bore_ignores_roof():
    a = cut_bore(_box(), BoreFeature(
        name="v", axis="Z", center=(0.0, 0.0, 0.0), d=2 * R,
        span=(0.0, 40.0), roof="teardrop"))[0]
    b = cut_bore(_box(), BoreFeature(
        name="v", axis="Z", center=(0.0, 0.0, 0.0), d=2 * R,
        span=(0.0, 40.0)))[0]
    assert a.val().Volume() == pytest.approx(b.val().Volume(), rel=1e-6)


def test_axis_x_teardrop_also_points_up():
    body = _teardrop(axis="X")
    peak_z = 20.0 + R * math.sqrt(2.0)
    below = box_probe(-15.0, -0.4, peak_z - 1.2, 15.0, 0.4, peak_z - 0.3)
    assert solid_fraction(body, below) < 0.05
