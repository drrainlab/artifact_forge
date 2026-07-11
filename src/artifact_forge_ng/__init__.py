"""Artifact Forge — a deterministic-first YAML Product Grammar engine for
3D-printable parts.

A product is YAML bound against a typed catalog (archetypes, features,
modifiers, interfaces); the engine builds a CAD-free Form IR, measures it
with registered checks, and only then compiles solids. The honesty rule
runs through every layer: a feature is only claimed after its validators
PASS, and an unknown op / check / joint name is a load error, never a
silent skip.

Quickstart::

    from pathlib import Path
    from artifact_forge_ng import run_pre_cad

    state = run_pre_cad(Path("catalog/examples/desk_cable_clip_20mm.yaml"),
                        strict_flag=None)

Importing this package never loads the CAD kernel — cadquery is only
required by the compile step (the ``cad`` extra). Domain packs plug in via
the ``artifact_forge_ng.packs`` entry-point group (see
:mod:`artifact_forge_ng.packs`).
"""
from __future__ import annotations

__version__ = "0.1.0"

from .catalog.loader import CatalogError, load_catalog, load_instance
from .core.findings import Finding, Level, Status
from .form.part import PartForm
from .packs import PackContext, PackError, load_packs
from .pipeline import PipelineFailure, PipelineState, pre_cad_from_instance, run_pre_cad

__all__ = [
    "__version__",
    "CatalogError",
    "Finding",
    "Level",
    "PackContext",
    "PackError",
    "PartForm",
    "PipelineFailure",
    "PipelineState",
    "Status",
    "load_catalog",
    "load_instance",
    "load_packs",
    "pre_cad_from_instance",
    "run_pre_cad",
]
