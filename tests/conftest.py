"""Session bootstrap: point the repo-level local catalog at the test
fixture dir, so the local-merge mechanism is exercised hermetically and
the suite never depends on a developer's private catalog/local/."""
import os
from pathlib import Path

os.environ.setdefault(
    "ARTIFACT_FORGE_LOCAL_CATALOG",
    str(Path(__file__).parent / "data" / "local_catalog"),
)


import pytest


@pytest.fixture(autouse=True, scope="session")
def _tmp_build_library(tmp_path_factory):
    """EVERY test builds into a throwaway library — the developer's real
    .artifact-forge/library must never grow (or be read) from the suite.
    SESSION scope on purpose: module-scoped build fixtures (e.g. the
    voronoi ring) execute before function-scoped autouse fixtures and
    would leak into the real library otherwise."""
    from artifact_forge_ng.store import registry

    old = registry.LIBRARY_ROOT
    registry.LIBRARY_ROOT = tmp_path_factory.mktemp("build_library")
    yield
    registry.LIBRARY_ROOT = old
