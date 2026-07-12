"""prompt -> assembly/v1: creative composition over the catalog (wave W2).

The LLM emits a COMPACT typed form (parts + structured joint endpoints +
scoped shared + optional wiring), never a full assembly document; the
server grounds every name against the registries, expands to assembly/v1
and validates with the ordinary CAD-free pipeline. An LLM answer is
treated exactly like hand-written YAML — never trusted raw. No user
requirement is dropped silently: a grounding loss is a fail-finding that
feeds the repair loop, not a filter.

Verification is three-tiered: ``pre_cad_valid`` (schema + grounding +
validate pass) -> ``build_required`` when contract/wiring checks only
run at build -> ``fully_verified`` after a successful build.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

import yaml

from ..assembly.evaluation import AssemblyEvaluationSession
from ..assembly.joints import JOINT_TYPES
from ..catalog.grounding import (assembly_digest, select_assembly_candidates,
                                 shared_candidates)
from ..catalog.loader import Catalog, compatible_regions
from ..catalog.search import tokens
from ..product.assembly import _LEGAL_ANGLES, AssemblyInstance
from . import llm

MAX_PARTS = 16
MAX_JOINTS = 24
MAX_MODIFIERS_PER_PART = 4
MAX_REPAIRS = 4
_POSE_PRIORITY = {"establish": 0, "either": 1, "verify": 2}

#: the literal the model writes into any ``format: svg_path_data`` param
#: to reference the attached SVG asset — the server substitutes the real
#: path data; the model NEVER retypes asset data
SVG_ASSET_MARKER = "@svg"


def prepare_svg_asset(svg_text: str, motif_w: float = 100.0) -> tuple[str, str]:
    """Intake of a user-attached SVG for prompt->assembly: accepts a full
    SVG document (path data extracted) or raw path data; import-time
    cleaning (specks dropped, unprintable hatch slivers merged — both
    REPORTED, never silent) and a one-line summary for the model.
    Raises ``RecipeError`` on hopeless input — the route refuses the job
    up front instead of burning LLM calls on a broken asset."""
    from ..form.recipe_ops_text import MIN_STROKE_ENGRAVE
    from ..form.svg_path import import_svg_path, svg_path_to_polygons

    ds = re.findall(r'\bd="([^"]+)"', svg_text)
    path_data = " ".join(ds) if ds else svg_text.strip()
    cleaned, info = import_svg_path(
        path_data, motif_w, floor=MIN_STROKE_ENGRAVE)
    outlines, holes, mw = svg_path_to_polygons(cleaned, motif_w)
    notes = [f"{len(outlines)} outline(s)", f"{len(holes)} hole(s)",
             f"min feature {mw:.2f}mm at {motif_w:g}mm wide"]
    for key, n in info.items():
        if n:
            notes.append(f"{key.replace('_', ' ')}: {n}")
    return cleaned, ", ".join(notes)


# -- findings ---------------------------------------------------------------------


def _f(check: str, message: str, *, critical: bool = True) -> dict[str, Any]:
    return {"check": check, "status": "fail", "message": message,
            "critical": critical, "level": "intent"}


@dataclass
class GroundingResult:
    compact: dict[str, Any]
    findings: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.findings)


# -- the compact schema -------------------------------------------------------------


def _assembly_schema(part_ids: list[str]) -> dict[str, Any]:
    endpoint = {
        "type": "object",
        "properties": {
            "ref": {"type": "string"},
            "kind": {"type": "string", "enum": ["datum", "port"]},
            "id": {"type": "string",
                   "description": "a published datum or declared port id "
                                  "of that part's archetype"},
        },
        "required": ["ref", "kind", "id"],
    }
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "snake_case assembly id"},
            "root": {"type": "string",
                     "description": "ref of the frame-of-reference part"},
            "parts": {"type": "array", "minItems": 2, "maxItems": MAX_PARTS,
                      "items": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string",
                            "description": "short snake_case ref"},
                    "archetype_id": {"type": "string",
                                     "enum": sorted(part_ids)},
                    "params": {"type": "object",
                               "additionalProperties": {"type": "string"},
                               "description": "value-grammar strings "
                                              "('82mm', 'M3'); only names "
                                              "from the digest"},
                    "modifiers": {"type": "array", "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "target": {"type": "string",
                                       "description": "region id"},
                            "params": {"type": "object"},
                        },
                        "required": ["id", "target"],
                    }},
                },
                "required": ["ref", "archetype_id"],
            }},
            "joints": {"type": "array", "minItems": 1, "maxItems": MAX_JOINTS,
                       "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": sorted(JOINT_TYPES)},
                    "a": endpoint, "b": endpoint,
                    "rotate": {"type": "array", "minItems": 3, "maxItems": 3,
                               "items": {"type": "number", "enum": sorted(
                                   _LEGAL_ANGLES)}},
                    "params": {"type": "object"},
                },
                "required": ["type", "a", "b"],
            }},
            "shared": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "param": {"type": "string"},
                    "value": {"type": "string"},
                    "parts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["param", "value", "parts"],
            }},
            "wiring": {
                "type": "object",
                "description": "optional cable route between two parts",
                "properties": {
                    "from_part": {"type": "string"},
                    "to_part": {"type": "string"},
                    "via_parts": {"type": "array",
                                  "items": {"type": "string"}},
                    "d": {"type": "string"},
                },
                "required": ["from_part", "to_part"],
            },
            "contract_must_have": {"type": "array",
                                   "items": {"type": "string"}},
            "confidence": {"type": "string",
                           "enum": ["high", "medium", "low"]},
            "notes": {"type": "string",
                      "description": "design rationale: why these parts, "
                                     "params and modifiers"},
        },
        "required": ["id", "root", "parts", "joints", "confidence"],
    }


# -- grounding ----------------------------------------------------------------------


def _close(name: str, options: list[str]) -> str | None:
    hits = difflib.get_close_matches(name, options, n=1, cutoff=0.75)
    return hits[0] if hits else None


def _ground_endpoint(ep: Any, refs: dict[str, str], catalog: Catalog,
                     out: GroundingResult, where: str) -> str | None:
    """Returns the resolved 'ref.datum' anchor string, or None (finding
    already recorded). Ports resolve to their canonical datum HERE — kind
    never reaches the document, and never gets lost before resolution."""
    if not isinstance(ep, dict) or not all(
            k in ep for k in ("ref", "kind", "id")):
        out.findings.append(_f("assembly.intent.endpoint",
                               f"{where}: endpoint must be "
                               "{ref, kind, id}"))
        return None
    ref, kind, name = str(ep["ref"]), str(ep["kind"]), str(ep["id"])
    if ref not in refs:
        fixed = _close(ref, list(refs))
        if fixed:
            out.notes.append(f"{where}: ref {ref!r} -> {fixed!r}")
            ref = fixed
        else:
            out.findings.append(_f(
                "assembly.intent.endpoint",
                f"{where}: unknown part ref {ref!r} (parts: {sorted(refs)})"))
            return None
    spec = catalog.archetypes[refs[ref]]
    if kind == "port":
        port = next((i for i in spec.interfaces if i.id == name), None)
        if port is None:
            out.findings.append(_f(
                "assembly.intent.endpoint",
                f"{where}: {spec.id} declares no port {name!r} "
                f"(ports: {[i.id for i in spec.interfaces]})"))
            return None
        return f"{ref}.{port.datum}"
    if kind != "datum":
        out.findings.append(_f("assembly.intent.endpoint",
                               f"{where}: kind must be datum|port"))
        return None
    if spec.datums:
        from fnmatch import fnmatch
        if not any(fnmatch(name, d.id) or d.id == name for d in spec.datums):
            out.findings.append(_f(
                "assembly.intent.endpoint",
                f"{where}: {spec.id} declares no datum {name!r} "
                f"(declared: {[d.id for d in spec.datums]})"))
            return None
    else:
        out.notes.append(
            f"{where}: datum {ref}.{name} unverifiable — {spec.id} has no "
            "datum declarations yet; validation will measure it")
    return f"{ref}.{name}"


def _dict_items(raw: Any, what: str, out: GroundingResult) -> list[dict]:
    """The model must emit objects; a stray string/number is a finding,
    never a crash — the repair loop needs the message, not a traceback."""
    items = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    good: list[dict] = []
    for i, item in enumerate(items):
        if isinstance(item, dict):
            good.append(item)
        else:
            out.findings.append(_f(
                "assembly.intent.schema",
                f"{what}[{i}] must be an object, got "
                f"{type(item).__name__}: {str(item)[:60]!r}"))
    return good


def _ground_compact(raw: dict[str, Any], catalog: Catalog,
                    part_ids: list[str],
                    svg_asset: str | None = None) -> GroundingResult:
    out = GroundingResult(compact={})
    if not isinstance(raw, dict):
        out.findings.append(_f(
            "assembly.intent.schema",
            f"the answer must be an object, got {type(raw).__name__}"))
        return out
    parts_in = _dict_items(raw.get("parts"), "parts", out)
    joints_in = _dict_items(raw.get("joints"), "joints", out)
    if len(parts_in) > MAX_PARTS or len(joints_in) > MAX_JOINTS:
        out.findings.append(_f(
            "assembly.intent.limits",
            f"resource limits exceeded: {len(parts_in)} parts (max "
            f"{MAX_PARTS}), {len(joints_in)} joints (max {MAX_JOINTS})"))
        return out

    refs: dict[str, str] = {}       # ref -> archetype id
    parts_out: list[dict[str, Any]] = []
    for i, p in enumerate(parts_in):
        where = f"parts[{i}]"
        ref = str(p.get("ref") or f"part_{i}")
        aid = str(p.get("archetype_id", ""))
        if aid not in catalog.archetypes:
            fixed = _close(aid, list(catalog.archetypes))
            if fixed:
                out.notes.append(f"{where}: archetype {aid!r} -> {fixed!r}")
                aid = fixed
            else:
                out.findings.append(_f(
                    "assembly.intent.archetype",
                    f"{where}: unknown archetype {aid!r}"))
                continue
        spec = catalog.archetypes[aid]
        if ref in refs:
            out.findings.append(_f("assembly.intent.graph",
                                   f"duplicate part ref {ref!r}"))
            continue
        params: dict[str, str] = {}
        raw_params = p.get("params")
        if raw_params is not None and not isinstance(raw_params, dict):
            out.notes.append(f"{where}: params must be an object — dropped")
            raw_params = {}
        for name, value in (raw_params or {}).items():
            if name not in spec.parameters:
                out.notes.append(
                    f"{where}: dropped unknown param {name!r} (not on {aid})")
                continue
            if str(value).strip() == SVG_ASSET_MARKER:
                # "@svg" references the attached asset — the server
                # substitutes the REAL path data (the model never
                # retypes it); using the marker without an attachment
                # is a lost user requirement, not a silent drop
                if getattr(spec.parameters[name], "format", None) \
                        != "svg_path_data":
                    out.findings.append(_f(
                        "assembly.intent.asset",
                        f"{where}: param {name!r} is not svg_path_data — "
                        f"\"{SVG_ASSET_MARKER}\" only fits svg params"))
                    continue
                if not svg_asset:
                    out.findings.append(_f(
                        "assembly.intent.asset",
                        f"{where}: param {name!r} references "
                        f"\"{SVG_ASSET_MARKER}\" but no SVG asset is "
                        "attached to this request"))
                    continue
                # the marker stays in the compact (repair echoes stay
                # small, the model never sees raw path data) — _expand
                # substitutes the real asset into the document
                params[name] = SVG_ASSET_MARKER
                out.notes.append(f"{where}: {name} <- attached svg asset")
                continue
            params[name] = str(value)
        modifiers = _ground_modifiers(
            _dict_items(p.get("modifiers"), f"{where}.modifiers", out),
            spec, catalog, out, where)
        refs[ref] = aid
        parts_out.append({"ref": ref, "archetype_id": aid, "params": params,
                          "modifiers": modifiers})

    if len(parts_out) < 2:
        out.findings.append(_f(
            "assembly.intent.graph",
            f"an assembly needs at least 2 grounded parts, got "
            f"{len(parts_out)}"))
        return out

    root = str(raw.get("root", ""))
    if root not in refs:
        fixed = _close(root, list(refs))
        if fixed:
            out.notes.append(f"root {root!r} -> {fixed!r}")
            root = fixed
        else:
            out.findings.append(_f("assembly.intent.graph",
                                   f"root {root!r} is not a part ref"))
            return out

    joints_out: list[dict[str, Any]] = []
    for i, j in enumerate(joints_in):
        where = f"joints[{i}]"
        jtype = str(j.get("type", ""))
        if jtype not in JOINT_TYPES:
            fixed = _close(jtype, list(JOINT_TYPES))
            if fixed:
                out.notes.append(f"{where}: joint {jtype!r} -> {fixed!r}")
                jtype = fixed
            else:
                out.findings.append(_f("assembly.intent.joint",
                                       f"{where}: unknown joint type "
                                       f"{jtype!r}"))
                continue
        a = _ground_endpoint(j.get("a"), refs, catalog, out, f"{where}.a")
        b = _ground_endpoint(j.get("b"), refs, catalog, out, f"{where}.b")
        if a is None or b is None:
            continue
        if a.split(".", 1)[0] == b.split(".", 1)[0]:
            out.findings.append(_f(
                "assembly.intent.graph",
                f"{where}: a joint cannot connect part "
                f"{a.split('.', 1)[0]!r} to itself"))
            continue
        rotate = list(j.get("rotate") or [0, 0, 0])[:3] + [0, 0, 0]
        rotate = rotate[:3]
        snapped = [min(_LEGAL_ANGLES, key=lambda lg: abs(lg - float(r)))
                   for r in rotate]
        if snapped != [float(r) for r in rotate]:
            out.notes.append(f"{where}: rotate {rotate} snapped to {snapped}")
        j_params = j.get("params")
        joints_out.append({
            "type": jtype, "a": a, "b": b, "rotate": snapped,
            "params": dict(j_params) if isinstance(j_params, dict) else {}})

    shared_out = _ground_shared(_dict_items(raw.get("shared"), "shared", out),
                                refs, catalog, parts_out, out)
    wiring_out = _ground_wiring(raw.get("wiring"), refs, joints_out, out)
    contract = _ground_contract(raw.get("contract_must_have") or [],
                                catalog, out)

    out.compact = {
        "id": re.sub(r"[^a-z0-9_]", "_", str(raw.get("id", "assembly")).lower())
              or "assembly",
        "root": root,
        "parts": parts_out,
        "joints": joints_out,
        "shared": shared_out,
        "wiring": wiring_out,
        "contract_must_have": contract,
        "confidence": raw.get("confidence", "medium"),
        "notes": str(raw.get("notes", "")),
    }
    return out


def _ground_modifiers(mods: list[Any], spec, catalog: Catalog,
                      out: GroundingResult,
                      where: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    if len(mods) > MAX_MODIFIERS_PER_PART:
        out.findings.append(_f(
            "assembly.intent.limits",
            f"{where}: {len(mods)} modifiers exceed the per-part max "
            f"{MAX_MODIFIERS_PER_PART}"))
        return result
    catalog_mods = list(getattr(spec, "allowed_modifiers", []))
    for m in mods:
        mid = str(m.get("id", ""))
        if mid not in catalog_mods:
            fixed = _close(mid, catalog_mods)
            if fixed:
                out.notes.append(f"{where}: modifier {mid!r} -> {fixed!r}")
                mid = fixed
            else:
                out.findings.append(_f(
                    "assembly.intent.modifier",
                    f"{where}: modifier {mid!r} is not allowed on {spec.id} "
                    f"(allowed: {catalog_mods})"))
                continue
        target = str(m.get("target", ""))
        mod_def = catalog.modifiers.get(mid)
        legal = ([r.id for r in compatible_regions(spec, mod_def)]
                 if mod_def else [])
        if target not in legal:
            fixed_target = _close(target, legal)
            if fixed_target:
                out.notes.append(
                    f"{where}: modifier target {target!r} -> "
                    f"{fixed_target!r}")
                target = fixed_target
            else:
                out.findings.append(_f(
                    "assembly.intent.modifier",
                    f"{where}: region {target!r} is not a legal target for "
                    f"{mid} on {spec.id} (legal: {legal})"))
                continue
        mod_params = dict(m.get("params") or {})
        if mod_def is not None:
            unknown = [k for k in mod_params if k not in mod_def.params]
            for k in unknown:
                out.notes.append(
                    f"{where}: dropped unknown modifier param {k!r}")
                mod_params.pop(k)
        key = (mid, target)
        if key in seen:
            out.findings.append(_f(
                "assembly.intent.modifier",
                f"{where}: duplicate modifier {mid} on target {target!r}"))
            continue
        seen.add(key)
        result.append({"id": mid, "target": target, "params": mod_params})
    return result


def _ground_shared(shared: list[Any], refs: dict[str, str], catalog: Catalog,
                   parts_out: list[dict[str, Any]],
                   out: GroundingResult) -> list[dict[str, Any]]:
    specs = [catalog.archetypes[a] for a in refs.values()]
    candidates = shared_candidates(specs)
    by_ref = {p["ref"]: p for p in parts_out}
    result = []
    for i, b in enumerate(shared):
        where = f"shared[{i}]"
        name, value = str(b.get("param", "")), str(b.get("value", ""))
        target_refs = [str(r) for r in (b.get("parts") or [])]
        bad_refs = [r for r in target_refs if r not in refs]
        if bad_refs:
            out.findings.append(_f(
                "assembly.intent.shared",
                f"{where}: unknown part refs {bad_refs}"))
            continue
        declaring = [r for r in target_refs
                     if name in catalog.archetypes[refs[r]].parameters]
        if len(declaring) < len(target_refs):
            out.findings.append(_f(
                "assembly.intent.shared",
                f"{where}: {name!r} is not a parameter of every listed "
                f"part"))
            continue
        if name not in candidates and len(target_refs) > 1:
            out.notes.append(
                f"{where}: {name!r} is not a known shared candidate — "
                "kept, validation will judge the mate")
        conflict = [
            r for r in target_refs
            if by_ref[r]["params"].get(name) not in (None, value)
        ]
        if conflict:
            out.findings.append(_f(
                "assembly.intent.shared",
                f"{where}: shared {name}={value} would silently override "
                f"an explicit value on {conflict} — state one value"))
            continue
        result.append({"param": name, "value": value, "parts": target_refs})
    return result


def _joint_graph(joints: list[dict[str, Any]]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {}
    for j in joints:
        a = j["a"].split(".", 1)[0]
        b = j["b"].split(".", 1)[0]
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj


def _count_paths(adj: dict[str, set[str]], src: str, dst: str,
                 cap: int = 2) -> int:
    """Simple paths src->dst, counting stops at ``cap``."""
    count = 0

    def dfs(node: str, seen: frozenset[str]) -> None:
        nonlocal count
        if count >= cap:
            return
        if node == dst:
            count += 1
            return
        for nxt in adj.get(node, ()):  # deterministic enough for a count
            if nxt not in seen:
                dfs(nxt, seen | {nxt})

    dfs(src, frozenset({src}))
    return count


def _ground_wiring(wiring: Any, refs: dict[str, str],
                   joints: list[dict[str, Any]],
                   out: GroundingResult) -> dict[str, Any] | None:
    if not wiring:
        return None
    if isinstance(wiring, str):
        # forced tool calls sometimes stuff optional objects with a "none"
        # string — an explicit absence marker is absence, anything else
        # is a real schema finding
        if wiring.strip().lower() in ("none", "null", "n/a", "-", "нет"):
            out.notes.append("wiring: none-marker string treated as absent")
            return None
    if not isinstance(wiring, dict):
        out.findings.append(_f(
            "assembly.intent.wiring",
            f"wiring must be an object, got {type(wiring).__name__}: "
            f"{str(wiring)[:60]!r}"))
        return None
    frm, to = str(wiring.get("from_part", "")), str(wiring.get("to_part", ""))
    for r in (frm, to):
        if r not in refs:
            out.findings.append(_f("assembly.intent.wiring",
                                   f"wiring: unknown part ref {r!r}"))
            return None
    via = [str(v) for v in (wiring.get("via_parts") or [])]
    bad = [v for v in via if v not in refs]
    if bad:
        out.findings.append(_f("assembly.intent.wiring",
                               f"wiring: unknown via_parts {bad}"))
        return None
    adj = _joint_graph(joints)
    if via:
        chain = [frm] + via + [to]
        for x, y in zip(chain, chain[1:]):
            if y not in adj.get(x, ()):
                out.findings.append(_f(
                    "assembly.intent.wiring",
                    f"wiring: via path breaks between {x!r} and {y!r} — "
                    "no joint connects them"))
                return None
    else:
        n = _count_paths(adj, frm, to)
        if n == 0:
            out.findings.append(_f(
                "assembly.intent.wiring",
                f"wiring: no joint path from {frm!r} to {to!r}"))
            return None
        if n > 1:
            out.findings.append(_f(
                "assembly.intent.wiring",
                "wiring: ambiguous wiring path — specify via_parts"))
            return None
    return {"from_part": frm, "to_part": to,
            "d": str(wiring.get("d", "6mm"))}


def _ground_contract(features: list[Any], catalog: Catalog,
                     out: GroundingResult) -> list[str]:
    result = []
    for f_name in features:
        name = str(f_name)
        if name in catalog.features:
            result.append(name)
        else:
            out.findings.append(_f(
                "assembly.intent.contract",
                f"contract feature {name!r} is not in the catalog "
                "vocabulary — a user requirement must not be dropped"))
    return result


# -- graph grounding: invariants + pose-aware stable reorder ------------------------


def _ground_graph(compact: dict[str, Any], out: GroundingResult) -> None:
    parts = {p["ref"] for p in compact.get("parts", [])}
    joints = compact.get("joints", [])
    root = compact.get("root")

    # ambiguous pose establishment: two establish-ONLY joints on one part
    establishers: dict[str, list[str]] = {}
    for j in joints:
        b = j["b"].split(".", 1)[0]
        if JOINT_TYPES[j["type"]].pose_mode == "establish":
            establishers.setdefault(b, []).append(j["type"])
    for ref, types in establishers.items():
        if len(types) > 1:
            out.findings.append(_f(
                "assembly.intent.pose",
                f"ambiguous pose establishment: part {ref!r} has "
                f"{len(types)} establish joints ({types}) — the kernel "
                "would silently obey the first; pick one"))

    ordered, reordered, problems = _reorder_joints(joints, root, parts)
    out.findings.extend(problems)
    if reordered:
        out.notes.append("joints reordered into chain order "
                         "(establish before verify)")
    compact["joints"] = ordered


def _reorder_joints(
    joints: list[dict[str, Any]], root: str, parts: set[str],
) -> tuple[list[dict[str, Any]], bool, list[dict[str, Any]]]:
    """Deterministic pose-aware chain order: sort key
    (pose_depth of a-side, target part, establish->either->verify,
    original index); the original relative order survives wherever it
    does not contradict a pose dependency."""
    posed: dict[str, int] = {root: 0}
    remaining = list(enumerate(joints))
    ordered: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    while remaining:
        best = None
        for pos, (i, j) in enumerate(remaining):
            a_ref = j["a"].split(".", 1)[0]
            b_ref = j["b"].split(".", 1)[0]
            if a_ref not in posed:
                continue
            mode = JOINT_TYPES[j["type"]].pose_mode
            if b_ref not in posed and mode == "verify":
                continue        # a verify joint cannot pose a new part
            key = (posed[a_ref], b_ref, _POSE_PRIORITY[mode], i)
            if best is None or key < best[0]:
                best = (key, pos, i, j, a_ref, b_ref)
        if best is None:
            break
        _, pos, i, j, a_ref, b_ref = best
        remaining.pop(pos)
        ordered.append(j)
        if b_ref not in posed:
            posed[b_ref] = posed[a_ref] + 1
    for i, j in remaining:
        a_ref = j["a"].split(".", 1)[0]
        b_ref = j["b"].split(".", 1)[0]
        if a_ref not in posed and b_ref in posed:
            problems.append(_f(
                "assembly.intent.pose",
                f"joints[{i}] ({j['type']}): its a-side {a_ref!r} is never "
                "posed — swap a/b or add an establishing joint"))
        elif b_ref not in posed and all(
                JOINT_TYPES[jj["type"]].pose_mode == "verify"
                for jj in joints
                if jj["b"].split(".", 1)[0] == b_ref):
            problems.append(_f(
                "assembly.intent.pose",
                f"part {b_ref!r} has only verify-mode joints — it needs an "
                "establish/either joint to get a pose"))
        else:
            problems.append(_f(
                "assembly.intent.pose",
                f"joints[{i}] ({j['type']}): not reachable from the root "
                "chain"))
    for ref in parts - set(posed):
        if not any(p["message"].startswith(f"part {ref!r}")
                   for p in problems):
            problems.append(_f(
                "assembly.intent.graph",
                f"part {ref!r} is isolated — no joint chain reaches it "
                "from the root"))
    # unresolvable joints stay in the document (tail) — the draft must
    # faithfully show what the model asked for; the findings above say why
    ordered.extend(j for _, j in remaining)
    reordered = ordered != list(joints)
    return ordered, reordered, problems


# -- expansion -----------------------------------------------------------------------


def _expand(compact: dict[str, Any], catalog: Catalog,
            svg_asset: str | None = None) -> dict[str, Any]:
    """Compact -> full assembly/v1. Scoped shared values MATERIALIZE into
    the listed parts' params; only a binding that covers every declaring
    part becomes kernel-level ``shared`` (kernel injection is global by
    parameter name — the parts list would be lost). The "@svg" marker
    resolves to the attached asset HERE — the compact (and every repair
    echo) stays small."""
    parts_by_ref = {p["ref"]: p for p in compact["parts"]}
    kernel_shared: dict[str, str] = {}
    for binding in compact.get("shared", []):
        name, value = binding["param"], binding["value"]
        declaring_everywhere = [
            p["ref"] for p in compact["parts"]
            if name in catalog.archetypes[p["archetype_id"]].parameters
        ]
        if set(binding["parts"]) >= set(declaring_everywhere):
            kernel_shared[name] = value
        else:
            for ref in binding["parts"]:
                parts_by_ref[ref]["params"][name] = value

    doc: dict[str, Any] = {
        "schema": "assembly/v1",
        "id": compact["id"],
        "strict": True,
        "root": compact["root"],
        "parts": [],
        "joints": [
            {"type": j["type"], "a": j["a"], "b": j["b"],
             "rotate": j["rotate"], "params": j["params"]}
            for j in compact["joints"]
        ],
    }
    if kernel_shared:
        doc["shared"] = kernel_shared
    for p in compact["parts"]:
        spec = catalog.archetypes[p["archetype_id"]]
        product: dict[str, Any] = {
            "schema": "product/v1",
            "id": f"{compact['id']}_{p['ref']}",
            "archetype": spec.ref,
            "params": {
                name: (svg_asset if svg_asset
                       and str(value).strip() == SVG_ASSET_MARKER
                       else value)
                for name, value in p["params"].items()
            },
        }
        if p.get("modifiers"):
            product["modifiers"] = [
                {"id": m["id"], "target": m["target"],
                 **({"params": m["params"]} if m["params"] else {})}
                for m in p["modifiers"]
            ]
        doc["parts"].append({"ref": p["ref"], "product": product})
    if compact.get("contract_must_have"):
        doc["contract"] = {"must_have": list(compact["contract_must_have"])}
    if compact.get("wiring"):
        doc["wiring"] = dict(compact["wiring"])   # via_parts already dropped
    return doc


# -- prompt constraints (hard -> fail, soft -> note) ---------------------------------

_HARD_PATTERNS = (
    re.compile(r"\bM(\d(?:\.\d)?)\b", re.I),          # M3, M4
    re.compile(r"\bE(\d{2})\b", re.I),                # E27, GU10-like
    re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:mm|мм)\b", re.I),
)
_HARD_WORDS = {"snap": ("snap",), "защёлк": ("snap",), "защелк": ("snap",),
               "перфопанел": ("pegboard",), "pegboard": ("pegboard",)}
_SOFT_WORDS = ("красив", "лёгк", "легк", "минималист", "аккуратн", "стильн")


def _prompt_constraints(prompt: str) -> tuple[list[str], list[str]]:
    hard: list[str] = []
    low = prompt.lower()
    for pat in _HARD_PATTERNS:
        for m in pat.finditer(prompt):
            # dimensions normalize to the canonical value-grammar form
            # («140 мм» -> "140mm") — that is how they appear in params
            token = re.sub(r"\s+", "", m.group(0).replace("мм", "mm"))
            hard.append(token if token[0].isdigit() else token.upper())
    for stem, mapped in _HARD_WORDS.items():
        if stem in low:
            hard.extend(mapped)
    soft = [w for w in _SOFT_WORDS if w in low]
    return sorted(set(hard)), soft


def _constraint_findings(prompt: str, doc: dict[str, Any],
                         catalog: Catalog) -> tuple[list[dict], list[str]]:
    hard, soft = _prompt_constraints(prompt)
    if not hard and not soft:
        return [], []
    blob = json.dumps(doc, ensure_ascii=False).lower()
    for part in doc.get("parts", []):
        aid = part["product"]["archetype"].split("@", 1)[0]
        spec = catalog.archetypes.get(aid)
        if spec is not None:
            # derived reflection: the archetype's own vocabulary counts
            # (an E27 socket cup reflects "E27" via its description)
            blob += " " + spec.description.lower()
            blob += " " + " ".join(spec.provides_features)
    findings = []
    for token in hard:
        if token.lower() not in blob:
            findings.append(_f(
                "assembly.intent.constraint",
                f"hard prompt constraint {token!r} is not reflected "
                "anywhere in the draft (params/parts/contract/wiring)"))
    notes = [f"soft preference {w!r} noted" for w in soft]
    return findings, notes


# -- verification state ---------------------------------------------------------------


def _contract_checks(report: dict[str, Any], doc: dict[str, Any],
                     catalog: Catalog) -> tuple[list[str], list[str]]:
    """(immediate_failures, deferred_checks). A contract feature whose
    verified_by checks appear in the validate report and FAIL is an
    immediate failure; one whose checks never ran pre-CAD is deferred to
    build. Wiring continuity is always a build-time probe."""
    seen: dict[str, str] = {}
    for j in report.get("joints", []):
        seen[j.get("check", "")] = j.get("status", "")
    for part in report.get("parts", {}).values():
        for f_dict in part.get("findings", []):
            seen[f_dict.get("check", "")] = f_dict.get("status", "")
    immediate: list[str] = []
    deferred: list[str] = []
    for feature in doc.get("contract", {}).get("must_have", []):
        decl = catalog.features.get(feature)
        checks = list(decl.verified_by) if decl else []
        ran = [c for c in checks if c in seen]
        if any(seen.get(c) == "fail" for c in ran):
            immediate.append(feature)
        elif not ran:
            deferred.append(f"contract:{feature}")
    if doc.get("wiring"):
        deferred.append("assembly.channel_continuous_across")
    return immediate, deferred


# -- attempts, scoring, repair --------------------------------------------------------


@dataclass
class Attempt:
    compact: dict[str, Any]
    doc: dict[str, Any] | None
    report: dict[str, Any] | None
    grounding_findings: list[dict[str, Any]]
    notes: list[str]
    schema_failures: list[dict[str, Any]] = field(default_factory=list)
    immediate_contract: list[str] = field(default_factory=list)
    deferred_checks: list[str] = field(default_factory=list)

    @property
    def report_fails(self) -> list[dict[str, Any]]:
        if not self.report:
            return []
        out = [j for j in self.report.get("joints", [])
               if j.get("status") == "fail"]
        for ref, part in self.report.get("parts", {}).items():
            for f_dict in part.get("findings", []):
                if f_dict.get("status") == "fail":
                    out.append({**f_dict, "part": ref})
        return out

    @property
    def pre_cad_valid(self) -> bool:
        return (self.report is not None
                and self.report.get("status") == "pass"
                and not self.schema_failures
                and not self.grounding_findings
                and not self.immediate_contract)


def _draft_score(a: Attempt) -> tuple[int, ...]:
    fails = a.report_fails
    critical = sum(1 for f_dict in fails if f_dict.get("critical"))
    joints_total = len(a.compact.get("joints", []))
    joints_bad = sum(
        1 for j in (a.report or {}).get("joints", [])
        if j.get("status") == "fail")
    parts_total = len(a.compact.get("parts", []))
    parts_bad = sum(
        1 for p in (a.report or {}).get("parts", {}).values()
        if p.get("status") == "fail")
    contract_pass = (len(a.compact.get("contract_must_have", []))
                     - len(a.immediate_contract))
    return (
        # an attempt that produced no document can never be the best draft
        int(a.doc is not None),
        int(a.report is not None),
        -(critical + len(a.schema_failures)),
        -len(fails),
        -len(a.grounding_findings),
        contract_pass,
        joints_total - joints_bad,
        parts_total - parts_bad,
        -len(a.notes),
    )


def _failure_digest(attempt: Attempt, cap: int = 15) -> list[str]:
    lines: list[str] = []
    for f_dict in attempt.schema_failures + attempt.grounding_findings:
        lines.append(f"[{f_dict.get('check')}] {f_dict.get('message')}")
    critical = [f_dict for f_dict in attempt.report_fails
                if f_dict.get("critical")]
    rest = [f_dict for f_dict in attempt.report_fails
            if not f_dict.get("critical")]
    for f_dict in critical + rest:
        where = f"part {f_dict['part']}: " if f_dict.get("part") else ""
        line = f"[{f_dict.get('check')}] {where}{f_dict.get('message')}"
        if f_dict.get("suggestion"):
            line += f" (suggestion: {f_dict['suggestion']})"
        lines.append(line)
    for feature in attempt.immediate_contract:
        lines.append(f"[contract] must_have feature {feature!r} failed "
                     "its verifying checks")
    return lines[:cap]


_SYSTEM_INSTRUCTION = """\
You compose a MULTI-PART printed assembly from the catalog below. Emit
the compact form through the tool: parts (ref, archetype_id, params,
modifiers), joints with structured endpoints, scoped shared bindings,
optional wiring, contract features. Joints in CHAIN ORDER from the root.
Use ONLY archetypes, datums, ports, joints, params and modifiers listed
in the catalog digest. Explain your design choices in notes.
"""


def llm_assembly(prompt: str, catalog: Catalog,
                 progress: Callable[[str], None] = lambda m: None,
                 max_repairs: int = MAX_REPAIRS,
                 svg_asset: str | None = None,
                 svg_summary: str = "") -> dict[str, Any]:
    candidates = select_assembly_candidates(prompt, catalog)
    progress(f"candidates: {len(candidates)}")
    system = _SYSTEM_INSTRUCTION + "\n" + assembly_digest(
        catalog, part_ids=candidates)
    if svg_asset:
        system += (
            f"\n\nSVG ASSET ATTACHED ({svg_summary or 'user art'}). "
            "When the user wants this art engraved, embossed or cut "
            "(гравировка, силуэт, фигурный вырез, логотип), pick an "
            "archetype with a parameter of format svg_path_data and set "
            f"that parameter to the literal string \"{SVG_ASSET_MARKER}\" "
            "— the server substitutes the real path data. NEVER retype, "
            "abbreviate or invent path data yourself.")
        progress(f"svg asset: {svg_summary}")
    schema = _assembly_schema(candidates)
    session = AssemblyEvaluationSession(catalog)

    attempts: list[Attempt] = []
    user = prompt
    last_digest: list[str] | None = None
    for attempt_no in range(1, max_repairs + 2):
        progress("composing assembly…" if attempt_no == 1
                 else f"repair {attempt_no - 1}/{max_repairs}…")
        try:
            raw = llm.complete(system, user, schema, max_tokens=4000)
        except RuntimeError:
            if not attempts:
                raise
            progress("LLM failed mid-repair — keeping the best draft")
            break
        attempt = _evaluate(raw, prompt, catalog, candidates, session,
                            svg_asset=svg_asset)
        attempts.append(attempt)
        progress(session.stats_line(attempt_no)
                 if attempt.report else "validation not reached")
        if attempt.pre_cad_valid:
            break
        digest = _failure_digest(attempt)
        progress(f"attempt {attempt_no}: {len(digest)} finding(s)")
        if digest == last_digest:
            progress("no progress between attempts — stopping early")
            break
        last_digest = digest
        if attempt_no > max_repairs:
            break
        user = (
            f"{prompt}\n\nYOUR PREVIOUS ASSEMBLY (compact JSON):\n"
            f"{json.dumps(attempt.compact, ensure_ascii=False)}\n\n"
            "VALIDATION FOUND THESE PROBLEMS:\n" + "\n".join(digest) +
            "\nFix ONLY what the findings name and re-emit the FULL "
            "corrected assembly through the tool. Datums must come from "
            "the per-archetype lists in the catalog above."
        )

    best = max(attempts, key=_draft_score)
    return _result(best, attempts, source="llm")


def _evaluate(raw: dict[str, Any], prompt: str, catalog: Catalog,
              candidates: list[str],
              session: AssemblyEvaluationSession,
              svg_asset: str | None = None) -> Attempt:
    grounded = _ground_compact(raw, catalog, candidates, svg_asset=svg_asset)
    attempt = Attempt(compact=grounded.compact or dict(raw), doc=None,
                      report=None,
                      grounding_findings=list(grounded.findings),
                      notes=list(grounded.notes))
    if not grounded.compact:
        return attempt
    _ground_graph(grounded.compact, grounded)
    attempt.grounding_findings = list(grounded.findings)
    attempt.notes = list(grounded.notes)

    doc = _expand(grounded.compact, catalog, svg_asset=svg_asset)
    try:
        asm = AssemblyInstance.model_validate(doc)
    except Exception as exc:  # pydantic ValidationError
        attempt.schema_failures.append(_f(
            "assembly.intent.schema", _clip_validation_error(exc)))
        attempt.doc = doc
        return attempt
    attempt.doc = doc
    try:
        report = session.validate(asm, strict_flag=False)
    except Exception as exc:  # CatalogError etc. — honest, not a traceback
        attempt.schema_failures.append(_f(
            "assembly.intent.validate", str(exc)[:500]))
        return attempt
    attempt.report = report
    c_findings, c_notes = _constraint_findings(prompt, doc, catalog)
    attempt.grounding_findings.extend(c_findings)
    attempt.notes.extend(c_notes)
    attempt.immediate_contract, attempt.deferred_checks = _contract_checks(
        report, doc, catalog)
    return attempt


def _clip_validation_error(exc: Exception, max_errors: int = 5) -> str:
    text = str(exc)
    lines = [ln for ln in text.splitlines() if ln.strip()][: max_errors * 2]
    return " | ".join(lines)[:600]


def _result(best: Attempt, attempts: list[Attempt], *,
            source: str) -> dict[str, Any]:
    pre_cad_valid = best.pre_cad_valid
    state = ("failed" if not pre_cad_valid
             else "build_required" if best.deferred_checks
             else "pre_cad_pass")
    validation = dict(best.report or {})
    if best.report is not None:
        validation["ok"] = best.report.get("status") == "pass"
    return {
        "ok": best.doc is not None,
        "source": source,
        "valid": pre_cad_valid,               # front compatibility
        "pre_cad_valid": pre_cad_valid,
        "verification_state": state,
        "deferred_checks": list(best.deferred_checks),
        "can_build": state in ("pre_cad_pass", "build_required"),
        "yaml": yaml.safe_dump(best.doc, sort_keys=False, allow_unicode=True)
                if best.doc else "",
        "validation": validation,
        "iterations": len(attempts),
        "selected_iteration": attempts.index(best) + 1,
        "grounding_findings": list(best.grounding_findings)
                              + list(best.schema_failures),
        "confidence": best.compact.get("confidence", "medium"),
        "notes": "; ".join(
            ([best.compact["notes"]] if best.compact.get("notes") else [])
            + best.notes),
    }


# -- deterministic fallback -----------------------------------------------------------


def deterministic_assembly(prompt: str, catalog: Catalog) -> dict[str, Any]:
    """Honest minimum without the LLM: composition needs a model — offer
    the closest example assemblies as a starting point instead."""
    from pathlib import Path

    examples_dir = Path(__file__).resolve().parents[3] / "catalog" / "examples"
    toks = [t for t in tokens(prompt) if len(t) > 2]
    suggestions = []
    for path in sorted(examples_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text())
        except Exception:
            continue
        if not isinstance(doc, dict) or doc.get("schema") != "assembly/v1":
            continue
        hay = " ".join([
            path.stem.replace("_", " "), str(doc.get("id", "")),
            " ".join(p.get("product", {}).get("archetype", "")
                     .replace("_", " ")
                     for p in doc.get("parts", [])),
        ]).lower()
        score = sum(1 for t in toks if t in hay)
        if score:
            suggestions.append(
                {"file": path.name, "id": doc.get("id"), "score": score})
    suggestions.sort(key=lambda s: (-s["score"], s["file"]))
    return {
        "ok": False,
        "source": "deterministic",
        "valid": False,
        "pre_cad_valid": False,
        "verification_state": "failed",
        "deferred_checks": [],
        "can_build": False,
        "yaml": "",
        "validation": {},
        "iterations": 0,
        "selected_iteration": 0,
        "grounding_findings": [_f(
            "assembly.intent.llm",
            "assembly composition requires the LLM (set ANTHROPIC_API_KEY); "
            "closest example assemblies are suggested instead",
            critical=False)],
        "confidence": "low",
        "suggestions": suggestions[:5],
        "notes": "keyword match against example assemblies (LLM OFF)",
    }
