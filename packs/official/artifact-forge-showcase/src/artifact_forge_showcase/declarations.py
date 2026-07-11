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
        # -- repair: Spare Fit Standard (impls in checks/spare.py) ----------
        _decl("form.barb_retention_ok", Level.FORM,
              "hose-barb height inside the retention band and >= 2 barbs per spigot"),
        _decl("form.shaft_fit_ok", Level.FORM,
              "square shaft socket clearance in the fit band with real engagement depth"),
        _decl("form.knob_torque_wall_ok", Level.FORM,
              "wall between socket corners and grip carries hand torque"),
        # -- jigs: shop probes (impls in checks/jig.py) ----------------------
        _decl("form.bushing_fit_ok", Level.FORM,
              "steel bushing press interference in band, engagement depth and seat walls real"),
        _decl("form.stop_registration_ok", Level.FORM,
              "the stop fence spans the full plate edge and hooks below the plate"),
        # -- education: the shared fit-ladder capability (checks/ladder.py) --
        _decl("form.ladder_steps_ok", Level.FORM,
              "ladder bores strictly increasing at constant pitch, clearances in the printable band"),
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
