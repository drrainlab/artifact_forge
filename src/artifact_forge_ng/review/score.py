"""Score and grade — with the hard gate that made v1 honest: a critical
FAIL at contract/topology/region level forces status FAIL and grade F no
matter how good the numbers look. Score answers "how good is it?"; the
gate answers "is it even the right product?" — the gate wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.findings import Level, Status, ValidationReport

#: Relative weights; missing dimensions are dropped and renormalized.
WEIGHTS = {"form": 0.40, "manufacturing": 0.35, "quality": 0.25}


@dataclass
class BuildScore:
    scores: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    grade: str = "F"
    status: str = "fail"
    cap_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "scores": {k: round(v, 1) for k, v in self.scores.items()},
            "overall": round(self.overall, 1),
            "grade": self.grade,
            "status": self.status,
            **({"cap_reason": self.cap_reason} if self.cap_reason else {}),
        }


def _level_score(report: ValidationReport, level: Level) -> float | None:
    findings = report.by_level(level)
    if not findings:
        return None
    score = 100.0
    for f in findings:
        if f.status is Status.FAIL:
            score -= 40.0
        elif f.status is Status.WARN:
            score -= 10.0
    return max(0.0, score)


def _grade(overall: float) -> str:
    for threshold, grade in ((90, "A"), (80, "B"), (70, "C"), (60, "D")):
        if overall >= threshold:
            return grade
    return "F"


def compute_score(
    report: ValidationReport, quality_scores: dict[str, float] | None = None
) -> BuildScore:
    dims: dict[str, float] = {}
    form = _level_score(report, Level.FORM)
    if form is not None:
        dims["form"] = form
    manufacturing = _level_score(report, Level.MANUFACTURING)
    if manufacturing is not None:
        dims["manufacturing"] = manufacturing
    if quality_scores:
        # quality metrics arrive as 0..1; moldedness up, boxiness down.
        moldedness = quality_scores.get("moldedness_score", 0.0)
        boxiness = quality_scores.get("boxiness_score", 0.0)
        dims["quality"] = max(0.0, min(100.0, 100.0 * (moldedness * 0.7 + (1 - boxiness) * 0.3)))

    total_weight = sum(WEIGHTS[k] for k in dims)
    overall = (
        sum(dims[k] * WEIGHTS[k] for k in dims) / total_weight if total_weight else 0.0
    )

    critical = report.critical_failures()
    if critical:
        names = ", ".join(sorted({f.check for f in critical}))
        return BuildScore(
            scores=dims,
            overall=overall,
            grade="F",
            status="fail",
            cap_reason=f"critical failure overrides score: {names}",
        )

    grade = _grade(overall)
    cap = ""
    if manufacturing is not None and any(
        f.status is Status.FAIL for f in report.by_level(Level.MANUFACTURING)
    ):
        if grade in ("A", "B"):
            grade, cap = "C", "manufacturing failure caps the grade at C"
    return BuildScore(
        scores=dims, overall=overall, grade=grade, status="pass", cap_reason=cap
    )
