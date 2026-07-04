"""Stage-1 intent and natural-language edits.

LLM path: prompt -> {archetype_id, params, confidence} grounded in the
catalog digest; the server then validates the pick against the REAL
catalog and the params through the ordinary /api/validate — an LLM answer
is treated exactly like hand-written YAML, never trusted raw.

Deterministic fallback (LLM OFF): token scoring against archetype ids,
object classes, descriptions and feature names. Honest and boring.
"""

from __future__ import annotations

import json
import re
from typing import Any

import yaml

from ..archetypes import builder_for
from ..catalog.loader import Catalog
from . import llm

_WORD = re.compile(r"[a-zA-Zа-яА-Я0-9_]+")

#: RU/EN hints mapped onto catalog tokens — keeps the fallback useful for
#: the Russian-speaking maker without any model.
_SYNONYMS = {
    "клипса": "clip", "кабель": "cable", "кабеля": "cable", "провод": "cable",
    "пучок": "bundle", "пучка": "bundle", "стол": "desk", "столом": "desk",
    "коробка": "enclosure box", "крышка": "lid", "лампа": "lamp",
    "лампы": "lamp", "патрон": "socket", "кронштейн": "bracket",
    "крючок": "hook", "крюк": "hook", "подставка": "stand",
    "телефон": "phone", "труба": "pipe", "трубы": "pipe", "швабра": "broom",
    "ручка": "handle", "полка": "shelf", "полки": "shelf",
    "гребенка": "comb", "гребёнка": "comb", "стяжка": "zip tie",
    "канал": "raceway channel", "подшипник": "bearing", "ферма": "truss",
    "распаечная": "junction", "переходник": "adapter", "пластина": "plate",
    "винт": "screw", "саморез": "screw",
}


def _tokens(text: str) -> list[str]:
    words = [w.lower() for w in _WORD.findall(text)]
    out = []
    for w in words:
        out.append(w)
        if w in _SYNONYMS:
            out.extend(_SYNONYMS[w].split())
    return out


def deterministic_intent(prompt: str, catalog: Catalog) -> dict[str, Any]:
    tokens = _tokens(prompt)
    scored = []
    for spec in catalog.archetypes.values():
        hay = " ".join([
            spec.id.replace("_", " "), spec.object_class.replace("_", " "),
            spec.description.lower(), " ".join(spec.provides_features),
        ]).lower()
        score = sum(1 for t in tokens if len(t) > 2 and t in hay)
        if score:
            scored.append((score, spec))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    candidates = [
        {
            "archetype_id": spec.id,
            "object_class": spec.object_class,
            "status": "recipe" if spec.form.type == "recipe" else (
                "buildable" if builder_for(spec) is not None else "metadata_only"
            ),
            "score": score,
        }
        for score, spec in scored[:3]
    ]
    top = scored[0][0] if scored else 0
    return {
        "ok": bool(candidates),
        "source": "deterministic",
        "confidence": "high" if top >= 4 else "medium" if top >= 2 else "low",
        "candidates": candidates,
        "params": _mm_guesses(prompt),
        "notes": "keyword match against the catalog (LLM OFF)",
    }


def _mm_guesses(prompt: str) -> dict[str, str]:
    """Pull obvious quantities: '20mm bundle' etc. Conservative — only
    values the archetype actually has get applied later."""
    out: dict[str, str] = {}
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm|мм)\s*(?:bundle|пуч)", prompt, re.I)
    if m:
        out["bundle_d"] = f"{m.group(1)}mm"
    m = re.search(r"(?:bundle|пуч\w*)\D{0,12}(\d+(?:\.\d+)?)\s*(?:mm|мм)", prompt, re.I)
    if m:
        out.setdefault("bundle_d", f"{m.group(1)}mm")
    m = re.search(r"\bM(\d)\b", prompt, re.I)
    if m:
        out["screw"] = f"M{m.group(1)}"
    return out


_INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "archetype_id": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "params": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "parameter values as value-grammar strings ('20mm')",
        },
        "requested_features": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": ["archetype_id", "confidence"],
}


def llm_intent(prompt: str, catalog: Catalog) -> dict[str, Any]:
    system = (
        "You translate a maker's request into an Artifact Forge archetype "
        "pick. Choose ONLY from the catalog below; use exact archetype ids "
        "and only its exposed parameter names. Values use the value grammar "
        "('20mm', 'M4'). If nothing fits, pick the closest and say so in "
        "notes.\n\n" + llm.catalog_digest(catalog)
    )
    raw = llm.complete(system, prompt, _INTENT_SCHEMA)
    spec = catalog.archetypes.get(raw.get("archetype_id", ""))
    if spec is None:
        # the model hallucinated an id — fall back honestly
        out = deterministic_intent(prompt, catalog)
        out["notes"] = f"LLM proposed unknown archetype {raw.get('archetype_id')!r}; deterministic fallback"
        return out
    params = {
        k: v for k, v in (raw.get("params") or {}).items()
        if k in spec.parameters
    }
    return {
        "ok": True,
        "source": "llm",
        "confidence": raw.get("confidence", "medium"),
        "candidates": [{
            "archetype_id": spec.id,
            "object_class": spec.object_class,
            "status": "recipe" if spec.form.type == "recipe" else (
                "buildable" if builder_for(spec) is not None else "metadata_only"
            ),
            "score": None,
        }],
        "params": params,
        "notes": raw.get("notes", ""),
    }


def nl_edit(text: str, current_yaml: str, archetype, catalog: Catalog,
            selected_region: str | None = None) -> dict[str, Any]:
    """Free-text edit -> a known intent name or a raw Patch dict, GROUNDED
    in the current archetype: the model sees exactly which parameter names,
    modifier params, preserve entries AND region targets are legal. Targets
    are enum-constrained to the regions each modifier may land on
    (compatible_regions); a region selected in the UI pins that enum.
    Whatever comes back still goes through /api/edit/preview like any
    hand-written patch — aliases are canonicalized and missing targets
    auto-filled server-side (with a note), never passed through to fail
    late."""
    from ..catalog.loader import compatible_regions, resolve_region_name
    from ..repair.intents import INTENTS

    param_names = sorted(archetype.parameters)
    preserve_ok = sorted(set(param_names) | set(catalog.features))
    notes: list[str] = []
    compat: dict[str, list[str]] = {}
    mod_digest = []
    for mod_id in archetype.allowed_modifiers:
        mdef = catalog.modifiers.get(mod_id)
        if mdef is not None:
            compat[mod_id] = [r.id for r in compatible_regions(archetype, mdef)]
            mod_digest.append(
                f"{mod_id}(params: {', '.join(sorted(mdef.params))}; "
                f"targets: {', '.join(compat[mod_id]) or '-'})")
    selected = (resolve_region_name(archetype, selected_region)
                if selected_region else None)
    if selected_region and selected is None:
        notes.append(f"selected region {selected_region!r} does not exist "
                     f"on {archetype.id!r} — ignored")
    target_enum = ([selected.id] if selected is not None
                   else sorted({r for ids in compat.values() for r in ids}))
    # update targets an EXISTING use — its legal values come from the
    # instance document, not from the archetype.
    doc = yaml.safe_load(current_yaml) or {}
    used_targets = sorted({
        str(m.get("target")) for m in doc.get("modifiers", [])
        if isinstance(m, dict) and m.get("target")
    })
    add_target: dict[str, Any] = {"type": "string"}
    if target_enum:
        add_target["enum"] = target_enum
    upd_target: dict[str, Any] = {"type": "string"}
    if used_targets:
        upd_target["enum"] = used_targets
    # modifier ids are CATALOG ids, never invented instance names — the
    # enum constrains the model, the server grounds whatever comes back
    legal_add_ids = sorted(compat)
    used_ids = sorted({
        str(m.get("id")) for m in doc.get("modifiers", [])
        if isinstance(m, dict) and m.get("id")
    })
    add_id: dict[str, Any] = {"type": "string"}
    if legal_add_ids:
        add_id["enum"] = legal_add_ids
    upd_id: dict[str, Any] = {"type": "string"}
    if used_ids:
        upd_id["enum"] = used_ids
    schema = {
        "type": "object",
        "properties": {
            "intent": {
                "type": ["string", "null"],
                "enum": [*sorted(INTENTS), None],
                "description": "a known goal intent, when one matches exactly",
            },
            "patch": {
                "type": ["object", "null"],
                "description": "the typed patch as a NESTED JSON OBJECT — "
                               "never a JSON- or YAML-encoded string",
                "properties": {
                    "type": {"type": "string",
                             "enum": ["functional", "manufacturing",
                                      "structural", "style"]},
                    "reason": {"type": "string"},
                    "params": {"type": "object",
                               "additionalProperties": {"type": "string"},
                               "description": f"ONLY these names: {', '.join(param_names)}"},
                    "preserve": {"type": "array",
                                 "items": {"type": "string", "enum": preserve_ok}},
                    "modifiers": {
                        "type": "object",
                        "properties": {
                            "update": {"type": "array", "items": {
                                "type": "object",
                                "properties": {
                                    "id": upd_id,
                                    "target": upd_target,
                                    "params": {"type": "object",
                                               "additionalProperties": {"type": "string"}},
                                },
                                "required": ["id", "params"],
                            }},
                            "add": {"type": "array", "items": {
                                "type": "object",
                                "properties": {
                                    "id": add_id,
                                    "target": add_target,
                                    "params": {"type": "object",
                                               "additionalProperties": {"type": "string"}},
                                },
                                "required": ["id", "target"],
                            }},
                            "remove": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        },
    }
    region_lines = []
    for r in archetype.regions:
        mods = [m for m, ids in compat.items() if r.id in ids]
        if mods:
            label = f' ("{r.label}")' if r.label else ""
            region_lines.append(
                f"- {r.id}{label}: role {r.role.value}; "
                f"modifiers: {', '.join(mods)}")
    protected = [r.id for r in archetype.regions
                 if not any(r.id in ids for ids in compat.values())]
    system = (
        "You translate a free-text edit request for an Artifact Forge "
        "product into EITHER a known intent name OR a typed patch "
        "(patch/v1). Rules:\n"
        "- patch.params: ONLY archetype parameter names (absolute values "
        "or '+3mm'/'-3mm' deltas). NEVER percentages — to halve or scale a "
        "dimension, compute the absolute number yourself.\n"
        "- pattern/field changes ('more voronoi', 'denser holes') go into "
        "modifiers.update on the EXISTING modifier use (merge params like "
        "sites/min_ligament/hole_d), never into patch.params.\n"
        "- preserve: only from the allowed list (archetype params + feature "
        "vocabulary) — modifier params are NOT valid preserve entries.\n"
        "- modifiers.add.target: a CANONICAL region id from the target "
        "regions below — a target is a Form IR region, never free text or "
        "a feature name.\n"
        "- fit field params to the window: on narrow bands/strips (height "
        "≤ 10mm) set edge_margin 0.5-0.8mm (NOT more — every cell shrinks "
        "by ligament/2 per side and 1mm margins kill them all) and "
        "min_ligament ~1.2mm; on ring/cylinder bands keep sites 16-20 — "
        "fewer sites make cells wider than 0.6*radius and the cylindrical "
        "mapping honestly refuses, more sites make cells too narrow to "
        "survive the shrink.\n"
        f"Archetype {archetype.id}: params {', '.join(param_names)}.\n"
        f"Allowed modifiers: {'; '.join(mod_digest) or '-'}.\n"
        "Target regions:\n"
        + ("\n".join(region_lines) or "- (none — modifiers cannot be added)")
        + "\n"
        f"Protected regions (NEVER valid targets): "
        f"{', '.join(protected) or '-'}.\n"
        + (f"The user selected region {selected.id!r} — any modifiers.add "
           "MUST target exactly it.\n" if selected is not None else "")
        + f"Known intents: {', '.join(sorted(INTENTS))}"
    )
    def _attempt(user_msg: str):
        raw = llm.complete(system, user_msg, schema, cache_system=False)
        patch = _coerce_obj(raw.get("patch"), "patch", notes)
        mods = None
        if patch is not None:
            mods = _coerce_obj(patch.get("modifiers"), "modifiers", notes)
            patch["modifiers"] = mods or {}
        if mods:
            for key in ("add", "update", "remove"):
                if key in mods and not isinstance(mods[key], list):
                    notes.append(f"modifiers.{key}: not a list — dropped")
                    mods[key] = []
        if mods:
            # ground modifier IDS first (targets are grounded per-id below):
            # the model invents instance-ish names like 'hex_perforation_1' —
            # resolve them onto catalog ids or drop with the reason
            for key, legal_ids in (("add", legal_add_ids),
                                   ("update", sorted(set(used_ids) | set(legal_add_ids)))):
                kept_entries = []
                for entry in mods.get(key) or []:
                    if not isinstance(entry, dict):
                        kept_entries.append(entry)
                        continue
                    given = str(entry.get("id") or "")
                    hit = _resolve_modifier_id(given, legal_ids)
                    if hit is None:
                        notes.append(
                            f"modifiers.{key}: unknown modifier {given!r} — "
                            f"dropped (allowed: {', '.join(legal_ids) or '-'})")
                        continue
                    if hit != given:
                        notes.append(f"modifier id {given!r} -> catalog id {hit!r}")
                        entry["id"] = hit
                    kept_entries.append(entry)
                if key in mods and mods[key] is not None:
                    mods[key] = kept_entries
        if mods and mods.get("add"):
            raw_add = mods["add"] if isinstance(mods["add"], list) else []
            add_entries = [e for e in raw_add if isinstance(e, dict)]
            if len(add_entries) != len(raw_add):
                notes.append("dropped malformed modifiers.add entries")
            existing = {
                (str(m.get("id")), str(m.get("target")))
                for m in doc.get("modifiers", []) if isinstance(m, dict)
            }
            kept = []
            for entry in add_entries:
                _ground_add_target(entry, archetype, compat, selected, notes)
                key = (str(entry.get("id")), str(entry.get("target")))
                if key in existing:
                    # apply_patch silently skips duplicate adds — say it and
                    # turn the request into an update on the existing use
                    mods.setdefault("update", []).append(entry)
                    notes.append(
                        f"{entry.get('id')} is already on {entry.get('target')!r}"
                        " — converted add to update (tune its params: 'more/"
                        "denser/larger…')")
                else:
                    kept.append(entry)
            mods["add"] = kept
        if patch and isinstance(patch.get("preserve"), list):
            keep, dropped = [], []
            for name in patch["preserve"]:
                (keep if name in preserve_ok else dropped).append(name)
            patch["preserve"] = keep
            if dropped:
                notes.append(f"dropped invalid preserve entries: {', '.join(dropped)}")
        if patch and isinstance(patch.get("params"), dict):
            # ground the VALUES too: a '-50%' here would 500 the preview —
            # drop what the value grammar cannot parse, with the reason
            from ..core.values import parse_delta

            good: dict[str, Any] = {}
            for name, value in patch["params"].items():
                spec = archetype.parameters.get(name)
                if spec is None:
                    notes.append(f"params.{name}: not an archetype parameter — dropped")
                    continue
                if spec.type == "choice":
                    if value in spec.choices:
                        good[name] = value
                    else:
                        notes.append(f"params.{name}: {value!r} not in "
                                     f"{spec.choices} — dropped")
                    continue
                try:
                    parse_delta(value, spec.type, where=f"params.{name}")
                except ValueError as exc:
                    notes.append(
                        f"params.{name}: {exc} — dropped (use an absolute "
                        "value like '90mm' or a delta like '-30mm')")
                    continue
                good[name] = value
            patch["params"] = good
        if patch is not None and not any((
            patch.get("params"),
            any((patch.get("modifiers") or {}).get(k) for k in ("add", "update", "remove")),
            patch.get("manufacturing"), patch.get("style"), patch.get("archetype"),
        )):
            notes.append("patch had nothing actionable left after grounding")
            patch = None
        intent_name = raw.get("intent")
        intent_name = intent_name if isinstance(intent_name, str) else None
        return raw, intent_name, patch

    request_msg = f"{current_yaml}\n\nREQUEST: {text}"
    raw, intent_name, patch = _attempt(request_msg)
    if intent_name is None and patch is None:
        # one corrective retry: the model answered, but nothing actionable
        # survived coercion — name the drops and demand the object shape
        # instead of failing the maker's request on the first malformed try
        rejection = "; ".join(notes) or "empty answer"
        notes.append("first answer had nothing actionable — retried once")
        raw, intent_name, patch = _attempt(
            f"{request_msg}\n\nYOUR PREVIOUS ANSWER WAS REJECTED: {rejection}. "
            "Answer again through the tool: set patch to a NESTED JSON OBJECT "
            "(never a string). Parameter changes go in patch.params, new "
            "modifiers in patch.modifiers.add (id + target + params)."
        )
    if intent_name is None and patch is None:
        # nothing actionable came back — an honest failure WITH the drop
        # notes beats ok:true that downstream turns into 'edit.input'
        from .serialize import error_finding

        detail = "; ".join(notes) or (
            "raw answer: " + json.dumps(raw, ensure_ascii=False)[:300])
        return {"ok": False, "findings": [error_finding(
            f"LLM returned neither a known intent nor a patch ({detail}) — "
            "try rephrasing the request", "edit.nl")],
            "notes": "; ".join(notes)}
    return {"ok": True,
            "intent": intent_name,
            "patch": patch,
            "notes": "; ".join(notes)}


def _coerce_obj(value: Any, where: str, notes: list[str]) -> dict[str, Any] | None:
    """The forced tool call keeps the TOP shape honest, but the model still
    sometimes emits a nested object as its JSON string. Decode that case;
    drop (with a note, never a traceback) anything that is not an object."""
    if value is None or isinstance(value, dict):
        return value
    if isinstance(value, str):
        decoded = None
        try:
            decoded = json.loads(value)
        except ValueError:
            # models also emit YAML-ish strings (single quotes, bare keys);
            # YAML is a JSON superset, so try it before giving up
            try:
                decoded = yaml.safe_load(value)
            except yaml.YAMLError:
                decoded = None
        if isinstance(decoded, dict):
            notes.append(f"{where}: decoded JSON-string object from the LLM")
            return decoded
    notes.append(f"{where}: LLM returned {type(value).__name__} instead of "
                 "an object — dropped")
    return None


def _resolve_modifier_id(given: str, legal: list[str]) -> str | None:
    """Ground an LLM-emitted modifier id onto a catalog id: exact match,
    then the instance-suffix/prefix families ('hex_perforation_1' →
    'add_hex_perforation'), then a fuzzy last resort. None = no safe match."""
    g = given.strip().lower()
    if g in legal:
        return g
    core = re.sub(r"_\d+$", "", g)  # strip an invented instance suffix
    for lid in legal:
        if core == lid or f"add_{core}" == lid or (len(core) >= 6 and core in lid):
            return lid
    import difflib

    hits = difflib.get_close_matches(core, legal, n=1, cutoff=0.6)
    return hits[0] if hits else None


def _ground_add_target(entry: dict[str, Any], archetype,
                       compat: dict[str, list[str]],
                       selected, notes: list[str]) -> None:
    """Server-side ground truth for one modifiers.add entry: the schema
    enum only CONSTRAINS the model, it does not guarantee — aliases are
    canonicalized, and an empty/illegal target is auto-filled when the
    answer is unambiguous (the UI-selected region, or the single
    compatible one). Anything still wrong fails the preview with a
    did-you-mean, never silently."""
    from ..catalog.loader import resolve_region_name

    legal = compat.get(str(entry.get("id")), [])
    target = str(entry.get("target") or "")
    if target and target not in legal:
        hit = resolve_region_name(archetype, target)
        if hit is not None and hit.id in legal:
            notes.append(f"target {target!r} -> canonical region {hit.id!r}")
            entry["target"] = hit.id
            return
    if target in legal and target:
        return
    if selected is not None and selected.id in legal:
        entry["target"] = selected.id
        notes.append(f"auto-targeted {entry.get('id')}: "
                     f"selected region {selected.id!r}")
    elif len(legal) == 1:
        entry["target"] = legal[0]
        notes.append(f"auto-targeted {entry.get('id')} -> {legal[0]!r}: "
                     "only compatible editable region")
