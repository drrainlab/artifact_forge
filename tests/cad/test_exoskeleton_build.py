"""Bio-3 acceptance: the exoskeleton rib graph becomes REAL welded
material, the organic windows are verified real cuts, and the three bio
features flip to honestly BUILT — with the physical negative (skip the
weld -> the materialization probe fails the strict build loudly)."""

from pathlib import Path

import pytest
import yaml

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.compiler.pipeline import (  # noqa: E402
    run_build,
    run_build_from_state,
)
from artifact_forge_ng.core.findings import Level, Status  # noqa: E402
from artifact_forge_ng.pipeline import PipelineFailure, run_pre_cad  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
DEMO = EXAMPLES / "biomorphic_exoskeleton_demo_plate.yaml"

BIO_FEATURES = {"biomorphic_exoskeleton", "organic_windows", "load_path_ribs"}


@pytest.fixture(scope="module")
def demo_build(tmp_path_factory):
    target = tmp_path_factory.mktemp("exo") / "demo"
    state = run_pre_cad(DEMO, None)
    out, geometry = run_build_from_state(state, target)
    return state, out, geometry, target


def test_single_connected_valid_solid(demo_build):
    state, _, geometry, _ = demo_build
    assert geometry.solid_count() == 1
    assert geometry.is_valid()
    assert state.report.passed("topology.single_connected_solid")


def test_materialization_probes_pass(demo_build):
    state, out, _, _ = demo_build
    assert state.report.passed("topology.exoskeleton_ribs_materialized")
    assert state.report.passed("topology.organic_windows_open")
    assert out["compile"]["exoskeleton_ribs_welded"] > 0
    assert out["compile"]["field_cut"] is True


def test_bio_features_flip_to_built(demo_build):
    """The honesty flip: after a CAD build the bio features are BUILT
    (all their verified_by checks ran and passed). The validate-side twin
    (tests/form/test_exoskeleton_applicator.py::
    test_bio_features_supported_but_not_built) pins that a pure validate
    still reports them missing — the asymmetry is the point."""
    _, out, _, target = demo_build
    built = set(out["honesty_report"]["built_features"])
    assert BIO_FEATURES <= built
    assert not BIO_FEATURES & set(out["honesty_report"]["missing_features"])
    doc = yaml.safe_load((target / "honesty_report.yaml").read_text())
    assert BIO_FEATURES <= set(doc["built_features"])


def test_grade_survives_manufacturing_checks(demo_build):
    """Proud rounded ribs may WARN the manufacturing suite — acceptable;
    a critical FAIL (or a failed status) is not."""
    state, out, _, _ = demo_build
    assert out["status"] == "pass"
    assert state.report.critical_failures() == []
    man_fails = [
        f for f in state.report.by_level(Level.MANUFACTURING)
        if f.status is Status.FAIL
    ]
    assert not man_fails, [f.check for f in man_fails]


def test_stl_exported_and_ribs_add_material(demo_build, tmp_path, monkeypatch):
    """The exported STL exists, and the ribs are REAL added volume: the
    same product compiled with the welding stage skipped is measurably
    smaller and fails the materialization probe."""
    _, _, geometry, target = demo_build
    stl = target / "part.stl"
    assert stl.exists() and stl.stat().st_size > 10_000
    full_vol = geometry.workplane.val().Volume()

    import artifact_forge_ng.compiler.solids as solids_mod

    monkeypatch.setattr(solids_mod, "build_exoskeleton_solid", lambda form: None)
    state = run_pre_cad(DEMO, False)  # non-strict: we want the bare geometry
    _, bare = run_build_from_state(state, tmp_path / "bare")
    bare_vol = bare.workplane.val().Volume()
    assert full_vol > bare_vol + 500.0  # ribs are material, not paint
    assert not state.report.passed("topology.exoskeleton_ribs_materialized")
    bio_built = BIO_FEATURES & set(state.capability.built_features)
    assert bio_built <= {"organic_windows"}  # windows still cut; ribs gone


def test_skipping_the_weld_fails_strict(tmp_path, monkeypatch):
    """The mutation negative: a build that never welds the ribs must FAIL
    strict, naming the materialization check."""
    import artifact_forge_ng.compiler.solids as solids_mod

    monkeypatch.setattr(solids_mod, "build_exoskeleton_solid", lambda form: None)
    with pytest.raises(PipelineFailure) as exc:
        run_build(DEMO, tmp_path, None)
    assert "exoskeleton_ribs_materialized" in str(exc.value)
