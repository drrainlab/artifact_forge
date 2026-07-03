"""The voronoi ring, geometry level: radial cuts are real, the finger
passes, the report is deterministic, support-free stays a measured verdict."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.compiler.pipeline import run_build  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
RING = EXAMPLES / "mens_ring_voronoi.yaml"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("ring")
    return run_build(RING, out, None)


def test_ring_builds_green(built):
    assert built["score"]["status"] == "pass"
    hr = built["honesty_report"]
    assert set(hr["built_features"]) >= {"ring_band", "voronoi_field"}
    checks = {f["check"]: f["status"] for f in built.get("findings", [])}
    # non-pass findings only — absence means PASS
    assert checks.get("topology.hex_field_present") is None
    assert checks.get("topology.revolve_cavity_open") is None


def test_opening_span_is_a_measured_verdict(built, tmp_path):
    """DoD: support-free is reported as a measured span, never a claim."""
    findings = pytest.importorskip("yaml").safe_load(
        (Path(built["exports"]["stl"]).parent / "findings.yaml").read_text()
    )["findings"]
    span = next(f for f in findings if f["check"] == "manufacturing.max_opening_span")
    assert span["measured"] is not None and 0 < span["measured"] <= 12.0
    assert "bridges fine" in span["message"]


def test_report_deterministic(built, tmp_path):
    again = run_build(RING, tmp_path, None)
    assert again["score"] == built["score"]
    assert again["compile"]["field_cut"] == built["compile"]["field_cut"]
