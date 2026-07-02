"""Tier-2 for the lamp pair — the channel-continuity money shot and the
revolved cavity, plus the sabotage mutation (a bracket missing its
horizontal run must FAIL loudly)."""

from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.compiler.pipeline import run_build  # noqa: E402
from artifact_forge_ng.pipeline import PipelineFailure  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


def test_socket_cup_builds(tmp_path):
    out = run_build(EXAMPLES / "socket_cup_e27.yaml", tmp_path, None)
    assert out["status"] == "pass"
    honesty = out["honesty_report"]
    assert set(honesty["requested_features"]) <= set(honesty["built_features"])


def test_bracket_builds_with_continuous_channel(tmp_path):
    out = run_build(EXAMPLES / "shelf_lamp_bracket.yaml", tmp_path, None)
    assert out["status"] == "pass"
    assert out["compile"]["bores_cut"] == 2
    assert "wiring_channel" in out["honesty_report"]["built_features"]


def test_sabotaged_bracket_fails_channel_continuity(tmp_path, monkeypatch):
    """Remove the horizontal run bore: entry alone must not count as a
    wiring channel — blocked_channel is a forbidden form."""
    from artifact_forge_ng.archetypes import lamp_bracket

    real_build = lamp_bracket.build_form

    def sabotaged(resolved, archetype, instance):
        form = real_build(resolved, archetype, instance)
        form.bores = [b for b in form.bores if b.name != "channel_run"]
        return form

    monkeypatch.setitem(
        __import__("artifact_forge_ng.archetypes", fromlist=["FORM_BUILDERS"]).FORM_BUILDERS,
        lamp_bracket.SECTION_NAME,
        sabotaged,
    )
    with pytest.raises(PipelineFailure) as exc_info:
        run_build(EXAMPLES / "shelf_lamp_bracket.yaml", tmp_path, None)
    assert "channel_continuous" in str(exc_info.value) or "must_have" in str(
        exc_info.value
    )
