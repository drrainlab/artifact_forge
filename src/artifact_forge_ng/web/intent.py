"""Stage-1 intent and natural-language edits.

LLM path: prompt -> {archetype_id, params, confidence} grounded in the
catalog digest; the server then validates the pick against the REAL
catalog and the params through the ordinary /api/validate — an LLM answer
is treated exactly like hand-written YAML, never trusted raw.

Deterministic fallback (LLM OFF): token scoring against archetype ids,
object classes, descriptions and feature names. Honest and boring.
"""

from __future__ import annotations

import re
from typing import Any

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


def nl_edit(text: str, current_yaml: str) -> dict[str, Any]:
    """Free-text edit -> either a known intent name or a raw Patch dict.
    The result goes through /api/edit/preview like any hand-written patch."""
    from ..repair.intents import INTENTS

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
                "properties": {
                    "type": {"type": "string",
                             "enum": ["functional", "manufacturing",
                                      "structural", "style"]},
                    "reason": {"type": "string"},
                    "params": {"type": "object",
                               "additionalProperties": {"type": "string"}},
                    "preserve": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }
    system = (
        "You translate a free-text edit request for an Artifact Forge "
        "product into EITHER a known intent name OR a typed patch "
        "(patch/v1: absolute values or '+3mm' deltas on existing "
        "parameters). Prefer a known intent when it matches. The current "
        "product YAML follows; only reference its parameters.\n"
        f"Known intents: {', '.join(sorted(INTENTS))}"
    )
    raw = llm.complete(system, f"{current_yaml}\n\nREQUEST: {text}", schema,
                       cache_system=False)
    return {"ok": True, "intent": raw.get("intent"), "patch": raw.get("patch")}
