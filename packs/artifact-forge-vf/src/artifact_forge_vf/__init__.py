"""Artifact Forge — Vertical Farm Pack (private, pro tier).

Entry point for the ``artifact_forge_ng.packs`` group: :func:`register`
declares the VF check vocabulary, self-registers the VF recipe ops /
checks / joints / probes, contributes the VF catalog data (features +
archetypes) and plugs the carrier findings and water/frame reports into
the assembly and compiler pipelines.
"""
from __future__ import annotations

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_PACK_YAML = Path(__file__).resolve().parents[2] / "pack.yaml"

# The check vocabulary is declared the moment ANY pack module is imported —
# the impl modules register probes against these names at import time.
from .declarations import declare as _declare  # noqa: E402

_declare()


def register(ctx) -> None:

    # 2. Self-registering implementation modules (ops, form checks, joints,
    #    IR-free). CAD-tier probes register lazily below.
    from . import checks, joints, ops  # noqa: F401

    # 3. CAD-tier probes (topology + manufacturing) need cadquery; keep the
    #    pack importable without the cad extra, exactly like core.
    try:
        from . import manufacturing, topology  # noqa: F401
    except ModuleNotFoundError:
        pass

    # 4. Catalog data: VF features + archetypes.
    ctx.add_pack_manifest(_PACK_YAML)
    ctx.add_data_dir(_DATA_DIR)

    # 5. Pipeline hooks: carrier/row findings + report sections.
    from .carrier import carrier_findings
    from .frame_report import build_frame_report
    from .water_report import build_views, build_water_report

    ctx.add_assembly_finding_hook(carrier_findings)

    def _report_sections(*, asm, states, joint_findings, poses):
        yield ("frame", "frame_report.yaml",
               build_frame_report(asm, states, joint_findings))
        yield ("water", "water_report.yaml",
               build_water_report(states, joint_findings, asm=asm,
                                  poses=poses))
        yield ("views", None, build_views(asm, states, poses))

    ctx.add_assembly_report_hook(_report_sections)

    def _part_water(state):
        if "channel_slope_deg" not in state.form.frame:
            return None
        water = build_water_report({"part": state})
        return ("water", water) if water is not None else None

    ctx.add_part_report_hook(_part_water)
