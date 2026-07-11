"""Session bootstrap: point the repo-level local catalog at the test
fixture dir, so the local-merge mechanism is exercised hermetically and
the suite never depends on a developer's private catalog/local/."""
import os
from pathlib import Path

os.environ.setdefault(
    "ARTIFACT_FORGE_LOCAL_CATALOG",
    str(Path(__file__).parent / "data" / "local_catalog"),
)
