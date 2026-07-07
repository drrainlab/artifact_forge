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
    # Bio-4M fork: style.skin=implicit writes part.stl from the analytic
    # SDF (marching cubes); part.step stays the simplified BRep reference.
    # If the implicit export is impossible the build FAILS loudly — handing
    # back a BRep STL under a skin request would be a hallucination.
    implicit = bool(getattr(state.form.style, "implicit_skin", False))
    skin_meta: dict[str, Any] = {}
    if implicit:
        from .implicit.skin import ImplicitSkinError, export_implicit_skin

        try:
            stl, skin_findings, skin_meta = export_implicit_skin(
                state.form, target / "part.stl"
            )
        except ImplicitSkinError as exc:
            raise PipelineFailure(
                f"style.skin: implicit requested but the implicit engine "
                f"cannot honor it — {exc}",
                code=5,
            ) from exc
        # skin findings land BEFORE _finalize so score/honesty see them
        state.report.extend(skin_findings)
        from ..product.capability import EngineGap

        state.capability.engine_gaps = [
            *state.capability.engine_gaps,
            EngineGap(
                feature_or_check="exports.step",
                suggestion=(
                    "part.step is the simplified BRep reference; production "
                    "output is part.stl (implicit skin)"
                ),
            ),
        ]
    else:
        stl = oriented.export_stl(target / "part.stl")
    step = oriented.export_step(target / "part.step")

    out = state.summary()
    out["compile"] = {
        "holes_bored": log.holes_bored,
        "holes_countersunk": log.holes_countersunk,
        "bores_cut": log.bores_cut,
        "boxes_cut": log.boxes_cut,
        "ribs_welded": log.ribs_welded,
        "exoskeleton_ribs_welded": log.exoskeleton_ribs_welded,
        "field_cut": log.field_cut,
        "blends_applied": log.blends_applied,
        "blends_skipped": log.blends_skipped,
        "notes": log.notes,
    }
    out["exports"] = {
        "stl": str(stl),
        "step": str(step),
        "print_orientation": state.form.print_orientation,
        "stl_source": "implicit" if implicit else "brep",
    }
    if implicit:
        out["exports"]["skin"] = skin_meta
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
