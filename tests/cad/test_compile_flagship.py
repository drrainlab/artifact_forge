"""Tier-2: the flagship compiles from its profile into one valid solid with
real features — ported assertion style from v1 test_underdesk_v2_molded."""

import math
from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.archetypes import builder_for  # noqa: E402
from artifact_forge_ng.catalog.loader import load_catalog, load_instance  # noqa: E402
from artifact_forge_ng.compiler.solids import compile_part  # noqa: E402
from artifact_forge_ng.cad.probes import box_probe, channel_probe, solid_fraction  # noqa: E402
from artifact_forge_ng.product.instance import ProductInstance  # noqa: E402
from artifact_forge_ng.product.resolve import resolve_params  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = EXAMPLES / "desk_cable_clip_20mm.yaml"


def build(bundle_d: float | None = None, **param_overrides):
    catalog = load_catalog()
    instance = load_instance(GOLDEN)
    if bundle_d is not None or param_overrides:
        data = instance.model_dump(by_alias=True)
        if bundle_d is not None:
            data["params"]["bundle_d"] = f"{bundle_d}mm"
            # keep dependent params inside their legal ranges
            data["params"]["mouth_gap"] = f"{min(10.0, bundle_d * 0.55):g}mm"
        data["params"].update(param_overrides)
        instance = ProductInstance.model_validate(data)
    archetype = catalog.archetypes[instance.archetype_id]
    resolved = resolve_params(archetype, instance)
    assert resolved.ok, [f.message for f in resolved.findings]
    builder = builder_for(archetype)
    form = builder(resolved, archetype, instance)
    from artifact_forge_ng.modifiers import apply_modifiers

    apply_modifiers(form, instance.modifiers, catalog.modifiers_for(instance), archetype)
    geometry, log = compile_part(form)
    return geometry, log, form


@pytest.fixture(scope="module")
def golden_build():
    return build()


@pytest.mark.parametrize("bundle_d", [8.0, 20.0, 40.0])
def test_one_valid_solid_across_range(bundle_d):
    geometry, _, _ = build(bundle_d)
    assert geometry.solid_count() == 1
    assert geometry.is_valid()


def test_cavity_is_real_void(golden_build):
    geometry, _, form = golden_build
    bb = geometry.bounding_box()
    box_volume = bb.width * bb.depth * bb.height
    assert geometry.volume() < box_volume * 0.55  # hollow, not a brick


def test_bbox_matches_ir(golden_build):
    geometry, _, form = golden_build
    lo, hi = form.section.outer.bbox()
    bb = geometry.bounding_box()
    plate = form.plates[0]
    # The flange runs along the cable axis, wider than the hook in X.
    assert bb.xmin == pytest.approx(min(0.0, plate.x0), abs=0.5)
    assert bb.xmax == pytest.approx(max(form.width, plate.x1), abs=0.5)
    # section (u, v) = (y, z); the hook's mouth extends y past the flange
    assert bb.zmin == pytest.approx(lo.v, abs=0.5)
    assert bb.zmax == pytest.approx(plate.z_top, abs=0.5)
    assert bb.ymax == pytest.approx(max(hi.u, plate.y1), abs=0.5)


def test_screw_holes_open(golden_build):
    geometry, log, form = golden_build
    assert log.holes_bored == len(form.holes) == 2
    for hole in form.holes:
        x, y, z_top = hole.at
        probe = channel_probe([(x, y, z_top + 1.0), (x, y, z_top - hole.through - 1.0)], d=3.0)
        frac = solid_fraction(geometry.workplane, probe)
        assert frac < 0.2, f"hole at {hole.at} is blocked (solid fraction {frac:.2f})"


def test_countersinks_present(golden_build):
    geometry, log, form = golden_build
    assert log.holes_countersunk == 2
    head_r = form.frame["screw_head_r"]
    for hole in form.holes:
        x, y, z_top = hole.at
        # A thin annular band just under the top face, outside the bore but
        # inside the head circle — must be partially cut by the cone.
        band = box_probe(
            x - head_r, y - head_r, z_top - 0.4, x + head_r, y + head_r, z_top - 0.05
        )
        frac = solid_fraction(geometry.workplane, band)
        assert frac < 0.9, f"no countersink at {hole.at} (solid fraction {frac:.2f})"


def test_hex_field_removed_material(golden_build):
    geometry, log, form = golden_build
    assert form.fields and form.fields[0].centers
    assert log.field_cut
    field = form.fields[0]
    r_hex = field.cell / math.sqrt(3.0)
    cu, cv = field.centers[len(field.centers) // 2]
    probe = box_probe(
        cu - r_hex * 0.4, cv - r_hex * 0.4, field.plane_z - field.depth,
        cu + r_hex * 0.4, cv + r_hex * 0.4, field.plane_z,
    )
    frac = solid_fraction(geometry.workplane, probe)
    assert frac < 0.3, f"hex cell at ({cu:.1f},{cv:.1f}) not cut (fraction {frac:.2f})"


def test_screw_keepouts_not_perforated(golden_build):
    geometry, _, form = golden_build
    head_r = form.frame["screw_head_r"]
    bore_r = form.frame["screw_clear_d"] / 2.0 + 0.6
    for hole in form.holes:
        x, y, z_top = hole.at
        # The annulus between the bore and the keepout radius must be SOLID
        # (below the countersink depth) — no hex cell ate into it.
        zone = box_probe(
            x - head_r - 1.5, y - head_r - 1.5, z_top - hole.through,
            x + head_r + 1.5, y + head_r + 1.5, z_top - 2.2,
        )
        bore = channel_probe(
            [(x, y, z_top + 1), (x, y, z_top - hole.through - 1)], d=2 * bore_r
        )
        zone_v = solid_fraction(geometry.workplane, zone)
        assert zone_v > 0.75, f"keepout near {hole.at} was perforated ({zone_v:.2f})"
        del bore


def test_exports(golden_build, tmp_path):
    geometry, _, _ = golden_build
    stl = geometry.export_stl(tmp_path / "part.stl")
    step = geometry.export_step(tmp_path / "part.step")
    assert stl.stat().st_size > 10_000
    assert step.stat().st_size > 10_000


def test_forge_build_cli(tmp_path):
    from artifact_forge_ng.cli import main

    code = main(["build", str(GOLDEN), "-o", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "desk_cable_clip_20mm" / "part.stl").exists()
    assert (tmp_path / "desk_cable_clip_20mm" / "part.step").exists()
