"""Structured, severity-tagged findings — the one result shape every
validator, reviewer, and repair rule in the pipeline speaks.

Ported from v1 ``review/base.py`` (Finding / Status / worst) with two
NG additions on ``Finding``: the validation ``level`` it came from, and a
``critical`` flag. A critical FAIL at contract/topology/region level forces
the final status to FAIL regardless of any numeric score — the anti-"grade
masks a broken product" gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

    @property
    def rank(self) -> int:
        return {"pass": 0, "warn": 1, "fail": 2}[self.value]


def worst(statuses: list[Status]) -> Status:
    return max(statuses, key=lambda s: s.rank, default=Status.PASS)


class Level(Enum):
    SCHEMA = "schema"
    CONTRACT = "contract"
    TOPOLOGY = "topology"
    REGION = "region"
    MANUFACTURING = "manufacturing"
    QUALITY = "quality"
    FORM = "form"
    #: Cross-part checks in the assembled pose (joints, fit, continuity).
    ASSEMBLY = "assembly"


#: Levels whose FAILs are product-correctness failures: they override any
#: numeric grade. Manufacturing failures cap the grade; quality only scores.
CRITICAL_LEVELS = frozenset(
    {Level.CONTRACT, Level.TOPOLOGY, Level.REGION, Level.ASSEMBLY}
)


@dataclass(frozen=True)
class Finding:
    check: str
    status: Status
    message: str
    level: Level = Level.FORM
    critical: bool = False
    suggestion: str = ""
    measured: float | None = None
    limit: float | None = None
    unit: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "check": self.check,
            "status": self.status.value,
            "level": self.level.value,
            "message": self.message,
        }
        if self.critical:
            d["critical"] = True
        if self.suggestion:
            d["suggestion"] = self.suggestion
        if self.measured is not None:
            d["measured"] = round(self.measured, 4)
        if self.limit is not None:
            d["limit"] = round(self.limit, 4)
        if self.unit:
            d["unit"] = self.unit
        return d


@dataclass
class ValidationReport:
    """All findings from one pipeline run, grouped by level on demand."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def status(self) -> Status:
        return worst([f.status for f in self.findings])

    def by_level(self, level: Level) -> list[Finding]:
        return [f for f in self.findings if f.level is level]

    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.status is Status.FAIL]

    def critical_failures(self) -> list[Finding]:
        return [
            f
            for f in self.findings
            if f.status is Status.FAIL and (f.critical or f.level in CRITICAL_LEVELS)
        ]

    def passed(self, check: str) -> bool:
        """True iff ``check`` was run and its worst finding is PASS."""
        matched = [f for f in self.findings if f.check == check]
        return bool(matched) and worst([f.status for f in matched]) is Status.PASS

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "findings": [f.to_dict() for f in self.findings],
        }
