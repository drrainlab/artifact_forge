"""Pack discovery — the open-core extension point.

A *pack* is an installed distribution that plugs archetypes, recipe ops,
checks and joints into the engine's registries. It exposes one entry point
in the ``artifact_forge_ng.packs`` group::

    [project.entry-points."artifact_forge_ng.packs"]
    vf = "artifact_forge_vf:register"

``register(ctx)`` receives a :class:`PackContext`; it self-registers ops /
checks / joints by importing its own modules (the same import-time
``_register`` convention the core families use) and contributes archetype
YAML directories via :meth:`PackContext.add_archetype_dir`.

Guarantees:

- **Deterministic order** — entry points load sorted by name.
- **Idempotent** — :func:`load_packs` runs discovery once per process.
- **Fail-fast on collisions** — a pack that overwrites an existing
  RECIPE_OPS / JOINT_TYPES entry, an existing KNOWN_CHECKS declaration or
  an already-attached check impl raises :class:`PackError` unless it first
  declared the override via :meth:`PackContext.declare_override`.
- **Opt-out** — ``ARTIFACT_FORGE_DISABLE_PACKS=1`` skips discovery
  entirely (core-only mode; used by the core-only release gate).

The single call site is :func:`artifact_forge_ng.catalog.loader.load_catalog`
— every pipeline (CLI validate/build, web, tests) loads the catalog first,
so packs are registered before any YAML binds against the registries.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path

DISABLE_ENV = "ARTIFACT_FORGE_DISABLE_PACKS"
ENTRY_POINT_GROUP = "artifact_forge_ng.packs"


class PackError(RuntimeError):
    """A pack failed to load or tried to clobber an existing registration."""


@dataclass
class PackContext:
    """Handed to each pack's ``register``; collects its contributions."""

    pack_id: str
    archetype_dirs: list[Path] = field(default_factory=list)
    overrides: set[str] = field(default_factory=set)

    def add_archetype_dir(self, path: Path | str) -> None:
        p = Path(path)
        if not p.is_dir():
            raise PackError(
                f"pack {self.pack_id!r}: archetype dir {p} does not exist")
        self.archetype_dirs.append(p)

    def declare_override(self, name: str) -> None:
        """Explicitly allow this pack to replace one existing registration."""
        self.overrides.add(name)


#: pack_id -> its archetype dirs, in load order. None = not discovered yet.
_loaded: dict[str, list[Path]] | None = None


def _discover():
    """Separated for tests: returns the entry points, sorted by name."""
    return sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda e: e.name)


def _registry_snapshot() -> dict[str, dict[str, object]]:
    from .assembly.joints_core import JOINT_TYPES
    from .form.recipe_ops_core import RECIPE_OPS
    from .validators.probes import KNOWN_CHECKS

    return {
        "recipe op": dict(RECIPE_OPS),
        "joint type": dict(JOINT_TYPES),
        "check decl": dict(KNOWN_CHECKS),
        "check impl": {n: d.impl for n, d in KNOWN_CHECKS.items()
                       if d.impl is not None},
    }


def _verify_no_clobber(pack_id: str, before: dict[str, dict[str, object]],
                       allowed: set[str]) -> None:
    after = _registry_snapshot()
    for kind, old in before.items():
        new = after[kind]
        for name, value in old.items():
            if name in allowed:
                continue
            if name not in new or new[name] is not value:
                raise PackError(
                    f"pack {pack_id!r} replaced existing {kind} {name!r} — "
                    "packs must not clobber registrations (declare_override "
                    "to opt in explicitly)")


def load_packs() -> dict[str, list[Path]]:
    """Discover and register every installed pack (once per process).

    Returns ``{pack_id: [archetype dirs]}`` in deterministic load order.
    """
    global _loaded
    if os.environ.get(DISABLE_ENV, "").strip() not in ("", "0"):
        return {}
    if _loaded is not None:
        return _loaded

    loaded: dict[str, list[Path]] = {}
    for ep in _discover():
        try:
            register = ep.load()
        except Exception as exc:  # broken pack must be loud, never skipped
            raise PackError(f"pack {ep.name!r}: entry point failed to load: "
                            f"{exc}") from exc
        ctx = PackContext(pack_id=ep.name)
        before = _registry_snapshot()
        try:
            register(ctx)
        except PackError:
            raise
        except Exception as exc:
            raise PackError(f"pack {ep.name!r}: register() failed: {exc}") from exc
        _verify_no_clobber(ep.name, before, ctx.overrides)
        loaded[ep.name] = list(ctx.archetype_dirs)

    _loaded = loaded
    return _loaded


def pack_archetype_dirs() -> list[tuple[str, Path]]:
    """``(pack_id, dir)`` pairs of every loaded pack, in load order."""
    return [(pid, d) for pid, dirs in load_packs().items() for d in dirs]
