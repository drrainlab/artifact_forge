"""Bio-4M acceptance: the demo plate in implicit-skin mode produces a
watertight, byte-deterministic, organically-shaped STL whose analytic SDF
honors the IR — with the honest negatives (revolve refusal, nothing to
skin, wrong surface, sabotaged assembly order)."""

from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
cq = pytest.importorskip("cadquery")
pytest.importorskip("skimage")
pytestmark = pytest.mark.cad

from artifact_forge_ng.catalog.loader import load_catalog, load_instance  # noqa: E402
from artifact_forge_ng.compiler.implicit.from_form import recipe_from_form  # noqa: E402
from artifact_forge_ng.compiler.implicit.recipe import (  # noqa: E402
    Blob,
    CanvasPad,
    CylinderCut,
    FrustumCutZ,
)
from artifact_forge_ng.compiler.implicit.sdf import smin  # noqa: E402
from artifact_forge_ng.compiler.implicit.skin import (  # noqa: E402
    _probe_finding,
    export_implicit_skin,
)
from artifact_forge_ng.compiler.implicit.stl import read_binary_stl  # noqa: E402
from artifact_forge_ng.compiler.pipeline import run_build_from_state  # noqa: E402
from artifact_forge_ng.core.fasteners import hole_cut_dims  # noqa: E402
from artifact_forge_ng.core.findings import Level, Status  # noqa: E402
from artifact_forge_ng.pipeline import (  # noqa: E402
    PipelineFailure,
    pre_cad_from_instance,
    run_pre_cad,
)

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"
IMPLICIT = EXAMPLES / "biomorphic_exoskeleton_demo_plate_implicit.yaml"
REVOLVE = EXAMPLES / "socket_cup_e27.yaml"

BIO_FEATURES = {"biomorphic_exoskeleton", "organic_windows"}
FUNCTIONAL_LEVELS = {Level.FORM, Level.TOPOLOGY, Level.REGION}


@pytest.fixture(scope="module")
def implicit_build(tmp_path_factory):
    target = tmp_path_factory.mktemp("bio4m") / "demo"
    state = run_pre_cad(IMPLICIT, None)
    out, geometry = run_build_from_state(state, target)
    return state, out, geometry, target


def _stl_verts(path: Path) -> np.ndarray:
    _, tris = read_binary_stl(path)
    return tris.reshape(-1, 3).astype(np.float64)


# ---------------------------------------------------------------------------
# the pre-flight gate
# ---------------------------------------------------------------------------


def test_strict_pass_and_implicit_source(implicit_build):
    state, out, _, target = implicit_build
    assert out["status"] == "pass"
    assert state.report.critical_failures() == []
    assert out["exports"]["stl_source"] == "implicit"
    stl = target / "part.stl"
    assert stl.exists()
    assert 8_000_000 < stl.stat().st_size < 40_000_000  # expected 15-25MB class
    assert BIO_FEATURES <= set(out["honesty_report"]["built_features"])


def test_watertight_and_richer_than_brep(implicit_build):
    state, out, geometry, _ = implicit_build
    assert state.report.passed("manufacturing.mesh_watertight")
    skin = out["exports"]["skin"]
    assert skin["triangles"] > 50_000
    _, brep_tris = geometry.mesh(0.2)
    assert skin["triangles"] > len(brep_tris)  # mesh detail beats tessellation
    assert skin["voxels"] <= 16_000_000


def test_analytic_probe_findings_pass(implicit_build):
    state, _, _, _ = implicit_build
    assert state.report.passed("manufacturing.implicit_skin_fidelity")
    assert state.report.passed("manufacturing.boss_growth_preserves_fastener_access")
    assert state.report.passed("manufacturing.skin_assembly_clearance")
    assert state.report.passed("manufacturing.mesh_min_feature")


def test_visual_metrics(implicit_build):
    state, _, _, _ = implicit_build
    assert state.report.passed("quality.rectangularity_reduced")
    rect = [f for f in state.report.findings
            if f.check == "quality.rectangularity_reduced"][0]
    assert rect.measured is not None and rect.measured < 0.55
    assert state.report.passed("quality.window_shadow_present")


def test_skin_stands_proud_of_the_plate(implicit_build):
    state, _, _, target = implicit_build
    verts = _stl_verts(target / "part.stl")
    thickness = state.form.params["thickness"]
    # grown bosses + capsules stand well proud of the 6mm plate top
    assert float(verts[:, 2].max()) > thickness + 4.0
    # keep_in: nothing below the mounting face
    assert float(verts[:, 2].min()) >= -1e-3


def test_bolt_exactness_on_the_mesh(implicit_build):
    state, _, _, target = implicit_build
    verts = _stl_verts(target / "part.stl")
    dims = hole_cut_dims("m4", state.form.params["thickness"])
    bore_r = dims["bore_d"] / 2.0
    for hole in state.form.holes:
        x, y, _ = hole.at
        # below the countersink cone, inside the plate
        band = (verts[:, 2] > 0.8) & (verts[:, 2] < 3.8)
        radial = np.hypot(verts[band, 0] - x, verts[band, 1] - y)
        near = radial < bore_r + 0.3
        assert near.sum() > 50  # the bore wall exists in the mesh
        assert float(radial[near].min()) > bore_r - 0.12  # nothing narrows it


def test_windows_open_on_the_mesh(implicit_build):
    state, _, _, target = implicit_build
    verts = _stl_verts(target / "part.stl")
    ir = state.form.exoskeleton
    poly = ir.windows[0]
    ca = sum(p[0] for p in poly) / len(poly)
    cb = sum(p[1] for p in poly) / len(poly)
    cx, cy, _ = ir.local_to_world(ca, cb, 0.0)
    mid = (verts[:, 2] > 2.0) & (verts[:, 2] < 4.0)
    radial = np.hypot(verts[mid, 0] - cx, verts[mid, 1] - cy)
    assert float(radial.min()) > 0.4  # the window column is void material


def test_engine_gap_for_step(implicit_build):
    _, out, _, target = implicit_build
    gaps = out["honesty_report"]["engine_gaps"]
    assert any(
        "part.step is the simplified BRep reference" in g.get("suggestion", "")
        for g in gaps
    )
    assert (target / "part.step").exists()  # the BRep reference still ships


def test_recess_honesty_meta(implicit_build):
    _, out, _, _ = implicit_build
    ow = out["exports"]["skin"]["organic_windows"]
    assert ow["mode"] == "through"
    assert ow["through_cuts"] is True  # legal on a plate — and said out loud
    assert ow["reason"]


def test_deterministic_stl_bytes(implicit_build, tmp_path):
    _, _, _, target = implicit_build
    state = run_pre_cad(IMPLICIT, None)  # a completely fresh IR run
    path, _, _ = export_implicit_skin(state.form, tmp_path / "again.stl")
    assert path.read_bytes() == (target / "part.stl").read_bytes()


def test_skin_off_vs_on_same_functional_pass_set(implicit_build, tmp_path):
    """Skin ON must not move a single functional (form/topology/region)
    verdict: the BRep twin is the same product."""
    state_on, out_on, _, _ = implicit_build
    inst = load_instance(IMPLICIT)
    style_off = {k: v for k, v in inst.style.items()
                 if not (k == "skin" or k.startswith("skin_"))}
    state_off = pre_cad_from_instance(
        inst.model_copy(update={"style": style_off}), load_catalog(), True
    )
    out_off, _ = run_build_from_state(state_off, tmp_path / "off")
    assert out_off["exports"]["stl_source"] == "brep"
    assert out_off["status"] == "pass" and out_on["status"] == "pass"

    def functional_passes(state):
        checks = {
            f.check for f in state.report.findings if f.level in FUNCTIONAL_LEVELS
        }
        return {c for c in checks if state.report.passed(c)}

    assert functional_passes(state_on) == functional_passes(state_off)


# ---------------------------------------------------------------------------
# recipe contents
# ---------------------------------------------------------------------------


def test_recipe_from_form_contents():
    state = run_pre_cad(IMPLICIT, None)
    recipe, probes, meta = recipe_from_form(state.form)
    ir = state.form.exoskeleton
    assert len(recipe.skin_capsules) == len(ir.graph.edges)
    assert 0 < len(recipe.skin_spheres) <= len(ir.graph.nodes)
    assert len(recipe.window_prisms) == len(ir.windows) > 0

    # hard cuts: per M4 top-seat hole — exact bore + countersink frustum +
    # driver-access cylinder (fastener access is a hard cut, by law)
    assert len(state.form.holes) == 2
    cyls = [c for c in recipe.hard_cuts if isinstance(c, CylinderCut)]
    frusta = [c for c in recipe.hard_cuts if isinstance(c, FrustumCutZ)]
    assert len(frusta) == 2 and len(cyls) == 4
    dims = hole_cut_dims("m4", state.form.params["thickness"])
    radii = sorted({round(c.r, 3) for c in cyls})
    assert round(dims["bore_d"] / 2.0, 3) in radii
    assert round(dims["seat_r"], 3) in radii

    # organic_base_shell: canvas pad first, then grown bosses (+ noise)
    assert isinstance(recipe.shell[0], CanvasPad)
    assert sum(isinstance(t, Blob) for t in recipe.shell) >= 2
    assert recipe.canvas is not None
    assert len(recipe.keep_in) == 1  # the mounting-plane clip

    # k-knobs derive from organicity 0.6
    assert recipe.k_blend == pytest.approx(1.2 + 2.5 * 0.6)
    assert recipe.k_weld == pytest.approx(2.0 + 2.5 * 0.6)
    assert recipe.k_lip == pytest.approx(1.0 + 1.5 * 0.6)

    assert meta["organic_windows"]["through_cuts"] is True
    assert probes.fidelity and probes.boss and probes.clearance


# ---------------------------------------------------------------------------
# negatives — honesty under refusal
# ---------------------------------------------------------------------------


def test_revolve_body_refused_loudly(tmp_path):
    inst = load_instance(REVOLVE)
    style = dict(inst.style)
    style.update({"surface": "biomechanical_exoskeleton", "skin": "implicit"})
    state = pre_cad_from_instance(
        inst.model_copy(update={"style": style}), load_catalog(), False
    )
    with pytest.raises(PipelineFailure) as exc:
        run_build_from_state(state, tmp_path / "revolve")
    assert "profile_revolve" in str(exc.value)  # the reason is NAMED
    assert not (tmp_path / "revolve" / "part.stl").exists()  # no silent BRep


def test_skin_without_exoskeleton_is_nothing_to_skin(tmp_path):
    inst = load_instance(IMPLICIT).model_copy(update={
        "modifiers": [],
        "requested_features": ["mounting_plate_body", "hole_pattern"],
    })
    state = pre_cad_from_instance(inst, load_catalog(), True)
    with pytest.raises(PipelineFailure) as exc:
        run_build_from_state(state, tmp_path / "noskel")
    assert "nothing to skin" in str(exc.value)


def test_skin_on_non_biomech_surface_is_value_error():
    inst = load_instance(IMPLICIT)
    style = dict(inst.style)
    style["surface"] = "molded_utility_part"
    with pytest.raises(ValueError, match="biomechanical_exoskeleton"):
        pre_cad_from_instance(
            inst.model_copy(update={"style": style}), load_catalog(), True
        )


def test_missing_skimage_is_a_loud_failure(tmp_path, monkeypatch):
    """No marching cubes -> no export -> ImplicitSkinError (the pipeline
    wraps it into PipelineFailure) — never a silent BRep STL."""
    import sys

    from artifact_forge_ng.compiler.implicit.skin import ImplicitSkinError

    state = run_pre_cad(IMPLICIT, None)
    monkeypatch.setitem(sys.modules, "skimage", None)
    with pytest.raises(ImplicitSkinError, match="scikit-image"):
        export_implicit_skin(state.form, tmp_path / "x.stl")


def test_sabotaged_assembly_order_fails_the_probes():
    """Hard cuts applied BEFORE the organic growth (the forbidden order):
    the grown boss re-fills the bolt bore, and the analytic probes catch it
    without ever meshing."""
    state = run_pre_cad(IMPLICIT, None)
    recipe, probes, _ = recipe_from_form(state.form)

    class SabotagedOrder:
        def evaluate(self, P):
            P = np.ascontiguousarray(P, dtype=np.float64)
            d = recipe.body_sdf(P)
            d = recipe.apply_hard_cuts(d, P)  # WRONG: cuts before growth
            shell = recipe.shell_sdf(P)
            if shell is not None:
                d = smin(d, shell, recipe.k_weld)
            skin = recipe.skin_sdf(P)
            if skin is not None:
                d = smin(d, skin, recipe.k_weld)
            d = recipe.apply_window_lips(d, P)
            return recipe.apply_keep_in(d, P)

    good = _probe_finding("manufacturing.boss_growth_preserves_fastener_access",
                          recipe, probes.boss, "ok")
    assert good.status is Status.PASS
    bad = _probe_finding("manufacturing.boss_growth_preserves_fastener_access",
                         SabotagedOrder(), probes.boss, "ok")
    assert bad.status is Status.FAIL and bad.critical
    assert "expected void" in bad.message
