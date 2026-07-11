"""Showcase check declarations — the vocabulary this pack adds to
KNOWN_CHECKS at registration (same fail-fast semantics as core names).
Waves fill this dict as they land; declare() is idempotent."""
from __future__ import annotations

from artifact_forge_ng.core.findings import Level
from artifact_forge_ng.validators.probes import KNOWN_CHECKS, CheckDecl


def _decl(name: str, level: Level, description: str):
    return name, CheckDecl(name=name, level=level, description=description)


SHOWCASE_CHECKS: dict[str, CheckDecl] = dict(
    [
    ]
)


def declare() -> None:
    """Idempotent: importing any part of the pack declares the vocabulary."""
    for name, decl in SHOWCASE_CHECKS.items():
        existing = KNOWN_CHECKS.get(name)
        if existing is None:
            KNOWN_CHECKS[name] = decl
        elif existing is not decl:
            raise RuntimeError(
                f"showcase pack: check {name!r} already declared by someone else")
