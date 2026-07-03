"""Sweep + truss + veins acceptance (geometry level)."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.compiler.pipeline import run_build  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


def test_handle_bar_follows_its_arc(tmp_path):
    out = run_build(EXAMPLES / "drawer_handle_110.yaml", tmp_path, None)
    assert out["score"]["status"] == "pass"
    hr = out["honesty_report"]
    assert "swept_grip_bar" in hr["built_features"]


def test_truss_and_veins(tmp_path):
    out = run_build(EXAMPLES / "truss_beam_180.yaml", tmp_path, None)
    assert "truss_web" in out["honesty_report"]["built_features"]
    out2 = run_build(EXAMPLES / "showcase_vein_plate.yaml", tmp_path, None)
    assert "stiffening_ribs" in out2["honesty_report"]["built_features"]
