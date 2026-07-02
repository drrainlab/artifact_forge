"""The architectural guarantee, as a test: the whole pre-CAD pipeline —
form kernel, builders, CLI validate — must be importable and runnable
without cadquery ever entering sys.modules."""

import subprocess
import sys


def test_form_pipeline_never_imports_cadquery():
    code = (
        "import sys\n"
        "import artifact_forge_ng.form.profiles\n"
        "import artifact_forge_ng.form.validators\n"
        "import artifact_forge_ng.form.silhouette\n"
        "import artifact_forge_ng.form.fields\n"
        "import artifact_forge_ng.archetypes\n"
        "import artifact_forge_ng.cli\n"
        "assert 'cadquery' not in sys.modules, 'cadquery leaked into the form layer'\n"
        "print('clean')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "clean" in result.stdout
