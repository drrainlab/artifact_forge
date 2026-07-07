"""Golden tests for apply_biomorphic_exoskeleton / add_bone_windows on the
stable demo product (biomorphic_exoskeleton_demo_plate.yaml): green form
checks on the IR, honest refusals (second skeleton, cylindrical panel),
seed stability, debug dumps, and the supported-but-NOT-built honesty
asymmetry that defines Bio-2."""

import json
import zlib
from pathlib import Path

from artifact_forge_ng.archetypes import builder_for
from artifact_forge_ng.catalog.loader import load_catalog, load_instance
from artifact_forge_ng.cli import run_validate
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.exoskeleton.debug import dump_exoskeleton_debug
from artifact_forge_ng.form.exoskeleton.masks import EXO_PROTECTED_ROLES
from artifact_forge_ng.form.part import FaceWindow
from artifact_forge_ng.form.regions import Rect2D
from artifact_forge_ng.modifiers import apply_modifiers
from artifact_forge_ng.modifiers.common import PROTECTED_ROLES
from artifact_forge_ng.modifiers.exoskeleton import (
    add_bone_windows,
    apply_biomorphic_exoskeleton,
)
from artifact_forge_ng.modifiers.fields import add_vein_ribs
from artifact_forge_ng.pipeline import run_pre_cad
from artifact_forge_ng.product.capability import mark_built
from artifact_forge_ng.product.instance import ModifierUse, ProductInstance
from artifact_forge_ng.product.resolve import resolve_params

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
DEMO = EXAMPLES / "biomorphic_exoskeleton_demo_plate.yaml"

EXO_CHECKS = (
    "form.rib_graph_connected",
    "form.no_rib_islands",
    "form.rib_roots_touch_substrate",
    "form.min_rib_diameter_ok",
    "form.windows_inside_safe_regions",
    "form.min_ligament_ok",
)


def build_form_with_modifiers(path=DEMO, mutate=None):
    catalog = load_catalog()
    instance = load_instance(path)
    if mutate:
        data = instance.model_dump(by_alias=True)
        mutate(data)
        instance = ProductInstance.model_validate(data)
    archetype = catalog.archetypes[instance.archetype_id]
    resolved = resolve_params(archetype, instance)
    assert resolved.ok
    form = builder_for(archetype)(resolved, archetype, instance)
    findings = apply_modifiers(
        form, instance.modifiers, catalog.modifiers_for(instance), archetype
    )
    return form, findings, archetype


def test_demo_validates_strict():
    out = run_validate(DEMO, strict_flag=None)
    assert out["status"] == "pass"
    assert "debug_ir" not in out  # plain validate writes NOTHING


def test_demo_exoskeleton_checks_all_pass():
    state = run_pre_cad(DEMO, None)
    for check in EXO_CHECKS:
        assert state.report.passed(check), check
    ir = state.form.exoskeleton
    assert ir is not None and ir.region == "center_zone"
    assert len(ir.graph.nodes) >= 10 and len(ir.graph.edges) >= 12
    assert ir.graph.root_nodes and len(ir.windows) >= 6
    organic = [f for f in state.form.fields if f.pattern == "organic"]
    assert len(organic) == 1 and len(organic[0].polygons) == len(ir.windows)
    # the documented fallback-target note (aesthetic_lightening panel)
    notes = [
        f.message for f in state.report.findings
        if f.check == "modifier:apply_biomorphic_exoskeleton"
    ]
    assert any("fallback target" in m for m in notes)


def test_exo_protected_roles_superset_of_global():
    assert PROTECTED_ROLES <= EXO_PROTECTED_ROLES  # sync guard for the mirror


def test_second_exoskeleton_fails():
    def mutate(data):
        data["modifiers"] = data["modifiers"] * 2

    _, findings, _ = build_form_with_modifiers(mutate=mutate)
    fails = [f for f in findings if f.status is Status.FAIL]
    assert fails and "already carries an exoskeleton" in fails[0].message


def test_cylindrical_window_fails_honestly():
    def mutate(data):
        data["modifiers"] = []
        data["requested_features"] = ["mounting_plate_body", "hole_pattern"]

    form, _, archetype = build_form_with_modifiers(mutate=mutate)
    assert form.exoskeleton is None
    form.windows["cyl_zone"] = FaceWindow(
        origin=(0.0, 0.0, 0.0), tilt_deg=0.0,
        window=Rect2D(0.0, 0.0, 40.0, 20.0), depth=2.4,
        mapping="cylindrical", cyl_center=(0.0, 0.0),
        cyl_r=10.0, cyl_r_outer=12.0, cyl_z0=0.0,
    )
    use = ModifierUse(
        id="apply_biomorphic_exoskeleton", target="cyl_zone", params={}
    )
    findings = apply_biomorphic_exoskeleton(form, use, {"seed": 1}, archetype)
    assert findings[0].status is Status.FAIL
    assert "planar" in findings[0].message
    assert form.exoskeleton is None  # refused, nothing half-attached


def test_seed_zero_is_stable_across_runs():
    ir1 = run_pre_cad(DEMO, None).form.exoskeleton
    ir2 = run_pre_cad(DEMO, None).form.exoskeleton
    expected = zlib.crc32(b"biomorphic_exoskeleton_demo_plate") & 0xFFFF
    assert ir1.seed == ir2.seed == expected
    assert ir1.graph == ir2.graph  # tuple equality, whole graph
    assert ir1.windows == ir2.windows


def test_debug_dump_writes_four_schema_tagged_jsons(tmp_path):
    state = run_pre_cad(DEMO, None)
    written = dump_exoskeleton_debug(state.form, tmp_path)
    names = sorted(p.name for p in written)
    assert names == sorted([
        "rib_graph.json", "surface_samples.json",
        "keepout_mask.json", "window_regions.json",
    ])
    for path in written:
        doc = json.loads(path.read_text())
        assert doc["schema"] == "exoskeleton_debug/v1"
        assert doc["product"] == "biomorphic_exoskeleton_demo_plate"
        assert doc["region"] == "center_zone"
    graph_doc = json.loads((tmp_path / "rib_graph.json").read_text())
    assert graph_doc["nodes"] and graph_doc["edges"]
    mask_doc = json.loads((tmp_path / "keepout_mask.json").read_text())
    assert all(m["kind"] in ("rect", "circle") for m in mask_doc["masks"])


def test_bio_features_supported_but_not_built():
    """The Bio-2 honesty asymmetry: validate is green, the IR is attached,
    yet the bio features stay MISSING — their verified_by include the
    topology probes only Bio-3's CAD materialization can pass."""
    state = run_pre_cad(DEMO, None)
    assert "biomorphic_exoskeleton" in state.capability.supported_features
    assert "organic_windows" in state.capability.supported_features
    assert not state.capability.unsupported_features  # strict stays green
    cap = mark_built(state.capability, state.report, state.catalog.features)
    assert "biomorphic_exoskeleton" in cap.missing_features
    assert "organic_windows" in cap.missing_features
    assert "biomorphic_exoskeleton" not in cap.built_features
    assert "organic_windows" not in cap.built_features


def _point_in_poly(p, poly) -> bool:
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, list(poly[1:]) + [poly[0]]):
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def test_no_rib_crosses_a_window():
    """Regression for the inverted duality: on the demo pipeline no rib
    centerline sample may lie inside any final window polygon, and no
    anchor or load seed may sit inside a cut window (the pre-fix
    construction had 39/41 rib centerlines crossing windows)."""
    ir = run_pre_cad(DEMO, None).form.exoskeleton
    assert ir.windows  # the guarantee must be about something real
    for i, j in ir.graph.edges:
        a, b = ir.graph.nodes[i], ir.graph.nodes[j]
        for k in range(11):  # 10 samples per edge, endpoints included
            t = k / 10.0
            p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            assert not any(_point_in_poly(p, w) for w in ir.windows), (
                f"rib ({i},{j}) centerline enters a window at {p}"
            )
    for s in list(ir.anchors) + list(ir.load_seeds):
        assert not any(_point_in_poly(s, w) for w in ir.windows), (
            f"anchor/load seed {s} sits inside a cut window"
        )


def _clamp_lower_form():
    """A side-profile body whose target region has NO declared FaceWindow —
    the exact geometry the AABB fallback would slice through. Since Bio-4M
    stage B the clamp ops DO declare a profile_surface window, so we pop it
    to simulate any legacy/foreign side-profile body."""
    catalog = load_catalog()
    archetype = catalog.archetypes["branch_clamp_lower_v1"]
    instance = ProductInstance.model_validate({
        "schema": "product/v1", "id": "clamp_guard_probe",
        "archetype": "branch_clamp_lower_v1@1",
    })
    resolved = resolve_params(archetype, instance)
    assert resolved.ok
    form = builder_for(archetype)(resolved, archetype, instance)
    assert form.print_orientation == "side_profile"
    assert form.region("outer_shell") is not None
    # Bio-4M stage B: the op now declares the developable canvas
    assert form.windows["outer_shell"].mapping == "profile_surface"
    form.windows.pop("outer_shell")
    return form, archetype


def test_bio_applicators_refuse_side_profile_aabb_fallback():
    """FIX 4: all three bio applicators fail honestly on a side-profile
    body whose target region has no declared face window — instead of
    planting surfaces across the open saddle via the AABB 'top plane'."""
    cases = (
        (apply_biomorphic_exoskeleton, "apply_biomorphic_exoskeleton",
         {"seed": 1}),
        (add_bone_windows, "add_bone_windows", {"seed": 1}),
        (add_vein_ribs, "add_vein_ribs", {"seed": 1, "count": 3}),
    )
    for applicator, mod_id, params in cases:
        form, archetype = _clamp_lower_form()
        use = ModifierUse(id=mod_id, target="outer_shell", params={})
        findings = applicator(form, use, params, archetype)
        fails = [f for f in findings if f.status is Status.FAIL]
        assert fails, f"{mod_id} did not refuse the side-profile AABB"
        assert "no declared face window" in fails[0].message
        assert form.exoskeleton is None
        assert not form.fields and not form.ribs  # nothing half-planted


def test_add_bone_windows_emits_organic_field():
    def mutate(data):
        data["modifiers"] = [{
            "id": "add_bone_windows", "target": "center_zone",
            "params": {"seed": 9, "sites": 12},
        }]
        data["requested_features"] = [
            "mounting_plate_body", "hole_pattern", "organic_windows",
        ]

    form, findings, _ = build_form_with_modifiers(mutate=mutate)
    assert all(f.status is not Status.FAIL for f in findings)
    assert form.exoskeleton is None  # windows only — no graph
    organic = [f for f in form.fields if f.pattern == "organic"]
    assert len(organic) == 1 and len(organic[0].polygons) >= 4
