"""Vertical farm recipe ops: each op emits its declared IR, regions and
frame keys, and — the real interface proof — forms assembled from the op
chains PASS the water/cassette checks from checks_water.py and
checks_substrate_cassette.py (the ops publish exactly the frame contract
the checks read)."""

import pytest

from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.checks_substrate_cassette import (
    check_cassette_no_reservoir,
    check_contact_window_geometry_ok,
    check_lift_access_ok,
    check_mesh_floor_orthogonal_ok,
    check_snap_pockets_cleanable,
)
from artifact_forge_ng.form.checks_water import (
    check_cassette_seat_fit_ok,
    check_drainage_requires_mount,
    check_lap_joint_geometry_ok,
    check_lap_slot_leak_path_controlled,
    check_lightweight_windows_dry_ok,
    check_magnet_pockets_do_not_break_wall,
    check_magnet_pockets_outside_water_zone,
    check_no_secondary_water_channel,
    check_no_standing_water_ir,
    check_profile_seat_dry_ok,
    check_tongue_groove_profile_ok,
    check_water_channel_constant_depth_ok,
    check_water_channel_dims_ok,
)
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART
from artifact_forge_ng.validators.probes import KNOWN_CHECKS

RAIL_PARAMS = dict(
    module_l=248.0, module_w=248.0, body_h=30.0,
    channel_w=16.0, channel_d=5.0, channel_bottom_r=1.2,
    cassette_l=220.0, cassette_w=220.0,
    seat_depth=14.0, seat_clearance=0.75,
    module_pitch=250.0, corner_r=4.0,
    face_gap=0.4, lightweight=True, lw_rib=2.0,
    profile="2020", profile_inset=24.0,
)


def build_rail(**over) -> RecipeState:
    st = RecipeState()
    p = dict(RAIL_PARAMS)
    p.update(over)
    RECIPE_OPS["water_rail_body"].apply(st, p, "body")
    RECIPE_OPS["lap_outlet_lip"].apply(
        st, {"lip_len": 4.0, "lip_t": 1.4}, "lap_out")
    RECIPE_OPS["lap_inlet_receiver"].apply(
        st, {"pocket_len": 6.0, "side_clearance": 0.4}, "lap_in")
    RECIPE_OPS["edge_magnet_pockets"].apply(
        st, {"enabled": True, "magnet_d": 6.0, "magnet_t": 2.0,
             "fit_clearance": 0.2, "x_offset": 60.0, "z_center": 8.0}, "magnets")
    RECIPE_OPS["profile_seat_slot"].apply(
        st, {"profile": "2020", "clearance": 0.2, "depth": 6.0, "inset": 24.0},
        "profile")
    RECIPE_OPS["tongue_groove_edges"].apply(
        st, {"tongue_w": 6.0, "tongue_h": 4.0, "tongue_len": 3.6,
             "clearance": 0.4, "z0": 4.0, "bottom_margin": 0.4}, "edges")
    return st


def build_cassette() -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["substrate_tray_body"].apply(
        st, {"cassette_l": 220.0, "cassette_w": 220.0, "h": 26.0,
             "wall": 2.4, "floor_t": 2.0, "corner_r": 3.0}, "tray")
    RECIPE_OPS["contact_window"].apply(
        st, {"window_w": 12.0, "window_l": 60.0, "drop": 1.5,
             "cx": 0.0, "cy": 0.0}, "window")
    RECIPE_OPS["mesh_floor"].apply(
        st, {"cell": 6.0, "rib": 1.3, "margin": 6.0}, "mesh")
    for op_id, off in (("snap_window_a", -60.0), ("snap_window_b", 60.0)):
        RECIPE_OPS["snap_window_pair"].apply(
            st, {"w": 10.0, "h": 4.0, "top_offset": 8.5, "offset": off}, op_id)
    RECIPE_OPS["lift_tabs"].apply(st, {"notch_w": 18.0, "notch_d": 8.0}, "lift")
    return st


def build_frame() -> RecipeState:
    st = RecipeState()
    RECIPE_OPS["retainer_frame_body"].apply(
        st, {"l": 219.0, "w": 219.0, "t": 3.0, "band_w": 10.0, "corner_r": 3.0},
        "frame")
    RECIPE_OPS["frame_snap_hooks"].apply(
        st, {"beam_t": 1.6, "hook_w": 8.0, "hook_len": 9.0, "lip_d": 1.4,
             "lip_h": 3.0, "hook_span": 214.6, "sy": 120.0}, "snap")
    return st


def to_form(st: RecipeState, name: str, params: dict | None = None) -> PartForm:
    return PartForm(
        name=name, params=params or {}, frame=st.frame,
        section=st.section, width=st.width, style=MOLDED_UTILITY_PART,
        channels=st.channels, cutboxes=st.cutboxes, bores=st.bores,
        ribs=st.ribs, fields=st.fields, regions=st.regions, datums=st.datums,
    )


def test_all_declared_validators_exist():
    for op in ("water_rail_body", "lap_outlet_lip", "lap_inlet_receiver",
               "edge_magnet_pockets", "profile_seat_slot",
               "tongue_groove_edges", "substrate_tray_body", "contact_window",
               "mesh_floor", "lift_tabs", "retainer_frame_body",
               "frame_snap_hooks"):
        for check in RECIPE_OPS[op].validators:
            assert check in KNOWN_CHECKS, (op, check)


def test_rail_ops_satisfy_water_checks():
    form = to_form(build_rail(), "rail",
                   {"cassette_l": 220.0, "cassette_w": 220.0})
    for check in (check_water_channel_constant_depth_ok,
                  check_water_channel_dims_ok, check_drainage_requires_mount,
                  check_no_standing_water_ir, check_lap_joint_geometry_ok,
                  check_lap_slot_leak_path_controlled,
                  check_magnet_pockets_outside_water_zone,
                  check_magnet_pockets_do_not_break_wall,
                  check_lightweight_windows_dry_ok,
                  check_no_secondary_water_channel, check_cassette_seat_fit_ok,
                  check_tongue_groove_profile_ok, check_profile_seat_dry_ok):
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_rail_frame_contract_keys():
    st = build_rail()
    for key in ("channel_center_x", "channel_w", "channel_top_z",
                "channel_floor_z_inlet", "channel_floor_z_outlet",
                "channel_slope_deg", "channel_floor_margin",
                "seat_u0", "seat_v0", "seat_u1", "seat_v1", "seat_floor_z",
                "seat_depth", "seat_clearance",
                "face_gap", "flush_pitch",
                "lap_lip_len", "lap_lip_w", "lap_lip_t", "lap_lip_top_z",
                "lap_pocket_len", "lap_pocket_w",
                "magnet_count", "magnet_x_offset",
                "lw_enabled", "lw_window_count", "lw_rib",
                "tongue_w", "groove_w", "module_pitch", "profile_size"):
        assert key in st.frame, key
    for datum in ("cassette_seat", "module_origin", "line_east", "line_west",
                  "inlet", "outlet", "feed", "drain_edge"):
        assert datum in st.datums, datum
    names = {r.name for r in st.regions}
    assert {"water_channel", "lap_lip", "lap_receiver",
            "cassette_seat_walls"} <= names


def test_rail_channel_is_level():
    st = build_rail()
    ch = st.channels[0]
    assert ch.y0 > ch.y1  # inlet back (+Y), outlet front (-Y)
    assert ch.depth_end == pytest.approx(ch.depth_start)
    assert st.frame["channel_slope_deg"] == 0.0
    assert st.frame["channel_floor_z_inlet"] == st.frame["channel_floor_z_outlet"]


def test_rail_flush_datums():
    st = build_rail()
    floor = st.frame["channel_floor_z_inlet"]
    inlet, outlet = st.datums["inlet"]["at"], st.datums["outlet"]["at"]
    assert inlet[2] == outlet[2] == floor  # dZ = 0 mate by construction
    # mating outlet-on-inlet marches at module_w + face_gap
    assert (inlet[1] - outlet[1]) == pytest.approx(248.0 + 0.4)
    feed = st.datums["feed"]["at"]
    assert feed[2] == pytest.approx(floor + 2.5)  # the only surviving fall
    drain = st.datums["drain_edge"]["at"]
    assert drain[1] == pytest.approx(-124.0 - 4.0)
    assert drain[2] == pytest.approx(floor - 1.4)  # lip tip underside


def test_rail_lightweight_reversible():
    heavy = build_rail(lightweight=False)
    light = build_rail()
    def lwins(st):
        return [c for c in st.cutboxes if "_lwin_" in c.name]
    assert not lwins(heavy) and not heavy.frame["lw_enabled"]
    assert len(lwins(light)) == light.frame["lw_window_count"] >= 10


def test_rail_refuses_thin_floor():
    with pytest.raises(RecipeError):
        build_rail(body_h=22.0, seat_depth=15.0)  # floor margin < 2

def test_rail_refuses_face_gap_out_of_band():
    with pytest.raises(RecipeError):
        build_rail(face_gap=1.0)


def test_rail_refuses_oversized_cassette():
    with pytest.raises(RecipeError):
        build_rail(cassette_l=240.0)


def test_cassette_ops_satisfy_cassette_checks():
    form = to_form(build_cassette(), "cassette")
    for check in (check_mesh_floor_orthogonal_ok, check_cassette_no_reservoir,
                  check_contact_window_geometry_ok, check_snap_pockets_cleanable,
                  check_lift_access_ok, check_no_secondary_water_channel):
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_cassette_frame_contract_keys():
    st = build_cassette()
    for key in ("cassette_u0", "cassette_v0", "cassette_u1", "cassette_v1",
                "cassette_h", "floor_bottom_z", "window_cx", "window_w",
                "window_floor_z", "shell_wall", "inner_u0", "inner_u1",
                "lift_notch_count"):
        assert key in st.frame, key
    assert "seat" in st.datums and "rim" in st.datums
    assert len([c for c in st.cutboxes if "snap_window" in c.name]) == 4


def test_mesh_pierces_window_slab():
    st = build_cassette()
    fld = st.fields[0]
    assert fld.depth >= 2.0 + 1.5 + 0.5  # floor + drop + margin


def test_contact_window_must_run_before_mesh_for_depth():
    st = RecipeState()
    RECIPE_OPS["substrate_tray_body"].apply(
        st, {"cassette_l": 220.0, "cassette_w": 220.0, "h": 26.0,
             "wall": 2.4, "floor_t": 2.0, "corner_r": 3.0}, "tray")
    RECIPE_OPS["mesh_floor"].apply(
        st, {"cell": 6.0, "rib": 1.3, "margin": 6.0}, "mesh")
    # without a window first, the mesh only pierces the bare floor
    assert st.fields[0].depth == pytest.approx(3.0)


def test_frame_ops_emit_snap_contract():
    st = build_frame()
    lips = [r for r in st.ribs if r.name.startswith("snap_lip")]
    assert len(lips) == 4
    for key in ("snap_beam_t", "snap_hook_len", "snap_lip_d", "snap_hook_w"):
        assert key in st.frame, key
    # printable insertion strain (the snap_joint formula)
    strain = 1.5 * st.frame["snap_lip_d"] * st.frame["snap_beam_t"] / (
        st.frame["snap_hook_len"] ** 2)
    assert strain <= 0.05
    assert "seat" in st.datums


def test_frame_refuses_no_opening():
    st = RecipeState()
    with pytest.raises(RecipeError):
        RECIPE_OPS["retainer_frame_body"].apply(
            st, {"l": 60.0, "w": 60.0, "t": 3.0, "band_w": 25.0,
                 "corner_r": 3.0}, "frame")


# -- VF-5 root chamber under the cassette -------------------------------------


def build_root_chamber(**over):
    st = RecipeState()
    p = dict(RAIL_PARAMS, under_cassette="root_chamber",
             trough_w=26.0, trough_rib=6.0, trough_depth=12.0)
    p.update(over)
    RECIPE_OPS["water_rail_body"].apply(st, p, "body")
    return st


def test_root_chamber_troughs_and_blind_bottom():
    st = build_root_chamber()
    troughs = [c for c in st.channels if "root_trough" in c.name]
    assert len(troughs) == st.frame["root_trough_count"] >= 2
    # troughs are LEVEL const-depth (mount drains them, no geometry slope)
    for c in troughs:
        assert c.depth_start == c.depth_end
    # the blind containment bottom sits below the troughs
    assert st.frame["root_blind_bottom_z"] == pytest.approx(
        st.frame["seat_floor_z"] - 12.0)
    # the main pulse channel is still channels[0], level
    assert st.channels[0].name.endswith("_water")
    assert "root_trough" not in st.channels[0].name


def test_root_chamber_passes_water_checks():
    from artifact_forge_ng.form.checks_water import (
        check_no_secondary_water_channel, check_no_standing_water_ir,
        check_water_channel_constant_depth_ok, check_cassette_seat_fit_ok)
    form = to_form(build_root_chamber(), "rc",
                   {"cassette_l": 220.0, "cassette_w": 220.0})
    for check in (check_water_channel_constant_depth_ok,
                  check_no_secondary_water_channel,   # root troughs exempt
                  check_no_standing_water_ir, check_cassette_seat_fit_ok):
        finding = check(form)
        assert finding.status is Status.PASS, (finding.check, finding.message)


def test_skeleton_and_root_chamber_are_exclusive():
    """The param gate: root_chamber cuts NO skeleton windows (solid blind
    bottom), skeleton cuts NO root troughs."""
    sk = build_rail()  # default skeleton
    assert any("_lwin_" in c.name for c in sk.cutboxes)
    assert not any("root_trough" in c.name for c in sk.channels)
    rc = build_root_chamber()
    assert not any("_lwin_" in c.name for c in rc.cutboxes)
    assert any("root_trough" in c.name for c in rc.channels)


def test_root_chamber_magnets_avoid_troughs():
    """Magnets at the default x60 land in a root trough (wet) — the checks
    catch it; at the perimeter (x84) they sit in dry body."""
    from artifact_forge_ng.form.checks_water import (
        check_magnet_pockets_outside_water_zone)

    def with_magnets(x_off):
        st = build_root_chamber()
        RECIPE_OPS["edge_magnet_pockets"].apply(
            st, {"enabled": True, "magnet_d": 6.0, "magnet_t": 2.0,
                 "fit_clearance": 0.2, "x_offset": x_off, "z_center": 8.0},
            "magnets")
        return to_form(st, "rc")

    assert check_magnet_pockets_outside_water_zone(
        with_magnets(60.0)).status is Status.FAIL   # in a trough
    assert check_magnet_pockets_outside_water_zone(
        with_magnets(84.0)).status is Status.PASS   # dry perimeter


def test_root_chamber_ok_and_mutations():
    from dataclasses import replace
    from artifact_forge_ng.form.checks_water import check_root_chamber_ok
    st = build_root_chamber()
    form = to_form(st, "rc")
    assert check_root_chamber_ok(form).status is Status.PASS
    # skeleton rail: n/a-PASS (no troughs)
    assert check_root_chamber_ok(to_form(build_rail(), "sk")).status is Status.PASS
    # a sloped trough (geometry slope) -> FAIL
    bad = to_form(st, "rc")
    bad.channels[:] = [replace(c, depth_end=c.depth_start + 3.0)
                       if "root_trough" in c.name else c for c in bad.channels]
    f = check_root_chamber_ok(bad)
    assert f.status is Status.FAIL and "not level" in f.message
    # a trough not spanning both faces -> FAIL (no guaranteed drain)
    bad2 = to_form(st, "rc")
    bad2.channels[:] = [replace(c, y1=0.0) if "root_trough" in c.name else c
                        for c in bad2.channels]
    assert check_root_chamber_ok(bad2).status is Status.FAIL
