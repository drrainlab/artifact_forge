"""Wave P2 wearable cuff: golden pre-CAD run, frame math, the S/L
zero-hand-edits criterion, mutation negatives for every wearable check,
and the strap-slot contract honesty (no modifier -> strict failure)."""

import math
from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.profiles_wearable import (
    CuffParams, build_forearm_cuff_profile,
)
from artifact_forge_ng.form.checks_wearable import (
    check_arm_mouth_dons_ok, check_body_clearance_ok,
    check_pad_recess_exists, check_payload_mount_not_on_skin_side,
    check_payload_retention_ok, check_strap_access_ok,
)
from artifact_forge_ng.pipeline import PipelineFailure, run_pre_cad

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GOLDEN = EXAMPLES / "forearm_flashlight_cuff.yaml"


def _fails(state):
    return [f for f in state.report.findings if f.status is Status.FAIL]


def _write_variant(tmp_path, **body_fit_overrides):
    doc = yaml.safe_load(GOLDEN.read_text())
    doc["body_fit"].update(body_fit_overrides)
    p = tmp_path / "cuff.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


# -- golden ----------------------------------------------------------------

def test_golden_cuff_pre_cad_passes():
    state = run_pre_cad(GOLDEN, None)
    assert _fails(state) == []
    f = state.form.frame
    r_expected = 270.0 / (2.0 * math.pi) + 6.0
    assert f["arm_r_inner"] == pytest.approx(r_expected, abs=1e-6)
    assert f["land_count"] == 3.0
    # payload clip rides outside the ring with the declared bridge
    assert f["payload_cv"] == pytest.approx(
        f["arm_r_outer"] + 4.0 + f["payload_r_outer"], abs=1e-6)
    # donning: mouth within the flesh window
    d_eff = 270.0 / math.pi
    assert 0.75 * d_eff <= f["arm_mouth_gap"] <= 1.02 * d_eff
    # 4 strap slots (2 per tab) made it into the form
    slots = [c for c in state.form.cutboxes if c.name.startswith("strap_slot")]
    assert len(slots) == 4
    s = state.summary()
    assert s["mode"] == "wearable"
    assert "body_fit" in s.get("mode_tags", [])


def test_sizes_S_and_L_build_with_zero_hand_edits(tmp_path):
    """The ROADMAP P2 criterion: same YAML, different bodies."""
    for circ in ("220mm", "320mm"):
        state = run_pre_cad(_write_variant(tmp_path, circumference=circ), None)
        assert _fails(state) == [], f"size {circ} failed"


def test_missing_body_fit_is_a_named_param_fail(tmp_path):
    doc = yaml.safe_load(GOLDEN.read_text())
    del doc["body_fit"]
    doc["mode"] = "engineering"  # wearable would already reject at schema
    p = tmp_path / "cuff.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    state = run_pre_cad(p, None)
    fails = {f.check: f for f in _fails(state)}
    assert "param:arm_circumference" in fails
    assert "body_circumference" in fails["param:arm_circumference"].message
    assert "body_fit" in fails["param:arm_circumference"].message
    with pytest.raises(PipelineFailure, match="param:arm_circumference"):
        state.enforce_strict()


def test_strapless_cuff_fails_the_contract(tmp_path):
    doc = yaml.safe_load(GOLDEN.read_text())
    doc["modifiers"] = []
    p = tmp_path / "cuff.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    state = run_pre_cad(p, None)
    with pytest.raises(PipelineFailure, match="strap_mount"):
        state.enforce_strict()


# -- profile geometry -------------------------------------------------------

def test_profile_closes_across_sizes_and_captures():
    for circ, cap in [(220.0, 240.0), (320.0, 240.0), (270.0, 262.0),
                      (270.0, 210.0)]:
        profile, _ = build_forearm_cuff_profile(
            CuffParams(arm_circumference=circ, arm_capture_deg=cap))
        segs = list(profile.outer.segments)
        for i, s in enumerate(segs):
            nxt = segs[(i + 1) % len(segs)]
            assert s.b.dist(nxt.a) < 1e-6, f"gap after segment {i}"


def test_builder_refuses_nonsense():
    with pytest.raises(ValueError, match="205..262"):
        build_forearm_cuff_profile(
            CuffParams(arm_circumference=270.0, arm_capture_deg=190.0))
    with pytest.raises(ValueError, match="not smaller than the limb"):
        build_forearm_cuff_profile(
            CuffParams(arm_circumference=200.0, payload_d=70.0))
    with pytest.raises(ValueError, match="usable tab"):
        build_forearm_cuff_profile(
            CuffParams(arm_circumference=270.0, tab_len=14.0,
                       arm_capture_deg=210.0))


# -- mutation negatives ------------------------------------------------------

@pytest.fixture()
def golden_form():
    return run_pre_cad(GOLDEN, None).form


def test_doctored_radius_fails_body_clearance(golden_form):
    golden_form.frame["arm_r_inner"] -= 2.0
    finding = check_body_clearance_ok(golden_form)
    assert finding.status is Status.FAIL


def test_widened_frame_gap_fails_donning(golden_form):
    # pretend the limb is much thicker than the cavity was built for
    golden_form.params["body_d_eff"] = 130.0
    finding = check_arm_mouth_dons_ok(golden_form)
    assert finding.status is Status.FAIL
    assert "donning" in finding.message or "outside" in finding.message


def test_missing_pad_lands_fail(golden_form):
    kept = [s for s in golden_form.section.outer.segments
            if "pad_land" not in s.tags]
    golden_form.section.outer.segments = tuple(kept) if isinstance(
        golden_form.section.outer.segments, tuple) else kept
    finding = check_pad_recess_exists(golden_form)
    assert finding.status is Status.FAIL


def test_payload_mirrored_to_skin_side_fails(golden_form):
    golden_form.frame["payload_cv"] = -golden_form.frame["payload_cv"]
    finding = check_payload_mount_not_on_skin_side(golden_form)
    assert finding.status is Status.FAIL
    assert "skin" in finding.message or "arm" in finding.message


def test_shallow_payload_arc_fails_retention(golden_form):
    golden_form.frame["payload_arc_deg"] = 300.0  # declared != measured
    finding = check_payload_retention_ok(golden_form)
    assert finding.status is Status.FAIL


def test_slot_into_the_arm_circle_fails_strap_access(golden_form):
    slot = next(c for c in golden_form.cutboxes
                if c.name.startswith("strap_slot"))
    # teleport one slot to the cavity center band
    import dataclasses
    from artifact_forge_ng.form.regions import Box3
    bad = dataclasses.replace(
        slot, box=Box3(slot.box.x0, -13.0, slot.box.z0, slot.box.x1, 13.0,
                       slot.box.z1))
    golden_form.cutboxes[:] = [
        bad if c.name == slot.name else c for c in golden_form.cutboxes
    ]
    finding = check_strap_access_ok(golden_form)
    assert finding.status is Status.FAIL


def test_single_slot_per_tab_fails_strap_access(golden_form):
    golden_form.cutboxes[:] = [
        c for c in golden_form.cutboxes
        if not c.name.startswith("strap_slot_strap_land_left_1")
    ]
    finding = check_strap_access_ok(golden_form)
    assert finding.status is Status.FAIL
    assert "strap_land_left" in finding.message
