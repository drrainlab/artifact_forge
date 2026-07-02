"""Run every geometry-level check the archetype names, through the probe
registry. Importing this module pulls in the probe implementations (and
therefore cadquery) — the compiler loads it lazily.

Contract semantics on top of the raw probes:
- an archetype ``validators:`` name with no implementation is an ENGINE GAP
  finding (WARN in dev, strict turns the missing verification into honest
  ``missing_features`` downstream — never a silent skip);
- ``forbidden_forms`` bind through FORBIDDEN_FORM_DETECTORS: the detector
  check FAILING means the forbidden form is PRESENT (critical contract FAIL).
"""

from __future__ import annotations

from ..cad.geometry import Geometry
from ..core.findings import Finding, Level, Status
from ..core.expr import evaluate
from . import manufacturing, region, topology  # noqa: F401  (register probes)
from .probes import FORBIDDEN_FORM_DETECTORS, KNOWN_CHECKS


def run_geometry_validators(state, geometry: Geometry) -> list[Finding]:
    findings: list[Finding] = []
    form = state.form
    geometry_levels = {Level.TOPOLOGY, Level.REGION, Level.MANUFACTURING}
    for name in state.archetype.validators:
        decl = KNOWN_CHECKS[name]  # loader guaranteed existence
        if decl.level not in geometry_levels:
            continue  # form.* checks already ran pre-CAD
        if decl.impl is None:
            findings.append(
                Finding(
                    check=name,
                    status=Status.WARN,
                    level=decl.level,
                    message=f"declared check {name!r} has no implementation — engine gap",
                    suggestion=f"implement probe {name!r}",
                )
            )
            continue
        findings.append(decl.impl(geometry, form))
    # Checks the archetype may not have listed but must still run: what the
    # instance's modifiers promised, and the always-on manufacturing suite
    # (every part gets bed-fit/min-wall/overhang scrutiny).
    listed = set(state.archetype.validators)
    extra: list[str] = []
    for use in state.instance.modifiers:
        mod = state.catalog.modifiers.get(use.id)
        if mod is not None:
            extra.extend(mod.validators)
    extra.extend(n for n, d in KNOWN_CHECKS.items() if d.level is Level.MANUFACTURING)
    for name in extra:
        if name in listed:
            continue
        decl = KNOWN_CHECKS.get(name)
        if decl is None or decl.level not in geometry_levels:
            continue
        if decl.impl is not None:
            findings.append(decl.impl(geometry, form))
            listed.add(name)
    return findings


def contract_findings(state, report) -> list[Finding]:
    """Compile the archetype's product contract against the validation
    evidence: invariants over resolved params, forbidden forms via their
    detectors, must_have via feature verification downstream."""
    findings: list[Finding] = []
    contract = state.archetype.contract

    ctx = state.resolved.context
    for formula in contract.invariants:
        try:
            ok = evaluate(formula, ctx) != 0.0
        except Exception as exc:
            findings.append(
                Finding(
                    check=f"contract.invariant:{formula}",
                    status=Status.FAIL,
                    level=Level.CONTRACT,
                    message=f"invariant could not be evaluated: {exc}",
                    critical=True,
                )
            )
            continue
        findings.append(
            Finding(
                check=f"contract.invariant:{formula}",
                status=Status.PASS if ok else Status.FAIL,
                level=Level.CONTRACT,
                message=formula if ok else f"violated: {formula}",
                critical=True,
            )
        )

    checked = {f.check for f in report.findings} | {f.check for f in findings}
    for form_id in contract.must_not_have:
        detector = FORBIDDEN_FORM_DETECTORS[form_id]
        ran = detector in checked
        if not ran:
            findings.append(
                Finding(
                    check=f"contract.must_not_have:{form_id}",
                    status=Status.WARN,
                    level=Level.CONTRACT,
                    message=f"forbidden form {form_id!r} UNCHECKED (detector {detector} did not run)",
                )
            )
            continue
        absent = report.passed(detector)
        findings.append(
            Finding(
                check=f"contract.must_not_have:{form_id}",
                status=Status.PASS if absent else Status.FAIL,
                level=Level.CONTRACT,
                message=(
                    f"forbidden form {form_id!r} absent"
                    if absent
                    else f"forbidden form {form_id!r} PRESENT"
                ),
                critical=True,
            )
        )
    return findings


def must_have_findings(state, capability) -> list[Finding]:
    """After mark_built: every contract must_have feature must be BUILT."""
    findings: list[Finding] = []
    built = set(capability.built_features)
    for feature_id in state.archetype.contract.must_have:
        ok = feature_id in built
        findings.append(
            Finding(
                check=f"contract.must_have:{feature_id}",
                status=Status.PASS if ok else Status.FAIL,
                level=Level.CONTRACT,
                message=(
                    f"{feature_id} built and verified"
                    if ok
                    else f"{feature_id} NOT verified as built"
                ),
                critical=True,
            )
        )
    return findings
