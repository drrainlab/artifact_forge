"""forge build — the CAD half of the pipeline. Imports cadquery (via the
compiler/cad modules), so the CLI loads this lazily.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..cad.geometry import Geometry
from ..core.findings import Finding, Status
from ..form.part import PartForm
from ..pipeline import PipelineFailure, run_pre_cad
from .solids import compile_part


def orient_for_print(geometry: Geometry, form: PartForm) -> Geometry:
    """Bake the intended PRINT orientation into the exported solid, so the
    part lands on the slicer bed the way it must actually print — the
    lesson of a real slicer session where the part-frame STL sat hook-down.
    Validators always measure in the part frame; only exports go through
    here. "side_profile": the section lies on the bed, extrusion axis (X)
    points up — for a constant-section extrusion that orientation has zero
    overhangs by construction."""
    if form.print_orientation != "side_profile":
        return geometry
    wp = geometry.workplane.rotate((0, 0, 0), (0, 1, 0), -90.0)
    zmin = wp.val().BoundingBox().zmin
    if abs(zmin) > 1e-9:
        wp = wp.translate((0, 0, -zmin))
    return Geometry(wp)


def run_build(product_path: Path, out_dir: Path, strict_flag: bool | None) -> dict[str, Any]:
    state = run_pre_cad(product_path, strict_flag)
    out, _ = run_build_from_state(state, out_dir / state.instance.id)
    return out


def run_build_from_state(state, target: Path) -> tuple[dict[str, Any], "object"]:
    """The per-part build core — one compiled, validated, exported part.
    The assembly pipeline runs each part through exactly this and keeps
    the returned part-frame Geometry for the assembled-pose fit probes."""
    state.enforce_strict()  # never compile a form that failed its own IR
    if state.form is None:
        raise PipelineFailure("parameters did not resolve; nothing to build", code=4)

    geometry, log = compile_part(state.form)

    state.report.extend(_run_geometry_validators(state, geometry))

    oriented = orient_for_print(geometry, state.form)
    stl = oriented.export_stl(target / "part.stl")
    step = oriented.export_step(target / "part.step")

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
    out["exports"] = {
        "stl": str(stl),
        "step": str(step),
        "print_orientation": state.form.print_orientation,
    }
    out["status"] = state.report.status.value
    out["findings"] = [
        f.to_dict() for f in state.report.findings if f.status is not Status.PASS
    ]

    _finalize(state, geometry, out, target)

    state.enforce_strict()
    return out, geometry


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
