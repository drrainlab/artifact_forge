from pathlib import Path

import pytest

from artifact_forge_ng.pipeline import run_pre_cad

EXAMPLES = sorted((Path(__file__).parents[1] / "examples").rglob("*.yaml"),
                  key=lambda p: p.name)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_validates(path):
    state = run_pre_cad(path, strict_flag=True)
    assert state.report.status.value == "pass", path.name
