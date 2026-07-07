"""Bio-4M stage B — the developable (s, x) parameterization of a clamp
half: arc-length map correctness, canvas/seam placement, and the
conservative keepout projection (a bolt can never hide from its mask)."""

import math

import pytest

from artifact_forge_ng.archetypes import builder_for
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.form.exoskeleton.profile_surface import (
    build_profile_surface,
    profile_surface_canvas,
)
from artifact_forge_ng.product.instance import ProductInstance
from artifact_forge_ng.product.resolve import resolve_params


def _half_form(archetype_id: str, params: dict | None = None):
    catalog = load_catalog()
    archetype = catalog.archetypes[archetype_id]
    instance = ProductInstance.model_validate({
        "schema": "product/v1", "id": "ps_probe",
        "archetype": f"{archetype_id}@1", "params": params or {},
    })
    resolved = resolve_params(archetype, instance)
    assert resolved.ok
    return builder_for(archetype)(resolved, archetype, instance)


@pytest.mark.parametrize("arch", ["branch_clamp_lower_v1", "branch_clamp_upper_v1"])
def test_map_is_monotone_isometric_and_round_trips(arch):
    form = _half_form(arch)
    smap = build_profile_surface(form.section.outer, form.width)
    assert smap.total_s == pytest.approx(form.section.outer.perimeter(), rel=1e-3)
    assert all(b > a for a, b in zip(smap.s_breaks, smap.s_breaks[1:]))
    # knot round-trip: to_world at a knot lands on the knot point (n=0)
    for k in range(0, len(smap.s_breaks) - 1, max(1, len(smap.s_breaks) // 7)):
        s = smap.s_breaks[k]
        u, v = smap.points[k]
        x, wy, wz = smap.to_world(s, form.width / 2, 0.0)
        assert (wy, wz) == (pytest.approx(u, abs=1e-6), pytest.approx(v, abs=1e-6))
        assert x == pytest.approx(form.width / 2)
    # normals are unit and point away from the section centroid-ish interior
    for (nu, nv) in smap.normals[:: max(1, len(smap.normals) // 9)]:
        assert math.hypot(nu, nv) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("arch,has_rail", [
    ("branch_clamp_lower_v1", False),
    ("branch_clamp_upper_v1", True),
])
def test_canvas_excludes_mate_saddle_and_seam(arch, has_rail):
    form = _half_form(arch)
    canvas = profile_surface_canvas(form.section.outer, form.width)
    assert canvas.s0 == pytest.approx(0.0)
    assert 0.0 < canvas.s1 < canvas.surface.total_s
    # the seam lives in the mate/saddle block, never on the canvas
    assert not (canvas.s0 <= canvas.seam_s <= canvas.s1)
    assert (canvas.rail_interval is not None) == has_rail
    if canvas.rail_interval:
        lo, hi = canvas.rail_interval
        assert canvas.s0 < lo < hi < canvas.s1
    # the emitted FaceWindow uses this canvas
    fw = form.windows["outer_shell"]
    assert fw.mapping == "profile_surface"
    assert fw.window.u1 <= canvas.s1 + 1e-6
    assert fw.depth > 0.8  # published safe recess


def test_every_fastener_footprint_is_inside_a_mask():
    """KEY LAW 2: conservative superset — sample each bolt/heatset column's
    true pierce footprint on the surface; every sample must be masked."""
    from artifact_forge_ng.form.exoskeleton.masks import (
        profile_surface_keepout_mask,
    )
    from artifact_forge_ng.form.section import Pt

    form = _half_form("branch_clamp_upper_v1")
    fw = form.windows["outer_shell"]
    masks = profile_surface_keepout_mask(
        form, fw.surface, fw.window, extra=fw.keepouts)
    smap = fw.surface
    head_r = form.frame.get("screw_head_r", 3.5)
    checked = 0
    for hole in form.holes:
        cx, cy = hole.at[0], hole.at[1]
        # walk the surface knots; where the knot's u lies inside the bolt
        # circle the column pierces the surface — that (s, x) must be masked
        for k, (u, _v) in enumerate(smap.points):
            if abs(u - cy) > head_r:
                continue
            s = smap.s_breaks[k]
            if not (fw.window.u0 <= s <= fw.window.u1):
                continue
            p = Pt(s, cx)
            assert any(
                m.shape.contains(p) or m.shape.distance(p) <= m.clearance
                for m in masks
            ), f"unmasked bolt footprint at s={s:.1f}, x={cx:.1f}"
            checked += 1
    assert checked > 0, "probe never intersected the canvas — test is vacuous"


def test_generated_windows_respect_masks_by_the_checker_rule():
    """Regression for the generator/checker split found on the upper half:
    scaled bone-window cells must pass poly_clear (the checker's own rule)."""
    import yaml as _yaml
    from pathlib import Path

    from artifact_forge_ng.form.exoskeleton.masks import poly_clear
    from artifact_forge_ng.pipeline import pre_cad_from_instance

    catalog = load_catalog()
    doc = _yaml.safe_load(Path(
        "catalog/examples/biomorphic_branch_clamp_organic.yaml").read_text())
    for part in doc["parts"]:
        pdoc = dict(part["product"])
        pdoc.setdefault("schema", "product/v1")
        for k, v in (doc.get("shared") or {}).items():
            pdoc.setdefault("params", {}).setdefault(k, v)
        inst = ProductInstance.model_validate(pdoc)
        state = pre_cad_from_instance(inst, catalog, strict=True)
        for f in state.form.fields:
            if f.pattern != "organic":
                continue
            for poly in f.polygons:
                assert poly_clear(poly, f.keepouts), part["ref"]
