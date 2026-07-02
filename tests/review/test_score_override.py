"""The anti-"grade masks a broken product" gate."""

from artifact_forge_ng.core.findings import Finding, Level, Status, ValidationReport
from artifact_forge_ng.review.score import compute_score


def passing(check: str, level: Level) -> Finding:
    return Finding(check=check, status=Status.PASS, level=level, message="ok")


def test_critical_topology_fail_forces_grade_f():
    report = ValidationReport(
        findings=[
            passing("form.profile_closed", Level.FORM),
            passing("form.profile_smooth", Level.FORM),
            passing("manufacturing.bed_fit", Level.MANUFACTURING),
            Finding(
                check="topology.asymmetric_lips_geometry",
                status=Status.FAIL,
                level=Level.TOPOLOGY,
                message="symmetric ring",
                critical=True,
            ),
        ]
    )
    score = compute_score(report, {"moldedness_score": 1.0, "boxiness_score": 0.0})
    assert score.grade == "F"
    assert score.status == "fail"
    assert "asymmetric_lips_geometry" in score.cap_reason
    # the numeric dims were fine — the gate overrode them anyway
    assert score.scores["form"] == 100.0


def test_manufacturing_fail_caps_but_does_not_fail():
    report = ValidationReport(
        findings=[
            passing("form.profile_closed", Level.FORM),
            Finding(
                check="manufacturing.overhang",
                status=Status.FAIL,
                level=Level.MANUFACTURING,
                message="needs support",
            ),
        ]
    )
    score = compute_score(report, {"moldedness_score": 1.0, "boxiness_score": 0.0})
    assert score.status == "pass"
    assert score.grade == "C"
    assert "caps" in score.cap_reason


def test_warns_only_still_pass():
    report = ValidationReport(
        findings=[
            passing("form.profile_closed", Level.FORM),
            Finding(
                check="quality.boxiness",
                status=Status.WARN,
                level=Level.QUALITY,
                message="a bit boxy",
            ),
        ]
    )
    score = compute_score(report, {"moldedness_score": 0.9, "boxiness_score": 0.1})
    assert score.status == "pass"
    assert score.grade in ("A", "B")


def test_region_keepout_fail_is_critical():
    report = ValidationReport(
        findings=[
            passing("form.profile_closed", Level.FORM),
            Finding(
                check="region.keepouts_preserved",
                status=Status.FAIL,
                level=Level.REGION,
                message="hex cell cut a screw zone",
            ),
        ]
    )
    score = compute_score(report, None)
    assert score.grade == "F" and score.status == "fail"
