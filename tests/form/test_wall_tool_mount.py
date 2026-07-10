"""Wall Tool Mounts Pack v1, tier-1: wall_ring_mount frame/section/region
math, honest refusals, the tool_d sweep through the full pre-CAD pipeline,
and the nl_edit grounding guarantee (field modifiers land ONLY on the
flange lightening panel)."""

import math
from pathlib import Path

import pytest

from artifact_forge_ng.catalog.loader import (
    compatible_regions,
    load_catalog,
    load_instance,
)
from artifact_forge_ng.core.findings import Status
from artifact_forge_ng.form.recipe_ops import RECIPE_OPS, RecipeError, RecipeState
from artifact_forge_ng.pipeline import pre_cad_from_instance, run_pre_cad
from artifact_forge_ng.product.instance import ProductInstance

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
GRINDER = EXAMPLES / "wall_tool_mount_grinder_65.yaml"

DEFAULTS = {
    "tool_d": 65.0, "clearance": 1.0, "ring_wall": 7.0, "collar_h": 30.0,
    "capture_deg": 220.0, "standoff": 43.0, "flange_w": 78.0,
    "flange_h": 125.0, "flange_t": 7.0, "flange_corner_r": 6.0,
    "rib_t": 3.0, "tool_mass_kg": 2.5, "safety_factor": 2.5,
}


def _mount(**over) -> RecipeState:
    st = RecipeState()
    p = dict(DEFAULTS)
    p.update(over)
    RECIPE_OPS["wall_ring_mount"].apply(st, p, "body")
    return st


def test_frame_math_and_probe_keys():
    st = _mount()
    f = st.frame
    assert f["saddle_r"] == pytest.approx(33.5)
    assert f["d_eff"] == pytest.approx(67.0)
    assert f["r_outer"] == pytest.approx(40.5)
    assert f["saddle_cz"] == pytest.approx(43.0)
    # mouth chord from the capture angle, exact trig
    half_gap = math.radians((360.0 - 220.0) / 2.0)
    assert f["mouth_gap"] == pytest.approx(2 * 33.5 * math.sin(half_gap))
    # fusion half-width from the outer circle vs the flange front face
    drop = 43.0 - 7.0
    assert f["fusion_half_w"] == pytest.approx(math.sqrt(40.5**2 - drop**2))
    assert f["fusion_half_w"] >= 2 * 7.0
    # physically-named probe sizes
    assert f["tool_probe_d"] == pytest.approx(0.85 * 67.0)
    assert f["mouth_probe_d"] == pytest.approx(0.8 * f["mouth_gap"])
    # the honesty moment: mass * g * SF * standoff
    assert f["moment_nmm_est"] == pytest.approx(2.5 * 9.81 * 2.5 * 43.0)
    # hole checks measure against the PLATE outline
    assert (f["outline_u0"], f["outline_u1"]) == (0.0, 125.0)
    assert st.print_orientation == "side_profile"
    assert st.width == pytest.approx(30.0)


def test_regions_and_datums_match_archetype():
    st = _mount()
    names = {r.name for r in st.regions}
    assert {"wall_flange", "saddle_contact", "retaining_lip", "load_rib_zone",
            "flange_lightening", "outer_shell"} <= names
    assert {"tool_axis", "mount_face"} <= set(st.datums)
    # the lightening canvas sits between the collar and the flange top
    zone = next(r for r in st.regions if r.name == "flange_lightening")
    assert zone.box.x0 >= 30.0 + 6.0 - 1e-9
    assert zone.box.x1 <= 125.0 - 4.0 + 1e-9


def test_gusset_ribs_clear_the_cavity_and_weld_both_ends():
    st = _mount()
    assert len(st.ribs) == 2
    for rib in st.ribs:
        b = rib.box
        min_y = min(abs(b.y0), abs(b.y1))
        assert min_y > st.frame["saddle_r"]  # never inside the saddle
        assert b.z0 < st.frame["flange_t"]  # welds into the flange
        assert b.z1 == pytest.approx(st.frame["saddle_cz"])  # reaches the ring


def test_honest_refusals():
    with pytest.raises(RecipeError, match="standoff"):
        _mount(standoff=38.0)  # cavity would cut into the flange
    with pytest.raises(RecipeError, match="retention range"):
        _mount(capture_deg=180.0)
    with pytest.raises(RecipeError, match="does not retain"):
        _mount(capture_deg=200.0, clearance=2.0)  # loose + shallow arc
    with pytest.raises(RecipeError, match="ribs"):
        _mount(flange_w=60.0)  # gussets would stick past the flange
    with pytest.raises(RecipeError, match="reaches the flange|barely"):
        _mount(standoff=70.0, flange_w=120.0)  # ring floats off the flange
    with pytest.raises(RecipeError, match="anchor panel"):
        _mount(collar_h=60.0, flange_h=80.0)


def test_saddle_arc_is_the_declared_tool_circle():
    from artifact_forge_ng.form.section import ArcSeg

    st = _mount()
    assert st.section is not None
    arcs = [s for s in st.section.outer.tagged("saddle_contact")
            if isinstance(s, ArcSeg)]
    assert arcs, "saddle arc missing"
    for a in arcs:
        assert a.radius == pytest.approx(33.5, abs=0.05)
        assert a.center.u == pytest.approx(0.0, abs=1e-6)
        assert a.center.v == pytest.approx(43.0, abs=1e-6)


def _grinder_instance(**param_overrides) -> ProductInstance:
    instance = load_instance(GRINDER)
    if not param_overrides:
        return instance
    data = instance.model_dump(by_alias=True)
    data["params"].update(param_overrides)
    return ProductInstance.model_validate(data)


def test_golden_example_passes_with_the_honesty_warning():
    state = run_pre_cad(GRINDER, None)
    assert not any(f.status is Status.FAIL for f in state.report.findings), [
        f"{f.check}: {f.message}"
        for f in state.report.findings if f.status is Status.FAIL
    ]
    warn = next(f for f in state.report.findings
                if f.check == "form.anchor_wall_strength_unverified")
    assert warn.status is Status.WARN
    # default standoff = flange_t + tool_d/2 + clearance + 2 = 42.5
    assert warn.measured == pytest.approx(2.5 * 9.81 * 3.0 * 42.5)
    assert "external assumptions" in warn.message


def test_anchor_holes_land_centered_above_the_collar():
    state = run_pre_cad(GRINDER, None)
    assert state.form is not None
    holes = state.form.holes
    assert len(holes) == 2
    xs = sorted(h.at[0] for h in holes)
    assert xs[0] == pytest.approx((30.0 + 125.0) / 2 - 73.0 / 2)
    assert xs[1] == pytest.approx((30.0 + 125.0) / 2 + 73.0 / 2)
    assert all(abs(h.at[1]) < 1e-9 for h in holes)
    assert xs[0] > 30.0  # both anchors clear the collar


#: Per-diameter capture/flange: small tools need MORE arc for the same snap
#: interference; big tools need a wider flange for the gussets.
SWEEP = [
    (35.0, 235.0, 78.0),
    (50.0, 225.0, 78.0),
    (65.0, 220.0, 78.0),
    (80.0, 215.0, 105.0),
    (90.0, 212.0, 115.0),
]


@pytest.mark.parametrize("tool_d,capture,flange_w", SWEEP)
def test_tool_d_sweep_full_pre_cad(tool_d, capture, flange_w):
    catalog = load_catalog()
    instance = _grinder_instance(
        tool_d=f"{tool_d:g}mm", capture_deg=capture, flange_w=f"{flange_w:g}mm",
    )
    # let standoff/mount_spacing re-derive for the new diameter
    data = instance.model_dump(by_alias=True)
    data["params"].pop("standoff", None)
    data["id"] = f"sweep_{tool_d:g}"
    instance = ProductInstance.model_validate(data)
    state = pre_cad_from_instance(instance, catalog, True)
    fails = [f"{f.check}: {f.message}" for f in state.report.findings
             if f.status is Status.FAIL]
    assert not fails, fails
    assert any(f.check == "form.anchor_wall_strength_unverified"
               and f.status is Status.WARN for f in state.report.findings)
    # the saddle really is tool_d + 2*clearance
    assert state.form is not None
    assert state.form.frame["d_eff"] == pytest.approx(tool_d + 2.0)


def test_field_modifiers_ground_only_on_the_flange_panel():
    """The nl_edit grounding guarantee, no LLM needed: every field modifier
    is compatible with flange_lightening and NOTHING else."""
    catalog = load_catalog()
    spec = catalog.archetypes["wall_tool_ring_clamp_v1"]
    for mod_id in ("add_voronoi_field", "add_hex_perforation",
                   "add_grid_slot_field"):
        regions = [r.id for r in compatible_regions(spec, catalog.modifiers[mod_id])]
        assert regions == ["flange_lightening"], (mod_id, regions)
    protected = {r.id for r in spec.regions if not r.editable}
    assert {"wall_flange", "saddle_contact", "retaining_lip", "load_rib_zone",
            "outer_shell", "anchors_0", "anchors_1"} <= protected


def _grinder_with_modifier(mod: dict) -> "ProductInstance":
    data = load_instance(GRINDER).model_dump(by_alias=True)
    data["modifiers"] = [mod]
    data["id"] = "wtm_field_symmetry"
    return ProductInstance.model_validate(data)


def test_hex_field_symmetric_about_the_centerline():
    """The printed-part regression: hex lightening on the flange must be
    mirror-symmetric about y=0 — the part, the region and the keepouts all
    are, so an off-center pattern is the generator's fault."""
    catalog = load_catalog()
    instance = _grinder_with_modifier({
        "id": "add_hex_perforation", "target": "flange_lightening",
        "params": {"cell_d": "6mm", "wall_gap": "2mm", "cut_mode": "through"},
    })
    state = pre_cad_from_instance(instance, catalog, True)
    assert state.form is not None
    field = next(f for f in state.form.fields if f.centers)
    have = {(round(x, 6), round(y, 6)) for x, y in field.centers}
    for x, y in field.centers:
        assert (round(x, 6), round(-y, 6)) in have, f"no mirror for {(x, y)}"
    cy = sum(y for _, y in field.centers) / len(field.centers)
    assert cy == pytest.approx(0.0, abs=1e-6)


def test_slot_field_symmetric_about_the_centerline():
    catalog = load_catalog()
    instance = _grinder_with_modifier({
        "id": "add_grid_slot_field", "target": "flange_lightening",
        "params": {"slot_w": "4mm", "web": "3mm"},
    })
    state = pre_cad_from_instance(instance, catalog, True)
    assert state.form is not None
    field = next(f for f in state.form.fields if f.polygons)
    # slots run along x (the window is taller than wide) — their center
    # positions across y... along_u = width >= height; window is x∈[36,121]
    # (u), y∈±35 (v) → along_u, slots stacked in v(y): stack centered on 0
    ys = sorted(
        sum(p[1] for p in poly) / len(poly) for poly in field.polygons
    )
    assert len(ys) >= 3
    mid = (ys[0] + ys[-1]) / 2.0
    assert mid == pytest.approx(0.0, abs=1e-6)
    for a, b in zip(ys, reversed(ys)):
        assert a == pytest.approx(-b, abs=1e-6)


def test_voronoi_cells_respect_anchor_keepouts():
    state = run_pre_cad(GRINDER, None)
    assert state.form is not None
    field = next(f for f in state.form.fields if f.polygons)
    head_r = state.form.frame["screw_head_r"]
    hole_centers = [(h.at[0], h.at[1]) for h in state.form.holes]
    for poly in field.polygons:
        for (px, py) in poly:
            for (hx, hy) in hole_centers:
                assert math.hypot(px - hx, py - hy) > head_r, (
                    "voronoi cell vertex inside an anchor keepout")
