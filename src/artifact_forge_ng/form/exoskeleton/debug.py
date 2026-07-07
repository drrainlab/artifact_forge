"""Debug artifacts — the exoskeleton IR dumped as four schema-tagged JSON
files, so a human (or the Cockpit) can SEE the skeleton intent long before
Bio-3 materializes it. Opt-in only: ``forge validate --debug-ir`` and the
build path's honesty hook call this; a plain validate writes nothing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..regions import Circle2D, Rect2D, Region2D

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..part import PartForm

SCHEMA = "exoskeleton_debug/v1"


def _round(value: Any) -> Any:
    """Round every float to 4 decimals, recursively — diffable dumps."""
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, (list, tuple)):
        return [_round(v) for v in value]
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    return value


def _region2d(region: Region2D) -> dict[str, Any]:
    doc: dict[str, Any] = {"name": region.name, "role": region.role.value}
    shape = region.shape
    if isinstance(shape, Rect2D):
        doc.update(kind="rect", u0=shape.u0, v0=shape.v0,
                   u1=shape.u1, v1=shape.v1)
    else:
        assert isinstance(shape, Circle2D)
        doc.update(kind="circle", cx=shape.center.u, cy=shape.center.v,
                   r=shape.r)
    doc["clearance"] = region.clearance
    return doc


def dump_exoskeleton_debug(form: "PartForm", target: Path) -> list[Path]:
    """Write rib_graph.json / surface_samples.json / keepout_mask.json /
    window_regions.json into ``target``; returns the written paths (empty
    when the form carries no exoskeleton)."""
    ir = form.exoskeleton
    if ir is None:
        return []
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    head = {"schema": SCHEMA, "product": form.name, "region": ir.region}
    docs: dict[str, dict[str, Any]] = {
        "rib_graph.json": {
            **head,
            "seed": ir.seed,
            "min_rib_d": ir.min_rib_d,
            "nodes": [list(n) for n in ir.graph.nodes],
            "edges": [list(e) for e in ir.graph.edges],
            "edge_radius": list(ir.graph.edge_radius),
            "node_blend_radius": list(ir.graph.node_blend_radius),
            "root_nodes": list(ir.graph.root_nodes),
            "load_path_edges": [list(e) for e in ir.graph.load_path_edges],
            "load_path_routes": [list(r) for r in ir.graph.load_path_routes],
        },
        "surface_samples.json": {
            **head,
            "samples": [list(p) for p in ir.samples],
            "anchors": [list(p) for p in ir.anchors],
            "load_seeds": [list(p) for p in ir.load_seeds],
            "load_paths": [
                {"from": lp.from_region, "to": lp.to_region,
                 "priority": lp.priority, "seed": list(lp.seed)}
                for lp in ir.load_paths
            ],
        },
        "keepout_mask.json": {
            **head,
            "masks": [_region2d(k) for k in ir.masks],
        },
        "window_regions.json": {
            **head,
            "window": {"u0": ir.window.u0, "v0": ir.window.v0,
                       "u1": ir.window.u1, "v1": ir.window.v1},
            "origin": list(ir.origin) if ir.origin is not None else None,
            "tilt_deg": ir.tilt_deg,
            "plane_z": ir.plane_z,
            "depth": ir.depth,
            "min_ligament": ir.min_ligament,
            "windows": [[list(p) for p in poly] for poly in ir.windows],
        },
    }
    written: list[Path] = []
    for name, doc in docs.items():
        path = target / name
        path.write_text(json.dumps(_round(doc), indent=2, sort_keys=False))
        written.append(path)
    return written
