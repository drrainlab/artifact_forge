"""Deterministic semantic repair — findings and user phrases map to YAML
patches through an ordered rule table. No LLM, no freeform geometry edits;
a rule that fires twice without clearing its finding becomes an engine-gap
candidate via the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..core.findings import Finding, Status, ValidationReport
from ..product.instance import ProductInstance
from .patch import ModifierOps, Patch


def _patch(reason: str, params: dict | None = None, modifiers: ModifierOps | None = None) -> Patch:
    return Patch(
        schema="patch/v1",
        reason=reason,
        params=params or {},
        modifiers=modifiers or ModifierOps(),
    )


@dataclass(frozen=True)
class RepairRule:
    #: Substring matched against Finding.check.
    check_pattern: str
    make_patch: Callable[[Finding, ProductInstance], Patch]
    description: str


RULES: list[RepairRule] = [
    RepairRule(
        check_pattern="mouth_gap < bundle_d",
        make_patch=lambda f, i: _patch(
            "mouth gap violated its bundle invariant", {"mouth_gap": "expr(bundle_d * 0.65)"}
        ),
        description="pull mouth_gap back under the retention ceiling",
    ),
    RepairRule(
        check_pattern="lower_lip_longer_than_upper",
        make_patch=lambda f, i: _patch(
            "lips too symmetric", {"lower_lip_len": "expr(upper_lip_len * 1.8)"}
        ),
        description="restore the asymmetric-hook identity",
    ),
    RepairRule(
        check_pattern="manufacturing.min_wall",
        make_patch=lambda f, i: _patch(
            "thinnest wall under printer floor", {"wall": "expr(printer.min_wall * 1.5)"}
        ),
        description="thicken the wall past the printable floor (incl. lip taper)",
    ),
    RepairRule(
        check_pattern="manufacturing.overhang",
        make_patch=lambda f, i: _patch(
            "cavity bridge span too wide", {"clearance": "0.4mm"}
        ),
        description="tighten cavity clearance to shave the bridge span",
    ),
]

#: User-phrase semantics -> patches (the ТЗ repair map, deterministic).
SEMANTIC_RULES: dict[str, Callable[[ProductInstance], Patch]] = {
    "falls_out": lambda i: _patch(
        "cable falls out",
        {"mouth_gap": "expr(bundle_d * 0.5)", "lower_lip_len": "+3mm"},
    ),
    "too_tight": lambda i: _patch(
        "insertion too tight",
        {"mouth_gap": "expr(bundle_d * 0.65)"},
    ),
    "too_boxy": lambda i: _patch(
        "shape reads boxy",
        {"neck_drop": "+2mm"},
    ),
}


def propose_repairs(
    report: ValidationReport, instance: ProductInstance
) -> list[Patch]:
    """First matching rule per failing check, in report order."""
    patches: list[Patch] = []
    seen_rules: set[str] = set()
    for finding in report.findings:
        if finding.status is not Status.FAIL:
            continue
        for rule in RULES:
            if rule.check_pattern in finding.check and rule.check_pattern not in seen_rules:
                patches.append(rule.make_patch(finding, instance))
                seen_rules.add(rule.check_pattern)
                break
    return patches


@dataclass
class RepairLedger:
    """Findings that survive repair attempts become engine-gap candidates —
    the deterministic descendant of v1's systemic ledger."""

    attempts: dict[str, int] = field(default_factory=dict)

    def record_attempt(self, check: str) -> None:
        self.attempts[check] = self.attempts.get(check, 0) + 1

    def survivors(self, still_failing: list[str], min_attempts: int = 2) -> list[dict]:
        return [
            {
                "feature_or_check": check,
                "suggestion": "repair rules cannot clear this — engine gap",
                "survived_repairs": self.attempts[check],
            }
            for check in still_failing
            if self.attempts.get(check, 0) >= min_attempts
        ]
