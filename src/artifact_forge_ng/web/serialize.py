"""Cockpit view models — the PUBLIC CONTRACT between the engine and every
UI surface (frontend, tests, screenshots, the future authoring studio).

Engine internals never cross this boundary raw: everything the cockpit
shows goes engine state -> these serializers -> JSON. Change the engine
freely; keep these shapes stable.

Shapes (all plain JSON):
  ProductViewModel   {kind, name, archetype, section, regions, holes,
                      bores, pins, ribs, plates, fields, datums, frame,
                      print_orientation, width}
  FindingViewModel   {check, status, level, message, critical, measured,
                      limit, unit, suggestion}
  CapabilityViewModel{requested, supported, missing, buildable}
  ContractViewModel  {must_have, must_not_have, invariants}
  ValidateViewModel  {ok, product, archetype, strict, status, form_checks,
                      params, capability, contract, findings, form}
  PreviewVM          {section: {plane, segments}, holes, bores} | null
  CatalogCardVM      {id, version, object_class, description, summary,
                      status, maturity, pack, pack_name, domain, modes,
                      tier, kind, audience, tags, use_cases, hardware,
                      claims, source_relpath, examples_count,
                      provides_features, validators, allowed_modifiers,
                      regions, contract, parameters}

Errors are ALWAYS FindingViewModels (level "schema"), never tracebacks.
"""

from __future__ import annotations

from typing import Any

from ..core.findings import Finding
from ..form.part import PartForm
from ..form.section import ArcSeg, LineSeg
from ..pipeline import PipelineState
from ..product.archetype import ArchetypeSpec


def error_finding(message: str, check: str = "schema.load") -> dict[str, Any]:
    """A structured error the UI can render like any other finding."""
    return {
        "check": check,
        "status": "fail",
        "level": "schema",
        "message": message,
        "critical": True,
        "measured": None,
        "limit": None,
        "unit": "",
        "suggestion": "",
    }


def finding_vm(f: Finding) -> dict[str, Any]:
    d = f.to_dict()
    # normalize: the UI relies on these keys existing
    for key in ("measured", "limit", "unit", "suggestion", "critical"):
        d.setdefault(key, None if key in ("measured", "limit") else "")
    d.setdefault("critical", False)
    return d


def _pt(p) -> list[float]:
    return [round(p.u, 6), round(p.v, 6)]


def _segment_vm(seg) -> dict[str, Any]:
    if isinstance(seg, ArcSeg):
        return {
            "type": "arc",
            "a": _pt(seg.a),
            "b": _pt(seg.b),
            "center": _pt(seg.center),
            "ccw": bool(seg.ccw),
            "tags": sorted(seg.tags),
        }
    assert isinstance(seg, LineSeg)
    return {"type": "line", "a": _pt(seg.a), "b": _pt(seg.b), "tags": sorted(seg.tags)}


def _box_vm(b) -> dict[str, float]:
    return {"x0": b.x0, "y0": b.y0, "z0": b.z0, "x1": b.x1, "y1": b.y1, "z1": b.z1}


def form_vm(form: PartForm) -> dict[str, Any]:
    """ProductViewModel — the Form IR as the UI sees it."""
    return {
        "kind": form.kind,
        "name": form.name,
        "width": form.width,
        "print_orientation": form.print_orientation,
        "section": {
            "name": form.section.name,
            "plane": form.section.plane,
            "width_axis": form.section.width_axis,
            "segments": [_segment_vm(s) for s in form.section.outer.segments],
        },
        "regions": [
            {"name": r.name, "role": r.role.value, "box": _box_vm(r.box)}
            for r in form.regions
        ],
        "holes": [
            {"at": list(h.at), "screw": h.screw, "through": h.through,
             "countersink": h.countersink, "countersink_face": h.countersink_face,
             "head_style": h.head_style}
            for h in form.holes
        ],
        "bores": [
            {"name": b.name, "axis": b.axis, "center": list(b.center), "d": b.d,
             "span": list(b.span)}
            for b in form.bores
        ],
        "pins": [
            {"name": p.name, "axis": p.axis, "start": list(p.start_point()),
             "end": list(p.end_point()), "d": p.d}
            for p in form.pins
        ],
        "ribs": [{"name": r.name, "box": _box_vm(r.box)} for r in form.ribs],
        "plates": [
            {"name": p.name, "box": {"x0": p.x0, "y0": p.y0, "z0": p.z_bottom,
                                     "x1": p.x1, "y1": p.y1, "z1": p.z_top}}
            for p in form.plates
        ],
        "fields": [
            {"pattern": f.pattern, "cells": len(f.centers) + len(f.polygons),
             "min_ligament": f.min_ligament, "depth": f.depth}
            for f in form.fields
        ],
        "datums": form.datums,
        "frame": {k: round(v, 6) for k, v in form.frame.items()},
        # Compact Bio-2 exoskeleton digest (counts, not dumps — the full IR
        # lives in the --debug-ir JSON artifacts).
        "exoskeleton": None if form.exoskeleton is None else {
            "region": form.exoskeleton.region,
            "nodes": len(form.exoskeleton.graph.nodes),
            "edges": len(form.exoskeleton.graph.edges),
            "windows": len(form.exoskeleton.windows),
            "min_rib_d": form.exoskeleton.min_rib_d,
            "seed": form.exoskeleton.seed,
        },
    }


def preview_vm(form: PartForm) -> dict[str, Any]:
    """Card preview — the exact section silhouette plus hole/bore circles.
    Deliberately tiny: no regions/frame/datums, just enough to draw."""
    from ..core.fasteners import screw_spec

    return {
        "section": {
            "plane": form.section.plane,
            "segments": [_segment_vm(s) for s in form.section.outer.segments],
        },
        "holes": [
            {"at": [h.at[0], h.at[1]], "d": screw_spec(h.screw)["clear"]}
            for h in form.holes
        ],
        "bores": [
            {"center": list(b.center), "d": b.d, "axis": b.axis}
            for b in form.bores
        ],
    }


def catalog_card_vm(spec: ArchetypeSpec, *, status: str, pack: str,
                    pack_name: str, domain: str, source_relpath: str,
                    examples_count: int,
                    regions: list[dict[str, Any]]) -> dict[str, Any]:
    """The catalog card — schema truth plus the loader-derived shelving
    facts (pack/domain come from the LOADER, never from YAML claims)."""
    meta = spec.catalog
    description = spec.description.strip()
    summary = description.split(". ")[0].strip().rstrip(".")
    return {
        "id": spec.id,
        "version": spec.version,
        "object_class": spec.object_class,
        "description": description,
        "summary": summary,
        "status": status,
        "maturity": spec.maturity,
        "pack": pack,
        "pack_name": pack_name,
        "domain": domain,
        "modes": list(meta.modes),
        "tier": meta.tier,
        "kind": meta.kind,
        "audience": meta.audience,
        "tags": list(meta.tags),
        "use_cases": list(meta.use_cases),
        "hardware": list(meta.hardware),
        "claims": dict(meta.claims),
        "source_relpath": source_relpath,
        "examples_count": examples_count,
        "provides_features": list(spec.provides_features),
        "validators": list(spec.validators),
        "allowed_modifiers": list(spec.allowed_modifiers),
        "regions": regions,
        "contract": contract_vm(spec),
        "parameters": [
            {"name": n, "type": p.type, "role": p.role,
             "exposed": bool(p.exposed), "description": p.description,
             "choices": list(p.choices) if p.type == "choice" else None,
             "format": p.format,
             "default": getattr(p.default, "literal", p.default)}
            for n, p in spec.parameters.items()
        ],
    }


def contract_vm(archetype: ArchetypeSpec) -> dict[str, Any]:
    return {
        "must_have": list(archetype.contract.must_have),
        "must_not_have": list(archetype.contract.must_not_have),
        "invariants": list(archetype.contract.invariants),
        "forbidden_forms": list(archetype.forbidden_forms),
    }


def params_vm(archetype: ArchetypeSpec, state: PipelineState) -> list[dict[str, Any]]:
    """Parameter cards: spec + RESOLVED value + resolved bounds — what the
    live sliders render, incl. 'PASS until X' limits."""
    ctx = state.resolved.context
    out = []
    for name, spec in archetype.parameters.items():
        resolved_min = resolved_max = None
        if spec.min is not None:
            try:
                resolved_min = round(spec.min.resolve(ctx), 6)
            except Exception:
                resolved_min = None
        if spec.max is not None:
            try:
                resolved_max = round(spec.max.resolve(ctx), 6)
            except Exception:
                resolved_max = None
        value: Any = ctx.get(name)
        if spec.type == "choice":
            value = state.resolved.choices.get(name)
        out.append({
            "name": name,
            "type": spec.type,
            "role": spec.role,
            "exposed": bool(spec.exposed),
            "locked": spec.role == "safety_locked",
            "description": spec.description,
            "choices": list(spec.choices) if spec.type == "choice" else None,
            "format": spec.format,
            "value": value,
            "min": resolved_min,
            "max": resolved_max,
        })
    return out


def validate_vm(state: PipelineState) -> dict[str, Any]:
    """ValidateViewModel — everything /api/validate returns. The SAME
    summary the CLI prints is embedded verbatim (parity by construction)."""
    summary = state.summary()
    return {
        "ok": summary["status"] != "fail",
        "product": state.instance.id,
        "archetype": state.archetype.ref,
        "strict": state.strict,
        "status": summary["status"],
        "form_checks": summary["form_checks"],
        "capability": summary["capability"],
        "contract": contract_vm(state.archetype),
        "params": params_vm(state.archetype, state),
        "findings": [finding_vm(f) for f in state.report.findings],
        "form": form_vm(state.form) if state.form is not None else None,
        "cli_summary": summary,
    }
