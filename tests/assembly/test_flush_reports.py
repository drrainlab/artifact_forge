"""Row reports after the VF correction, at the IR level: water_report
tells the tilted flush row story (virtual drop, lap + drip handovers,
controlled seam leak), frame_report reports FULL seating on standard
straight profiles (span gap 0), and the BOM carries cut-to-length
profiles, the mount note and the magnet line."""

from pathlib import Path

import pytest

from artifact_forge_ng.assembly.bom import build_bom
from artifact_forge_ng.assembly.frame_report import build_frame_report
from artifact_forge_ng.assembly.pipeline import (
    _inject_shared,
    _joint_findings,
    load_assembly,
)
from artifact_forge_ng.assembly.water_report import build_water_report
from artifact_forge_ng.catalog.loader import load_catalog
from artifact_forge_ng.pipeline import pre_cad_from_instance

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples" / "vertical_farm"
ROW = EXAMPLES / "vertical_farm_row_3x1.yaml"
CELL = EXAMPLES / "water_rail_cell_2020_petg.yaml"


@pytest.fixture(scope="module")
def row_ctx():
    catalog = load_catalog()
    asm = load_assembly(ROW)
    instances = _inject_shared(asm, catalog)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in instances.items()}
    findings, poses, _ = _joint_findings(asm, states)
    return catalog, asm, states, findings, poses


def test_water_report_row_rollup(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    water = build_water_report(states, findings, asm=asm, poses=poses)
    row = water["row"]
    assert row["kind"] == "tilted_flush_row"
    assert row["modules_flush"] is True
    assert row["stair_step"] is False
    assert row["slope_deg"] == pytest.approx(1.5)
    assert row["slope_source"] == "mounted_profile"
    assert row["cells"] == 3
    # total virtual drop over the whole floor path — positive, real
    assert row["total_virtual_drop_mm"] > 10.0
    kinds = [h["type"] for h in row["handovers"]]
    assert kinds.count("lap_flow") == 2
    assert kinds.count("drip") == 2
    for h in row["handovers"]:
        assert h["status"] == "pass", h
        if h["type"] == "lap_flow":
            assert abs(h["dz_mm"]) <= 0.05  # flush means flush
    assert row["standing_water_under_mount"] == "none"
    assert row["lap_seam_leak"] == "controlled"
    assert set(row["drips_clear_of"]) == {"profiles", "magnets", "dry_zones"}
    assert row["orphan_fluid_ports"] == "none"
    # VF-4.2 honesty: the skeleton rail does not contain top-water overflow
    oc = row["overflow_containment"]
    assert oc["status"] == "absent"
    assert oc["path"] == "drains_through_skeleton"
    assert "VF-5" in oc["planned_fix"]


def test_water_report_channel_is_level(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    water = build_water_report(states, findings, asm=asm, poses=poses)
    ch = water["channel"]
    assert ch["slope_deg"] == 0.0
    assert ch["drop_mm"] == 0.0
    assert ch["depth_inlet_mm"] == ch["depth_outlet_mm"]
    lap = water["lap_handover"]
    assert lap["lip_len_mm"] == pytest.approx(4.0)
    assert lap["face_gap_mm"] == pytest.approx(0.4)


def test_frame_report_flush(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    frame = build_frame_report(asm, states, findings)
    assert frame["slope_source"] == "physical_mount"
    assert frame["slope_deg"] == pytest.approx(1.5)
    assert frame["full_profile_seating"] is True
    assert frame["span_gap_mm"] == 0
    assert frame["stair_step"] is False
    assert frame["modules_flush"] is True
    assert frame["drainage_verdict"] == "pass"
    for prof in frame["carrier"]:
        assert prof["slope_deg"] == 0.0  # the MODEL is straight
        assert "straight" in prof["geometry"]
    for rail in frame["rails"]:
        assert rail["contact"] == "full_length"
        assert len(rail["perched_on"]) == 2
    magnets = frame["magnet_installation"]
    assert magnets["method"] == "press_fit_dry_face"
    assert magnets["water_exposed"] is False
    assert magnets["role"] == "alignment_only"
    assert magnets["count"] == 12


def test_bom_profiles_magnets_and_mount_note(row_ctx):
    catalog, asm, states, findings, poses = row_ctx
    bom = build_bom(asm, states, catalog)
    hardware = {h["item"]: h for h in bom["hardware"]}
    profile = next(v for k, v in hardware.items() if "aluminum profile" in k)
    assert profile["qty"] == 2
    assert "standard straight" in profile["item"]
    assert "1.5" in profile["note"] and "mount the WHOLE row" in profile["note"]
    magnet = next(v for k, v in hardware.items() if "magnet" in k)
    assert magnet["qty"] == 12  # 3 rails x 4 sealed pockets
    assert "alignment only" in magnet["note"]
    assert "coated" in magnet["note"] or "epoxy" in magnet["note"]
    printed = {p["archetype"]: p for p in bom["printed_parts"]}
    assert printed["water_rail_v1"]["qty"] == 3
    assert "aluminum_profile_ref_v1" not in printed  # reference, never printed


def test_single_cell_report_shape_unchanged():
    catalog = load_catalog()
    asm = load_assembly(CELL)
    instances = _inject_shared(asm, catalog)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in instances.items()}
    findings, poses, _ = _joint_findings(asm, states)
    water = build_water_report(states, findings, asm=asm, poses=poses)
    assert water["mode"] == "transient_pulse"
    assert water["storage"] == "forbidden"
    assert water["channel"]["slope_deg"] == 0.0
    assert "row" not in water  # no water joints — no row story
    frame = build_frame_report(asm, states, findings)
    assert frame is None  # no carrier — no frame story


# -- VF-5A: the root chamber row -----------------------------------------------

ROW_RC = EXAMPLES / "vertical_farm_row_3x1_root_chamber.yaml"


def test_root_chamber_row_contains_overflow_and_drains():
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    findings, poses, _ = _joint_findings(asm, states)
    checks = {}
    for f in findings:
        checks.setdefault(f.check, []).append(f.status.value)
    assert checks["assembly.collector_catches_root_drainage"] == ["pass"]
    water = build_water_report(states, findings, asm=asm, poses=poses)
    row = water["row"]
    oc = row["overflow_containment"]
    assert oc["status"] == "contained"
    assert oc["return"] == "passive_root_drainage_return"
    rm = row["cassette_removal"]
    assert "roots" in rm["mid_cycle"]
    # the rails really are root chambers
    r1 = states["rail_1"].report
    assert r1.passed("form.root_chamber_ok")
    assert r1.passed("form.no_secondary_water_channel")  # troughs exempt


def test_root_chamber_row_endcaps_dock_magnetically():
    """VF-6: the collector and inlet cap magnetically dock onto the terminal
    modules' end wall tops — the seating check proves both mates."""
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    findings, poses, _ = _joint_findings(asm, states)
    docks = [f for f in findings if f.check == "assembly.endcap_docks_to_rail"]
    assert len(docks) == 2  # collector (front) + cap (back)
    for f in docks:
        assert f.status.value == "pass", f.message
        assert f.measured < 1.0
    # only the terminal rails carry dock pockets; the middle one does not
    assert states["rail_1"].form.frame["dock_pocket_count"] == 2
    assert states["rail_2"].form.frame["dock_pocket_count"] == 0
    assert states["rail_3"].form.frame["dock_pocket_count"] == 2
    assert states["collector"].report.passed("form.dock_pockets_dry")
    assert states["cap"].report.passed("form.dock_pockets_dry")


def test_root_chamber_row_drain_screen_and_maintenance():
    """VF-8: the drop-in screen basket seats over the collector drain with no
    unfiltered bypass, and the row reports a machine-derived maintenance
    workflow."""
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    findings, poses, _ = _joint_findings(asm, states)
    nb = [f for f in findings if f.check == "assembly.screen_normal_no_bypass"]
    assert len(nb) == 1
    assert nb[0].status.value == "pass", nb[0].message
    assert "mesh-only" in nb[0].message  # normal_no_bypass
    # the basket itself validates (open area, debris reservoir, tool-free rim)
    sc = states["screen"].report
    assert sc.passed("form.screen_open_area_ratio_ok")
    assert sc.passed("form.screen_debris_capacity_ok")
    assert sc.passed("form.lift_access_ok")
    # maintenance workflow in the water report
    water = build_water_report(states, findings, asm=asm, poses=poses)
    m = water["row"]["maintenance"]
    assert m["all_tool_free"] is True
    assert "drain_screen" in m and "rinse" in m["drain_screen"]
    assert "unfiltered bypass" in m["drain_screen"]  # default zero-bypass
    assert "DEBRIS-REDUCED" in m["honest_note"]


def test_root_chamber_row_radial_funnel_sump():
    """VF-8.1: the collector drains through a LOWERED sump well fed by a radial
    funnel (the drain at the absolute low point, the basket seated in the well
    over it, not a barrier), verified by the six named checks."""
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    col = states["collector"].report
    for c in ("form.collector_sump_is_lowest_point",
              "form.tray_floor_slopes_to_sump",
              "form.basket_not_transverse_flow_barrier",
              "form.no_standing_water_before_screen"):
        assert col.passed(c), c
    # the collector really carries a funnel cut converging to the drain
    funnels = states["collector"].form.funnel_cuts
    assert len(funnels) == 1
    assert funnels[0].top[0] > funnels[0].bottom[0]     # slopes inward in X
    assert funnels[0].z_top > funnels[0].z_bottom       # and downward to the sump
    findings, poses, _ = _joint_findings(asm, states)
    checks = {f.check: f.status.value for f in findings}
    assert checks.get("assembly.drain_inside_screen_footprint") == "pass"
    assert checks.get("assembly.screen_removable_from_sump") == "pass"


def test_root_chamber_row_builds_strict():
    """VF-8 strict gate: EVERY part in the row (incl. the collector with the
    screen_seat recess and the drop-in screen) must have NO critical failure —
    i.e. `forge build --strict` would not abort. A golden that only validates
    at pre-CAD but trips enforce_strict is the class this catches cheaply."""
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    for ref, st in states.items():
        crit = st.report.critical_failures()
        assert not crit, f"{ref}: " + ", ".join(f.check for f in crit)


def test_universal_rail_floored_inlet_no_through_hole():
    """VF-9: every rail is UNIVERSAL — a FLOORED lip-seat inlet (solid bottom,
    no through hole under the water path). The cap drip lands on a channel-safe
    floor; the module seam has no external downward leak; the always-on
    no-through-hole invariant passes for every rail."""
    from artifact_forge_ng.validators.manufacturing import (
        no_through_holes_in_wet_lap_zone)
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    for ref in ("rail_1", "rail_2", "rail_3"):
        st = states[ref]
        pockets = [c for c in st.form.cutboxes if "lap_receiver" in c.name]
        assert len(pockets) == 1, ref
        assert pockets[0].box.z0 > 0.05, f"{ref}: receiver must be FLOORED"  # closed below
        assert st.report.passed("form.lap_receiver_has_floor"), ref
        assert st.report.passed("form.lap_receiver_residual_volume_ok"), ref
        assert st.report.passed("form.rail_universal_inlet_accepts_cap_and_lap"), ref
        # the manufacturing invariant runs at the CAD stage; assert on the form
        assert no_through_holes_in_wet_lap_zone(
            None, st.form).status.value == "pass", ref
    findings, _, _ = _joint_findings(asm, states)
    checks = {}
    for f in findings:
        checks.setdefault(f.check, []).append(f.status.value)
    assert checks.get("assembly.cap_drip_lands_in_channel_safe_floor") == ["pass"]
    assert all(s == "pass" for s in checks.get(
        "assembly.lap_joint_no_external_downward_leak", []))


def test_through_receiver_reintroduced_fails_invariant():
    """Mutation: reintroduce a through open-bottom lap receiver under the water
    path → the no-through-hole invariant + the has-floor + cap-drip checks all
    FAIL. Verified directly on the checks with a hand-mutated rail form."""
    from artifact_forge_ng.form.checks_water import check_lap_receiver_has_floor
    from artifact_forge_ng.validators.manufacturing import (
        no_through_holes_in_wet_lap_zone)
    from artifact_forge_ng.assembly.joints import (
        _cap_drip_lands_in_channel_safe_floor)
    catalog = load_catalog()
    asm = load_assembly(ROW_RC)
    states = {ref: pre_cad_from_instance(inst, catalog, True)
              for ref, inst in _inject_shared(asm, catalog).items()}
    rail = states["rail_2"].form
    # drop the floored pocket to a through hole (open bottom, z0 = -1)
    for i, c in enumerate(rail.cutboxes):
        if "lap_receiver" in c.name:
            b = c.box
            rail.cutboxes[i] = type(c)(name=c.name, box=type(b)(
                b.x0, b.y0, -1.0, b.x1, b.y1, b.z1))
            break
    assert check_lap_receiver_has_floor(rail).status.value == "fail"
    assert no_through_holes_in_wet_lap_zone(None, rail).status.value == "fail"
    assert _cap_drip_lands_in_channel_safe_floor(rail).status.value == "fail"
