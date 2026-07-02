"""The acceptance demo as a test: edit the golden clip support-free —
function verified preserved, printability verified improved, and the
negative: a patch that breaks its own preserve contract fails loudly."""

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.pipeline import PipelineFailure  # noqa: E402
from artifact_forge_ng.repair.edit import run_edit  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = EXAMPLES / "desk_cable_clip_20mm.yaml"


@pytest.fixture(scope="module")
def edit_result(tmp_path_factory):
    out = tmp_path_factory.mktemp("edit")
    return run_edit(GOLDEN, out, intent_name="make_support_free"), out


def test_edit_passes_and_preserves(edit_result):
    report, _ = edit_result
    er = report["edit_report"]
    assert er["status"] == "pass"
    assert er["preserve_violations"] == []
    preserved = {p["name"] for p in er["preserved"]}
    assert {"bundle_d", "mouth_gap", "lower_lip_len", "upper_lip_len",
            "asymmetric_side_hook", "retaining_lower_lip"} <= preserved


def test_printability_improved(edit_result):
    report, _ = edit_result
    p = report["edit_report"]["printability"]
    assert p["supports_recommended_before"] is True
    assert p["supports_recommended_after"] is False
    assert "teardrop" in p["overhang_after"]["message"]


def test_edited_yaml_is_standalone(edit_result):
    report, out = edit_result
    edited_yaml = Path(report["edit_report"]["edited_yaml"])
    assert edited_yaml.exists()
    doc = yaml.safe_load(edited_yaml.read_text())
    assert doc["params"]["cavity_roof"] == "teardrop"
    from artifact_forge_ng.compiler.pipeline import run_build

    rebuilt = run_build(edited_yaml, out / "rebuild", None)
    assert rebuilt["score"]["status"] == "pass"


def test_teardrop_geometry_real(edit_result):
    """The old cavity bottom region now contains material (the chamfer
    walls), and the cable path is still fully open."""
    report, out = edit_result
    edited_yaml = Path(report["edit_report"]["edited_yaml"])
    from artifact_forge_ng.pipeline import run_pre_cad
    from artifact_forge_ng.compiler.solids import compile_part
    from artifact_forge_ng.cad.probes import box_probe, channel_probe, solid_fraction

    state = run_pre_cad(edited_yaml, False)
    form = state.form
    geometry, _ = compile_part(form)
    f = form.frame
    vc, r_i = f["cavity_center_v"], f["r_cavity"]
    # cable path open
    probe = channel_probe(
        [(-2, 0, vc), (form.width + 2, 0, vc)], d=f["mouth_gap"]
    )
    assert solid_fraction(geometry.workplane, probe) < 0.05
    # the corner pockets beside the old round bottom are now chamfer
    # material: sample near (±r/2, vc - r*0.95)
    corner = box_probe(
        form.width * 0.3, -r_i * 0.8, vc - r_i * 1.05,
        form.width * 0.7, -r_i * 0.55, vc - r_i * 0.85,
    )
    assert solid_fraction(geometry.workplane, corner) > 0.7


def test_negative_self_contradicting_patch_fails(tmp_path):
    """A patch that PRESERVES mouth_gap while CHANGING it must fail the
    preserve contract — the guarantee is checked, not trusted."""
    patch_file = tmp_path / "bad_patch.yaml"
    patch_file.write_text(
        "schema: patch/v1\n"
        "type: functional\n"
        "reason: contradiction\n"
        "preserve: [mouth_gap]\n"
        "params:\n"
        "  mouth_gap: 8mm\n"
    )
    with pytest.raises(PipelineFailure) as exc_info:
        run_edit(GOLDEN, tmp_path / "out", patch_path=patch_file)
    assert "preserve" in str(exc_info.value)
    assert "mouth_gap" in str(exc_info.value)
