"""VF-correction/4.1 early CAD smoke: ONE corrected rail really compiles —
constant-depth channel, lap lip welded past the outlet face, THROUGH
open-bottom lap receiver, sealed magnet pockets, and the OPEN SKELETON
lightweight windows (through the under-seat slab — no bridges by
construction). The lightweight gate is reversible and pays its mass
saving; the lap geometry is real on the solid, not just in the IR."""

import pytest

cq = pytest.importorskip("cadquery")
pytestmark = pytest.mark.cad

from artifact_forge_ng.compiler.solids import compile_part  # noqa: E402
from artifact_forge_ng.form.part import PartForm  # noqa: E402
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeState  # noqa: E402
from artifact_forge_ng.form.style import MOLDED_UTILITY_PART  # noqa: E402
from artifact_forge_ng.validators.topology import box_probe, solid_fraction  # noqa: E402

RAIL_PARAMS = dict(
    module_l=248.0, module_w=248.0, body_h=30.0,
    channel_w=16.0, channel_d=5.0, channel_bottom_r=1.2,
    cassette_l=220.0, cassette_w=220.0,
    seat_depth=14.0, seat_clearance=0.75,
    module_pitch=250.0, corner_r=4.0,
    face_gap=0.4, lw_rib=2.0,
    profile="2020", profile_inset=24.0,
)


def build_rail_form(*, lightweight: bool, magnets: bool = True) -> PartForm:
    st = RecipeState()
    p = dict(RAIL_PARAMS, lightweight=lightweight)
    RECIPE_OPS["water_rail_body"].apply(st, p, "body")
    RECIPE_OPS["lap_outlet_lip"].apply(st, {"lip_len": 4.0, "lip_t": 1.4}, "lap_out")
    RECIPE_OPS["lap_inlet_receiver"].apply(
        st, {"pocket_len": 6.0, "side_clearance": 0.4}, "lap_in")
    RECIPE_OPS["edge_magnet_pockets"].apply(
        st, {"enabled": magnets, "magnet_d": 6.0, "magnet_t": 2.0,
             "fit_clearance": 0.2, "x_offset": 60.0, "z_center": 8.0}, "magnets")
    RECIPE_OPS["profile_seat_slot"].apply(
        st, {"profile": "2020", "clearance": 0.2, "depth": 6.0, "inset": 24.0},
        "profile_slots")
    RECIPE_OPS["tongue_groove_edges"].apply(
        st, {"tongue_w": 6.0, "tongue_h": 4.0, "tongue_len": 3.6,
             "clearance": 0.4, "z0": 4.0, "bottom_margin": 0.4}, "edges")
    return PartForm(
        name=f"rail_{'lw' if lightweight else 'slab'}",
        params={"cassette_l": 220.0, "cassette_w": 220.0},
        frame=st.frame, section=st.section, width=st.width,
        style=MOLDED_UTILITY_PART,
        channels=st.channels, cutboxes=st.cutboxes, bores=st.bores,
        ribs=st.ribs, fields=st.fields, regions=st.regions, datums=st.datums,
    )


@pytest.fixture(scope="module")
def solids():
    light_form = build_rail_form(lightweight=True)
    heavy_form = build_rail_form(lightweight=False)
    light, light_log = compile_part(light_form)
    heavy, heavy_log = compile_part(heavy_form)
    return light_form, light, light_log, heavy_form, heavy, heavy_log


def test_both_variants_compile_clean(solids):
    _, light, light_log, _, heavy, heavy_log = solids
    for log in (light_log, heavy_log):
        assert not getattr(log, "errors", []), getattr(log, "errors", [])
    for geo in (light, heavy):
        assert geo.workplane.val().Volume() > 0


def test_lightweight_pays_its_mass_saving(solids):
    _, light, _, _, heavy, _ = solids
    v_light = light.workplane.val().Volume()
    v_heavy = heavy.workplane.val().Volume()
    saving = 1.0 - v_light / v_heavy
    # the open skeleton removes the window roofs too: target ~45%, with
    # slack for drift — never token (<25%) and never structural (>55%)
    assert 0.25 <= saving <= 0.55, f"saving {saving:.1%}"


def test_lap_lip_is_real_on_the_solid(solids):
    form, light, _, _, _, _ = solids
    f = form.frame
    tip_y = f["lap_lip_tip_y"]  # -128
    floor = f["channel_floor_z_outlet"]  # 11
    # material inside the lip slab past the face...
    lip_probe = box_probe(-8.0, tip_y + 0.4, floor - f["lap_lip_t"] + 0.2,
                          8.0, -124.0 - 0.4, floor - 0.2)
    assert solid_fraction(light.workplane, lip_probe) > 0.95
    # ...and open air directly above the lip top (the water surface) and
    # below the lip underside (the drip gap on the last module)
    above = box_probe(-8.0, tip_y + 0.4, floor + 0.2, 8.0, -124.4, floor + 2.0)
    below = box_probe(-8.0, tip_y + 0.4, 2.0, 8.0, -124.4, floor - f["lap_lip_t"] - 0.2)
    assert solid_fraction(light.workplane, above) < 0.05
    assert solid_fraction(light.workplane, below) < 0.05


def test_lap_receiver_cuts_through(solids):
    form, light, _, _, _, _ = solids
    f = form.frame
    floor = f["channel_floor_z_inlet"]
    # void from below the body up to the floor plane in the pocket footprint
    pocket = box_probe(-8.0, 124.0 - f["lap_pocket_len"] + 0.4, 0.3,
                       8.0, 123.6, floor - 0.3)
    assert solid_fraction(light.workplane, pocket) < 0.05
    # the channel walls above the pocket survive (the paz guides, the
    # opening has no ceiling — modules separate by a vertical lift)
    wall = box_probe(8.6, 124.0 - f["lap_pocket_len"] + 0.4, floor + 1.0,
                     9.2, 123.6, 15.0)
    assert solid_fraction(light.workplane, wall) > 0.9


def test_magnet_pockets_blind_on_the_solid(solids):
    form, light, _, _, _, _ = solids
    # pocket void just inside the +Y face at x=60...
    pocket = box_probe(58.0, 122.0, 7.0, 62.0, 123.8, 9.0)
    assert solid_fraction(light.workplane, pocket) < 0.1
    # ...and solid plastic behind the pocket floor (sealed, never through)
    behind = box_probe(58.0, 118.0, 7.0, 62.0, 121.2, 9.0)
    assert solid_fraction(light.workplane, behind) > 0.9


def test_windows_are_through_skeleton(solids):
    _, light, _, _, heavy, _ = solids
    # a window void runs THROUGH the slab — including the former roof band
    probe = box_probe(20.0, -60.0, 1.0, 40.0, -30.0, 15.5)
    assert solid_fraction(light.workplane, probe) < 0.05
    assert solid_fraction(heavy.workplane, probe) > 0.9
    # the rib grid survives between openings (support for the cassette)
    rib = box_probe(20.0, -65.4, 1.0, 40.0, -63.9, 14.0)
    assert solid_fraction(light.workplane, rib) > 0.85
