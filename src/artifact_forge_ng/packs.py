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
    data_dirs: list[Path] = field(default_factory=list)
    overrides: set[str] = field(default_factory=set)
    manifest: dict = field(default_factory=dict)
    pack_root: Path | None = None

    def add_pack_manifest(self, path: Path | str) -> None:
        """Read the pack's pack.yaml (name, tier, visibility, domains,
        catalog.featured, ...) — presentation metadata only, the engine
        attaches no build semantics to it. Fail-fast on a broken file."""
        import yaml

        p = Path(path)
        try:
            doc = yaml.safe_load(p.read_text())
        except Exception as exc:
            raise PackError(
                f"pack {self.pack_id!r}: unreadable manifest {p}: {exc}") from exc
        if not isinstance(doc, dict):
            raise PackError(
                f"pack {self.pack_id!r}: manifest {p} is not a mapping")
        self.manifest = doc
        self.pack_root = p.parent

    def add_data_dir(self, path: Path | str) -> None:
        """A catalog-data dir mirroring core's layout: optional
        ``features.yaml``, ``archetypes/``, ``modifiers/``."""
        p = Path(path)
        if not p.is_dir():
            raise PackError(
                f"pack {self.pack_id!r}: data dir {p} does not exist")
        self.data_dirs.append(p)

    def declare_override(self, name: str) -> None:
        """Explicitly allow this pack to replace one existing registration."""
        self.overrides.add(name)

    def add_assembly_finding_hook(self, fn) -> None:
        """``fn(asm, states, poses, findings) -> Iterable[Finding]`` — extra
        assembly-level findings appended during assembly validation."""
        ASSEMBLY_FINDING_HOOKS.append(fn)

    def add_assembly_report_hook(self, fn) -> None:
        """``fn(asm, states, joint_findings, poses) ->
        Iterable[(key, filename|None, payload)]`` — report sections; a
        filename also writes ``<target>/<filename>`` and records the export."""
        ASSEMBLY_REPORT_HOOKS.append(fn)

    def add_part_report_hook(self, fn) -> None:
        """``fn(state) -> (key, payload) | None`` — extra report section for
        a single-part CAD build."""
        PART_REPORT_HOOKS.append(fn)


#: Pack-contributed pipeline hooks, in pack load order.
ASSEMBLY_FINDING_HOOKS: list = []
ASSEMBLY_REPORT_HOOKS: list = []
PART_REPORT_HOOKS: list = []


#: pack_id -> its data dirs, in load order. None = not discovered yet.
_loaded: dict[str, list[Path]] | None = None

#: pack_id -> parsed pack.yaml (presentation metadata), in load order.
_manifests: dict[str, dict] = {}

#: pack_id -> the pack root (the manifest's directory), in load order.
_roots: dict[str, Path] = {}


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
        loaded[ep.name] = list(ctx.data_dirs)
        if ctx.manifest:
            _manifests[ep.name] = ctx.manifest
        if ctx.pack_root is not None:
            _roots[ep.name] = ctx.pack_root

    _loaded = loaded
    return _loaded


def pack_manifests() -> dict[str, dict]:
    """pack_id -> parsed pack.yaml metadata of every loaded pack that
    contributed one, in load order."""
    load_packs()
    return dict(_manifests)


def pack_example_dirs() -> list[tuple[str, Path]]:
    """``(pack_id, examples dir)`` of every loaded pack that has one."""
    load_packs()
    return [(pid, root / "examples") for pid, root in _roots.items()
            if (root / "examples").is_dir()]


def pack_data_dirs() -> list[tuple[str, Path]]:
    """``(pack_id, dir)`` pairs of every loaded pack, in load order."""
    return [(pid, d) for pid, dirs in load_packs().items() for d in dirs]
