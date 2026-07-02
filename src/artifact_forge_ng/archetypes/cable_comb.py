"""cable_comb_v1 — desk cable comb: N open-topped slots, each a circular
resting cavity behind a snap throat. Adhesive mount (no holes)."""

from __future__ import annotations

from ..form.part import PartForm
from ..form.profiles_comb import CombParams, build_cable_comb_profile
from ..form.regions import Box3, Region
from ..form.style import MOLDED_UTILITY_PART, STYLES
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "cable_comb_bar"


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = STYLES.get(archetype.surface_style, MOLDED_UTILITY_PART)
    params = CombParams(
        cable_d=ctx["cable_d"],
        slot_count=int(round(ctx["slot_count"])),
        clearance=ctx["clearance"],
        wall=ctx["wall"],
        throat_w=ctx["throat_w"],
        pitch=ctx["pitch"],
        base_h=ctx["base_h"],
        end_margin=ctx["end_margin"],
    )
    profile, frame = build_cable_comb_profile(params, style)
    depth = ctx["depth"]

    bar_l, total_h = frame["bar_l"], frame["total_h"]
    cv, r = frame["cavity_cv"], frame["cavity_r"]
    regions = [
        # Section plane XZ, width Y: (u, v, w) -> (x, y, z) = (u, w, v).
        Region("base_bar", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, 0.0, 0.0, bar_l, depth, frame["base_h"])),
        Region("cable_slots", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, 0.0, cv - r, bar_l, depth, total_h)),
        Region("teeth", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, 0.0, frame["base_h"], bar_l, depth, total_h)),
    ]

    frame = dict(frame)
    frame["width"] = depth

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=depth,
        style=style,
        regions=regions,
        datums={
            "first_slot": {
                "at": [frame["slot_cx_0"], depth / 2.0, cv],
                "rotate": [0.0, 0.0, 0.0],
            }
        },
    )
