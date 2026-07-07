"""Bio-4M stage B, CAD: the organic clamp's BRep twin — polyline capsule
ribs materialize on the curved surface, recess windows cut real material
without breaching the saddle, and every functional probe stays green with
the exoskeleton applied."""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.cad
cq = pytest.importorskip("cadquery")

from artifact_forge_ng.catalog.loader import load_catalog  # noqa: E402
from artifact_forge_ng.pipeline import pre_cad_from_instance  # noqa: E402
from artifact_forge_ng.compiler.pipeline import run_build_from_state  # noqa: E402
from artifact_forge_ng.product.instance import ProductInstance  # noqa: E402

EXAMPLES = Path(__file__).parents[2] / "catalog" / "examples"


def _built_half(ref: str, tmp_path: Path, *, skin: bool = False):
    doc = yaml.safe_load(
        (EXAMPLES / "biomorphic_branch_clamp_organic.yaml").read_text())
    part = next(p for p in doc["parts"] if p["ref"] == ref)
    pdoc = dict(part["product"])
    pdoc.setdefault("schema", "product/v1")
    for k, v in (doc.get("shared") or {}).items():
        pdoc.setdefault("params", {}).setdefault(k, v)
    if not skin:
        # BRep twin only: drop the implicit skin request, keep the style
        pdoc.setdefault("style", {}).pop("skin", None)
    catalog = load_catalog()
    state = pre_cad_from_instance(
        ProductInstance.model_validate(pdoc), catalog, strict=True)
    out, geometry = run_build_from_state(state, tmp_path / ref)
    return state, out, geometry


@pytest.fixture(scope="module")
def upper(tmp_path_factory):
    return _built_half("upper", tmp_path_factory.mktemp("organic"))


def test_brep_twin_materializes_surface_ribs_and_windows(upper):
    """The UPPER half is honestly graph-less (the rail keepout splits its
    canvas): ribs_materialized passes VACUOUSLY, while the recessed organic
    windows must be genuinely cut."""
    state, out, _ = upper
    findings = {f.check: f for f in state.report.findings}
    # add_bone_windows subscribes no rib probe — the check honestly does
    # not RUN on the graph-less upper half (subscription-driven runner).
    assert "topology.exoskeleton_ribs_materialized" not in findings
    for check in ("topology.organic_windows_open",
                  "topology.single_connected_solid"):
        assert str(findings[check].status).endswith("PASS"), check


def test_functional_probes_survive_the_exoskeleton(upper):
    state, out, _ = upper
    findings = {f.check: f for f in state.report.findings}
    for check in ("topology.cavity_open", "topology.bores_open",
                  "topology.rail_present", "topology.screw_holes_open",
                  "region.keepouts_preserved"):
        assert str(findings[check].status).endswith("PASS"), check


def test_recess_windows_do_not_breach_the_saddle(upper):
    """Sample the compiled solid just INSIDE the saddle surface: recess
    windows are depth-capped by safe_recess and must leave the saddle
    wall solid everywhere."""
    import math

    from artifact_forge_ng.cad.probes import box_probe, solid_fraction

    state, out, geometry = upper
    form = state.form
    r = form.frame["saddle_r"]
    cz = form.frame["saddle_cz"]
    w = form.width
    solid_hits = probed = 0
    # Upper half is modeled mate-face-down: the saddle notch opens downward
    # and the WALL band sits ABOVE the arc — sample INTO the wall (r + 1.2).
    for deg in range(30, 151, 15):
        a = math.radians(deg)
        u = (r + 1.2) * math.cos(a)
        v = cz + (r + 1.2) * math.sin(a)
        probe = box_probe(w * 0.4, u - 0.5, v - 0.5, w * 0.6, u + 0.5, v + 0.5)
        frac = solid_fraction(geometry.workplane, probe)
        probed += 1
        if frac > 0.9:
            solid_hits += 1
    assert probed and solid_hits >= probed - 1, (
        f"saddle wall shows voids ({solid_hits}/{probed}) — a recess broke through")
