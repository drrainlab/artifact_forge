"""The tilted flush row golden (VF correction): the 10-part row validates
end to end — drip in, two lap seams, drip out, full profile seating,
magnets aligned, drainage proven against the declared mount — and every
row-level mutation fails the check that owns it."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.pipeline import (
    AssemblyFailure,
    run_assembly_validate,
)

EXAMPLES = Path(__file__).parents[1] / "examples" / "vertical_farm"
ROW = EXAMPLES / "vertical_farm_row_3x1.yaml"
SMOKE = EXAMPLES / "vertical_farm_flush_smoke.yaml"


@pytest.fixture(scope="module")
def row_report():
    return run_assembly_validate(ROW, None)


def _joints(report) -> dict[str, list]:
    out: dict[str, list] = {}
    for j in report["joints"]:
        out.setdefault(j["check"], []).append(j)
    return out


def test_row_validates(row_report):
    assert row_report["status"] == "pass"


def test_row_is_flush_not_cascade(row_report):
    checks = _joints(row_report)
    assert all(j["status"] == "pass" for j in checks["assembly.lap_flow_ir"])
    assert len(checks["assembly.lap_flow_ir"]) == 2  # two module seams
    assert all(j["status"] == "pass" for j in checks["assembly.row_flush_aligned"])
    # the two drip handovers survive ONLY at the ends
    assert len(checks["assembly.fluid_joint_ir"]) == 2


def test_row_drains_under_mount(row_report):
    checks = _joints(row_report)
    drains = checks["assembly.row_drains_under_mount"]
    assert len(drains) == 1 and drains[0]["status"] == "pass"
    assert "1.5" in drains[0]["message"]


def test_full_profile_seating(row_report):
    checks = _joints(row_report)
    support = checks["assembly.profile_support_full_length"]
    assert all(j["status"] == "pass" for j in support)
    assert all(j["status"] == "pass" for j in checks["assembly.profile_perch_ir"])


def test_magnets_aligned(row_report):
    checks = _joints(row_report)
    magnets = checks["assembly.magnet_alignment_ok"]
    assert len(magnets) == 1 and magnets[0]["status"] == "pass"
    assert "4 magnet pair(s)" in magnets[0]["message"]


def test_cassettes_removable(row_report):
    checks = _joints(row_report)
    rem = checks["assembly.cassettes_removable_under_mount"]
    assert rem and rem[0]["status"] == "pass"


def test_contract_features_verified(row_report):
    """Every must_have feature's assembly checks pass in the validate
    report (the built_features stamp itself belongs to the CAD build)."""
    from artifact_forge_ng.catalog.loader import load_catalog

    catalog = load_catalog()
    passed = {j["check"] for j in row_report["joints"] if j["status"] == "pass"}
    failed = {j["check"] for j in row_report["joints"] if j["status"] == "fail"}
    cad_only = {"assembly.no_interference"}  # runs on solids, not at validate
    for feature in ("row_water_chain", "row_flush_integrity", "saddle_mount",
                    "vertical_farm_cassette_interface", "row_carried_by_profile"):
        for check in catalog.features[feature].verified_by:
            if check.startswith("assembly.") and check not in cad_only:
                assert check in passed and check not in failed, (feature, check)


def test_meta_row_kind(row_report):
    assert row_report["meta"]["row_kind"] == "tilted_flush_row"


# -- mutations -------------------------------------------------------------------


def _mutate(tmp_path, patch, src=None) -> Path:
    src = src or ROW
    doc = yaml.safe_load(src.read_text())
    patch(doc)
    out = tmp_path / src.name
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return out


def _run(path):
    try:
        return run_assembly_validate(path, None)
    except AssemblyFailure as exc:
        return exc.report


def _check_failed(report, check: str) -> bool:
    return any(j["check"] == check and j["status"] == "fail"
               for j in report["joints"])


def test_missing_mount_context_fails(tmp_path):
    def patch(doc):
        doc.pop("mount_context")

    report = _run(_mutate(tmp_path, patch, src=SMOKE))
    assert _check_failed(report, "assembly.row_drains_under_mount")


def test_flat_mount_fails(tmp_path):
    def patch(doc):
        doc["mount_context"]["slope_deg"] = 0.5

    report = _run(_mutate(tmp_path, patch, src=SMOKE))
    assert _check_failed(report, "assembly.row_drains_under_mount")


def test_steep_mount_fails(tmp_path):
    def patch(doc):
        doc["mount_context"]["slope_deg"] = 2.5

    report = _run(_mutate(tmp_path, patch, src=SMOKE))
    assert _check_failed(report, "assembly.row_drains_under_mount")


def test_band_edges_pass(tmp_path):
    for slope in (1.0, 2.0):
        def patch(doc, s=slope):
            doc["mount_context"]["slope_deg"] = s

        report = _run(_mutate(tmp_path, patch, src=SMOKE))
        assert not _check_failed(report, "assembly.row_drains_under_mount"), slope


def test_no_magnets_leaves_water_untouched(tmp_path):
    """Magnets off: fluid/lap verdicts identical, magnet check goes n/a."""
    def patch(doc):
        for part in doc["parts"]:
            part["product"]["params"].pop("magnet_enabled", None)

    report = _run(_mutate(tmp_path, patch))
    assert report["status"] == "pass"
    checks = _joints(report)
    assert all(j["status"] == "pass" for j in checks["assembly.lap_flow_ir"])
    assert "nothing to align" in checks["assembly.magnet_alignment_ok"][0]["message"]


def test_smoke_validates():
    report = run_assembly_validate(SMOKE, None)
    assert report["status"] == "pass"
    checks = _joints(report)
    assert len(checks["assembly.lap_flow_ir"]) == 1


def test_no_cascade_left_in_public_examples():
    for path in EXAMPLES.glob("*.yaml"):
        text = path.read_text()
        assert "fluid_cascade" not in text, path.name
        assert "row_fluid_chain" not in text, path.name
