"""Bio-1 split branch clamp, tier-1: both halves through the full pre-CAD
pipeline (golden zero-FAIL), plus the honest negatives — a bolt over the
open mouth, a doctored channel, a rectangular "dovetail", cord slots
through a bolt column, a compression gap below the floor, and the loader's
fail-fast on unsubscribed op validators."""

from pathlib import Path

import pytest
import yaml

from artifact_forge_ng.catalog.loader import CatalogError, load_catalog
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_clamp import (
    check_clamp_channel_clear,
    check_dovetail_rail_profile,
    check_saddle_geometry_ok,
)
from artifact_forge_ng.form.checks_cuts import check_cuts_respect_keepouts
from artifact_forge_ng.form.part import BoreFeature, PartForm
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.pipeline import run_pre_cad

LOWER = "branch_clamp_lower_v1"
UPPER = "branch_clamp_upper_v1"


def _product_path(tmp_path, archetype: str, **params) -> Path:
    doc = {
        "schema": "product/v1",
        "id": f"test_{archetype}",
        "archetype": f"{archetype}@1",
        "params": {"nominal_branch_d": "60mm", "clamp_w": "40mm",
                   "compression_gap": "3mm", **params},
        "manufacturing": {"material": "PETG", "support_policy": "none"},
    }
    p = tmp_path / f"{archetype}.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


def _fails(state):
    return [f"{f.check}: {f.message}" for f in state.report.findings
            if f.status is Status.FAIL]


def test_golden_lower_full_pre_cad(tmp_path):
    state = run_pre_cad(_product_path(tmp_path, LOWER), None)
    assert _fails(state) == []
    form = state.form
    f = form.frame
    # frame math: gap/2 beyond the mating plane, apex on the base floor
    assert f["saddle_r"] == pytest.approx(30.0)
    assert f["mate_z"] == pytest.approx(8.0 + 30.0 - 1.5)
    assert f["saddle_cz"] == pytest.approx(f["mate_z"] + 1.5)
    assert f["saddle_apex_v"] == pytest.approx(8.0)
    assert int(f["land_count"]) == 2
    # cavity vocabulary reused by topology.cavity_open
    assert f["cavity_center_v"] == pytest.approx(f["saddle_cz"])
    assert f["r_cavity"] == pytest.approx(30.0)
    # the gap is BAKED into the mate datum (joints cannot express offsets)
    assert form.datums["clamp_mate"]["at"] == [20.0, 0.0, f["mate_z"] + 3.0]
    assert form.datums["branch_axis"]["at"][2] == pytest.approx(f["saddle_cz"])
    # regions + the screw_joint pilot convention
    assert {"saddle_contact", "outer_shell"} <= {r.name for r in form.regions}
    pilots = [b for b in form.bores if b.name.startswith("mount_pilot")]
    assert len(pilots) == 4
    assert all(abs(b.center[1]) == pytest.approx(38.0) for b in pilots)
    assert len(form.cutboxes) == 2  # cord slots
    assert form.print_orientation == "side_profile"


def test_golden_upper_full_pre_cad(tmp_path):
    state = run_pre_cad(_product_path(tmp_path, UPPER), None)
    assert _fails(state) == []
    form = state.form
    f = form.frame
    assert f["mate_z"] == 0.0
    assert f["saddle_cz"] == pytest.approx(-1.5)
    assert f["saddle_apex_v"] == pytest.approx(28.5)
    assert f["rail_root_w"] < f["rail_top_w"] == pytest.approx(20.0)
    assert int(f["land_count"]) == 1
    # channel above the apex, below the rail_fix pocket floors
    assert f["channel_z"] - f["channel_d"] / 2.0 >= f["saddle_apex_v"] + 2.0
    rail_fix = [b for b in form.bores if b.name.startswith("rail_fix")]
    assert len(rail_fix) == 2
    for b in rail_fix:
        assert f["channel_z"] + f["channel_d"] / 2.0 + 2.0 <= min(b.span)
    # 4 counterbored clearance holes land on the lower half's pilot grid
    assert len(form.holes) == 4
    assert sorted({round(h.at[1], 3) for h in form.holes}) == [-38.0, 38.0]
    assert all(h.head_style == "cylinder" for h in form.holes)
    assert form.datums["clamp_mate"]["at"] == [20.0, 0.0, 0.0]
    assert {"saddle_contact", "outer_shell", "rail_interface"} <= {
        r.name for r in form.regions}


def test_negative_bolt_over_the_open_mouth(tmp_path):
    """bolt_web ~0: the bolt axis lands inside the saddle mouth — the
    split-clamp geometry check fails before any CAD."""
    state = run_pre_cad(_product_path(tmp_path, LOWER, bolt_web="0.5mm"), None)
    fails = _fails(state)
    assert any("form.saddle_geometry_ok" in f and "mouth" in f for f in fails)


def test_negative_doctored_channel(tmp_path):
    """A channel that no longer spans the body, or dives into the saddle,
    fails form.clamp_channel_clear on the mutated IR."""
    state = run_pre_cad(_product_path(tmp_path, UPPER), None)
    form = state.form
    channel = next(b for b in form.bores if b.name == "cable_channel")
    idx = form.bores.index(channel)
    # short span: not a through channel any more
    form.bores[idx] = BoreFeature(
        name=channel.name, axis=channel.axis, center=channel.center,
        d=channel.d, span=(0.0, form.width - 8.0), overshoot=channel.overshoot,
    )
    finding = check_clamp_channel_clear(form)
    assert finding.status is Status.FAIL and "span" in finding.message
    # blocked: dropped into the saddle apex zone
    zlow = form.frame["saddle_apex_v"]
    form.bores[idx] = BoreFeature(
        name=channel.name, axis=channel.axis,
        center=(0.0, 0.0, zlow), d=channel.d,
        span=channel.span, overshoot=channel.overshoot,
    )
    form.frame["channel_z"] = zlow
    finding = check_clamp_channel_clear(form)
    assert finding.status is Status.FAIL and "saddle" in finding.message


def test_negative_gap_below_min_is_a_resolve_finding(tmp_path):
    state = run_pre_cad(
        _product_path(tmp_path, LOWER, compression_gap="0.5mm"), None)
    clamp_findings = [f for f in state.report.findings
                      if f.check == "param:compression_gap"]
    assert clamp_findings, "expected a resolve finding for the clamped gap"
    assert state.form.frame["clamp_gap"] == pytest.approx(1.5)


def test_negative_rectangular_rail_fails_the_dovetail_check(tmp_path):
    state = run_pre_cad(_product_path(tmp_path, UPPER, rail_angle=0), None)
    fails = _fails(state)
    assert any("form.dovetail_rail_profile" in f for f in fails)
    assert check_dovetail_rail_profile(state.form).status is Status.FAIL


def test_negative_cord_slots_through_a_bolt_column():
    """Move the cord slots onto the bolt pilots: the z_top heatset keepout
    column vetoes them at the IR level (the boss floor-slab trick)."""
    st = RecipeState()
    base = dict(branch_d=60.0, clamp_w=40.0, gap=3.0, base_t=8.0,
                flange_t=10.0, bolt_y=38.0, edge_m=10.0, wall=4.0,
                corner_r=2.5, land_angle=50.0, land_w=14.0, pad_recess=1.2)
    RECIPE_OPS["clamp_half_lower"].apply(st, base, "body")
    mate_z = st.frame["mate_z"]
    RECIPE_OPS["heatset_insert_pocket"].apply(
        st, {"screw": "M4", "depth": 6.0, "spacing": 24.0, "cx": 20.0,
             "cy": 38.0, "z_top": mate_z}, "mount_pilot_a")
    RECIPE_OPS["cord_slot_pair"].apply(
        st, {"slot_l": 8.0, "slot_w": 4.0, "spacing": 76.0, "cx": 32.0},
        "cord_slots")
    form = PartForm(
        name="doctored", params={}, frame=st.frame, section=st.section,
        width=st.width, style=MOLDED_UTILITY_PART, bores=st.bores,
        cutboxes=st.cutboxes, regions=st.regions, datums=st.datums,
    )
    finding = check_cuts_respect_keepouts(form)
    assert finding.status is Status.FAIL
    assert "mount_pilot_a_keep" in finding.message
    # sanity: the intended near-center slots are clear
    assert check_saddle_geometry_ok(form).status is Status.PASS


def test_loader_fail_fast_on_unsubscribed_op_validator(tmp_path):
    """An archetype using clamp_half_lower without form.saddle_geometry_ok
    is refused at catalog load — geometry never ships without its checks."""
    import shutil
    from artifact_forge_ng.catalog import loader

    clone = tmp_path / "data"
    shutil.copytree(Path(loader.DATA_DIR), clone)
    doc = yaml.safe_load(
        (clone / "archetypes" / "branch_clamp_lower_v1.yaml").read_text())
    doc["id"] = "zz_bad_clamp"
    doc["validators"].remove("form.saddle_geometry_ok")
    (clone / "archetypes" / "zz_bad_clamp.yaml").write_text(
        yaml.safe_dump(doc, sort_keys=False))
    with pytest.raises(CatalogError, match="requires validators"):
        load_catalog(clone)


def test_heatset_z_top_zero_keeps_legacy_behavior():
    """Backward compatibility: without z_top the pockets still descend from
    the part top and emit NO keepout column (fastener_plate_v1 land)."""
    st = RecipeState()
    RECIPE_OPS["rounded_plate"].apply(
        st, {"l": 80.0, "w": 50.0, "t": 8.0, "corner_r": 3.0}, "plate")
    regions_before = len(st.regions)
    RECIPE_OPS["heatset_insert_pocket"].apply(
        st, {"screw": "M3", "depth": 5.0, "spacing": 30.0, "cx": 0.0,
             "cy": 0.0, "z_top": 0.0}, "inserts")
    assert len(st.regions) == regions_before  # no keepout columns
    for b in st.bores:
        assert b.span == (3.0, 8.0)  # t - depth .. t, exactly as before


def test_clamp_modifier_grounding_offers_only_the_bio_canvas():
    """nl_edit grounding: the bio modifiers land ONLY on outer_shell."""
    from artifact_forge_ng.catalog.loader import compatible_regions

    catalog = load_catalog()
    for arch in (LOWER, UPPER):
        spec = catalog.archetypes[arch]
        mod = catalog.modifiers["apply_biomorphic_exoskeleton"]
        assert [r.id for r in compatible_regions(spec, mod)] == ["outer_shell"]
        protected = {r.id for r in spec.regions if not r.editable}
        assert "saddle_contact" in protected
