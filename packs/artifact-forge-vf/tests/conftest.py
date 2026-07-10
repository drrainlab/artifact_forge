"""Pack test bootstrap: register the VF pack (ops/checks/joints/probes +
catalog data) before any test touches the registries — the same thing
load_catalog() does in every real pipeline."""
from __future__ import annotations

from artifact_forge_ng.packs import load_packs

load_packs()
