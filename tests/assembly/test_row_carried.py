"""VF-4 carried row at the IR level: the golden cascade rides two sloped
profile carriers (reference proxies) — every rail supported at its
station, pitch aligned, carrier slope derived from the water physics.
Mutations on the carried smoke: a flat carrier fights the water, a rail
left unperched hangs on its fluid joint, an undersized profile loses its
stations."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.assembly.pipeline import (
    AssemblyFailure,
    run_assembly_validate,
)
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
CARRIED = EXAMPLES / "vertical_farm_row_3x1_carried.yaml"
SMOKE = EXAMPLES / "vertical_farm_carried_smoke.yaml"


def mutate(tmp_path, src: Path, patch) -> Path:
    doc = yaml.safe_load(src.read_text())
    patch(doc)
    out = tmp_path / src.name
    out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
    return out


def checks_of(report, name):
    return [j for j in report["joints"] if j["check"] == name]


def run(path):
    try:
        return run_assembly_validate(path, None)
    except AssemblyFailure as exc:
        return exc.report


@pytest.fixture(scope="module")
def carried_report():
    return run_assembly_validate(CARRIED, None)


def test_carried_row_validates(carried_report):
    assert carried_report["status"] == "pass"
    assert carried_report["meta"]["mounting_policy"] == "profile_carried"


def test_every_rail_supported(carried_report):
    supported = checks_of(carried_report, "assembly.row_supported")
    assert supported and supported[0]["status"] == "pass"
    assert "3 rail(s) rest on 2 profile(s)" in supported[0]["message"]
    # the honest span-gap note: flat groove on a sloped line
    assert supported[0]["measured"] == pytest.approx(7.91, abs=0.05)
    assert "VF-4.1" in supported[0]["message"]


def test_pitch_and_slope_verdicts(carried_report):
    assert checks_of(carried_report, "assembly.row_pitch_aligned")[0]["status"] == "pass"
    assert checks_of(
        carried_report, "assembly.profile_slope_feeds_downhill")[0]["status"] == "pass"


def test_perch_joints_pass(carried_report):
    perch = checks_of(carried_report, "assembly.profile_perch_ir")
    assert len(perch) == 6
    assert all(p["status"] == "pass" for p in perch)


def test_vf3_water_story_untouched(carried_report):
    fluid = checks_of(carried_report, "assembly.fluid_joint_ir")
    assert len(fluid) == 4
    assert all(f["status"] == "pass" for f in fluid)
    inserts = checks_of(carried_report, "assembly.removable_insert_ir")
    assert len(inserts) == 3
    assert all(i["status"] == "pass" for i in inserts)


def test_carried_smoke_validates():
    report = run_assembly_validate(SMOKE, None)
    assert report["status"] == "pass"
    assert checks_of(report, "assembly.row_supported")[0]["status"] == "pass"


def test_derived_slope_tracks_the_water(tmp_path):
    """The carrier's grade is DERIVED from the shared channel slope — a
    different legal slope re-derives BOTH the cascade and the carrier in
    sync, so the row stays supported. Desync is unrepresentable by
    construction; this pins the derivation."""
    def patch(doc):
        doc["shared"]["slope_deg"] = 1.0

    report = run(mutate(tmp_path, SMOKE, patch))
    assert checks_of(report, "assembly.profile_slope_feeds_downhill")[0]["status"] == "pass"
    assert checks_of(report, "assembly.row_supported")[0]["status"] == "pass"


def test_unperched_rail_hangs_on_fluid_joint(tmp_path):
    def patch(doc):
        doc["joints"] = [j for j in doc["joints"]
                         if j["type"] != "profile_perch"
                         or j["a"] != "rail_2.seat_e"]

    report = run(mutate(tmp_path, CARRIED, patch))
    supported = checks_of(report, "assembly.row_supported")
    assert supported[0]["status"] == "fail"
    assert "hangs on its fluid joint" in supported[0]["message"] or \
           "hangs on" in supported[0]["message"]


def test_missing_all_perch_is_not_carried(tmp_path):
    """Without perch joints the carried feature must stay un-built."""
    def patch(doc):
        doc["joints"] = [j for j in doc["joints"]
                         if j["type"] != "profile_perch"]

    report = run(mutate(tmp_path, SMOKE, patch))
    # row checks vanish (n/a) -> row_carried_by_profile cannot be verified
    assert not checks_of(report, "assembly.row_supported")
    # and the part is now orphaned in the pose (profile posed by nothing)
    poses = [j for j in report["joints"] if j["check"] == "assembly.joint_pose"]
    assert any("not posed" in p["message"] for p in poses)


def test_short_profile_refuses():
    st = RecipeState()
    with pytest.raises(RecipeError):
        RECIPE_OPS["profile_ref_body"].apply(st, {
            "size": "2020", "length": 300.0, "slope_deg": 1.827,
            "station_pitch": 248.0, "stations": 3, "station_edge": 20.0,
        }, "profile")


def test_wrong_profile_size_fails_perch(tmp_path):
    def patch(doc):
        profile = next(p for p in doc["parts"] if p["ref"] == "profile_e")
        profile["product"]["params"]["size"] = "3030"

    report = run(mutate(tmp_path, SMOKE, patch))
    perch = checks_of(report, "assembly.profile_perch_ir")
    assert perch and perch[0]["status"] == "fail"
    assert "wrong profile size" in perch[0]["message"]
