"""forge build — the CAD half of the pipeline. Imports cadquery (via the
compiler/cad modules), so the CLI loads this lazily.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.findings import Finding, Status
from ..pipeline import PipelineFailure, run_pre_cad
from .solids import compile_part


def run_build(product_path: Path, out_dir: Path, strict_flag: bool | None) -> dict[str, Any]:
    state = run_pre_cad(product_path, strict_flag)
    state.enforce_strict()  # never compile a form that failed its own IR
    if state.form is None:
        raise PipelineFailure("parameters did not resolve; nothing to build", code=4)

    geometry, log = compile_part(state.form)

    state.report.extend(_run_geometry_validators(state, geometry))

    target = out_dir / state.instance.id
    stl = geometry.export_stl(target / "part.stl")
    step = geometry.export_step(target / "part.step")

    out = state.summary()
    out["compile"] = {
        "holes_bored": log.holes_bored,
        "holes_countersunk": log.holes_countersunk,
        "bores_cut": log.bores_cut,
        "boxes_cut": log.boxes_cut,
        "ribs_welded": log.ribs_welded,
        "field_cut": log.field_cut,
        "blends_applied": log.blends_applied,
        "blends_skipped": log.blends_skipped,
        "notes": log.notes,
    }
    out["exports"] = {"stl": str(stl), "step": str(step)}
    out["status"] = state.report.status.value
    out["findings"] = [
        f.to_dict() for f in state.report.findings if f.status is not Status.PASS
    ]

    _finalize(state, geometry, out, target)

    state.enforce_strict()
    return out


def _run_geometry_validators(state, geometry) -> list[Finding]:
    """Milestone D hook — populated by validators.topology/region/etc."""
    try:
        from ..validators.runner import run_geometry_validators
    except ImportError:
        return []
    return run_geometry_validators(state, geometry)


def _finalize(state, geometry, out: dict[str, Any], target: Path) -> None:
    """Milestone D hook — honesty report, score, silhouette cross-check."""
    try:
        from ..review.honesty import finalize_build
    except ImportError:
        return
    finalize_build(state, geometry, out, target)
