"""Check declarations — the fail-fast vocabulary this pack adds."""
from __future__ import annotations

from artifact_forge_ng.core.findings import Level
from artifact_forge_ng.validators.probes import KNOWN_CHECKS, CheckDecl


def _decl(name: str, level: Level, description: str):
    return name, CheckDecl(name=name, level=level, description=description)


PACK_CHECKS: dict[str, CheckDecl] = dict(
    [
        _decl("form.example_edge_margin_ok", Level.FORM,
              "every hole keeps the declared edge margin (demo check)"),
    ]
)


def declare() -> None:
    """Idempotent: importing any part of the pack declares the vocabulary."""
    for name, decl in PACK_CHECKS.items():
        existing = KNOWN_CHECKS.get(name)
        if existing is None:
            KNOWN_CHECKS[name] = decl
        elif existing is not decl:
            raise RuntimeError(
                f"example pack: check {name!r} already declared by someone else")
