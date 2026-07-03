"""The LLM seam (ported from v1 llm.py, Anthropic-only). ONE role: translate
human intent into typed documents (archetype pick + params, or a Patch).
Geometry is built exclusively by the deterministic pipeline; everything the
model outputs is re-validated by the same schemas as hand-written YAML.
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_MODEL = os.environ.get("FORGE_LLM_MODEL", "claude-sonnet-5")


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def complete(system: str, user: str, schema: dict[str, Any],
             cache_system: bool = True) -> dict[str, Any]:
    """Schema-constrained completion: the model MUST return JSON matching
    ``schema`` (enforced via a forced tool call). Raises RuntimeError on
    any transport/shape problem — callers turn that into a finding."""
    import anthropic

    client = anthropic.Anthropic()
    sys_block: Any = [{"type": "text", "text": system}]
    if cache_system:
        sys_block[0]["cache_control"] = {"type": "ephemeral"}
    try:
        resp = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=2000,
            system=sys_block,
            tools=[{
                "name": "emit",
                "description": "Emit the structured answer.",
                "input_schema": schema,
            }],
            tool_choice={"type": "tool", "name": "emit"},
            messages=[{"role": "user", "content": user}],
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LLM call failed: {exc}") from exc
    for block in resp.content:
        if block.type == "tool_use":
            return dict(block.input)
    raise RuntimeError("LLM returned no structured block")


def catalog_digest(catalog) -> str:
    """Compact catalog description the intent prompt is grounded in —
    cache_control keeps it cheap across requests."""
    lines = ["Artifact Forge archetype catalog:"]
    for spec in catalog.archetypes.values():
        exposed = [
            f"{n}({p.type})" for n, p in spec.parameters.items() if p.exposed
        ]
        lines.append(
            f"- {spec.id} | class={spec.object_class} | "
            f"params: {', '.join(exposed) or '-'} | "
            f"features: {', '.join(spec.provides_features)} | "
            f"{' '.join(spec.description.split())[:200]}"
        )
    return "\n".join(lines)


def to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)
