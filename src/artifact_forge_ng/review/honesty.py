"""The honesty report — what was requested, what the engine supports, what
was PROVEN built, what is missing, which forbidden forms were checked, and
which gaps the engine admits to. Assembled only from the typed capability
report and the validation evidence, so it cannot disagree with either.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from ..core.findings import Status, ValidationReport
from ..product.capability import CapabilityReport, mark_built
from ..review.quality import shape_quality
from ..review.score import compute_score
from ..validators.runner import contract_findings, must_have_findings


class FormCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form: str
    status: str  # "absent" | "present" | "unchecked"


class HonestyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_features: list[str] = []
    supported_features: list[str] = []
    built_features: list[str] = []
    missing_features: list[str] = []
    unsupported_features: list[str] = []
    forbidden_forms_checked: list[FormCheck] = []
    critical_failures: list[dict[str, Any]] = []
    engine_gaps: list[dict[str, Any]] = []


def _forbidden_forms(state, report: ValidationReport) -> list[FormCheck]:
    out: list[FormCheck] = []
    for form_id in state.archetype.forbidden_forms:
        check = f"contract.must_not_have:{form_id}"
        matched = [f for f in report.findings if f.check == check]
        if not matched:
            from ..validators.probes import FORBIDDEN_FORM_DETECTORS

            detector = FORBIDDEN_FORM_DETECTORS[form_id]
            if any(f.check == detector for f in report.findings):
                status = "absent" if report.passed(detector) else "present"
            else:
                status = "unchecked"
        else:
            worst = max(matched, key=lambda f: f.status.rank)
            status = "absent" if worst.status is Status.PASS else (
                "present" if worst.status is Status.FAIL else "unchecked"
            )
        out.append(FormCheck(form=form_id, status=status))
    return out


def build_honesty(
    state, capability: CapabilityReport, report: ValidationReport
) -> HonestyReport:
    gaps = [g.model_dump() for g in capability.engine_gaps]
    gaps.extend(
        {"feature_or_check": f.check, "suggestion": f.suggestion or "implement the probe"}
        for f in report.findings
        if f.status is Status.WARN and "no implementation" in f.message
    )
    return HonestyReport(
        requested_features=capability.requested_features,
        supported_features=capability.supported_features,
        built_features=capability.built_features,
        missing_features=[
            f
            for f in capability.missing_features
            if f in capability.requested_features or not capability.requested_features
        ],
        unsupported_features=capability.unsupported_features,
        forbidden_forms_checked=_forbidden_forms(state, report),
        critical_failures=[f.to_dict() for f in report.critical_failures()],
        engine_gaps=gaps,
    )


def finalize_build(state, geometry, out: dict[str, Any], target: Path) -> None:
    """The post-compile honesty pass: contract -> built verification ->
    quality -> score -> honesty report -> files."""
    report = state.report

    report.extend(contract_findings(state, report))

    state.capability = mark_built(state.capability, report, state.catalog.features)
    report.extend(must_have_findings(state, state.capability))

    quality_scores: dict[str, float] = {}
    if state.form is not None:
        quality_scores, quality_findings = shape_quality(state.form)
        report.extend(quality_findings)

    score = compute_score(report, quality_scores)
    honesty = build_honesty(state, state.capability, report)

    out["score"] = score.to_dict()
    out["honesty_report"] = honesty.model_dump()
    out["status"] = score.status
    out["findings"] = [
        f.to_dict() for f in report.findings if f.status is not Status.PASS
    ]

    target.mkdir(parents=True, exist_ok=True)
    (target / "honesty_report.yaml").write_text(
        yaml.safe_dump(honesty.model_dump(), sort_keys=False, allow_unicode=True)
    )
    (target / "findings.yaml").write_text(
        yaml.safe_dump(
            {"status": score.status, "score": score.to_dict(),
             "findings": [f.to_dict() for f in report.findings]},
            sort_keys=False,
            allow_unicode=True,
        )
    )

    # Bio-2 exoskeleton debug artifacts ride along with every build that
    # carries the IR (lazy import — most builds have no exoskeleton).
    if state.form is not None and getattr(state.form, "exoskeleton", None) is not None:
        from ..form.exoskeleton.debug import dump_exoskeleton_debug

        dump_exoskeleton_debug(state.form, target)
