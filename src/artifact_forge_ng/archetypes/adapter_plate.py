"""adapter_plate_v1 — a universal adapter/mounting plate: a rounded-rect
plate carrying up to two fastener hole patterns (line / grid / bolt circle)
and an optional central bore. The plate IS the section (plane XY, extruded
by thickness along Z); patterns expand to HoleFeatures at the IR level so
min-web and outline checks run before any CAD.
"""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import BoreFeature, PartForm
from ..form.patterns import (
    bolt_circle_centers,
    grid_centers,
    holes_from_centers,
    line_centers,
)
from ..form.profiles_plate import rounded_rect_loop
from ..form.regions import Box3, Region
from ..form.section import SectionProfile
from ..form.style import MOLDED_UTILITY_PART, STYLES
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "rounded_plate"

KEEPOUT_CLEARANCE = 2.0


def _pattern_centers(prefix: str, ctx: dict, choices: dict) -> list[tuple[float, float]]:
    kind = choices.get(f"{prefix}_kind", "none")
    center = (ctx.get(f"{prefix}_cx", 0.0), ctx.get(f"{prefix}_cy", 0.0))
    if kind == "none":
        return []
    if kind == "line":
        return line_centers(int(round(ctx[f"{prefix}_count"])), ctx[f"{prefix}_spacing"], center)
    if kind == "grid":
        return grid_centers(
            int(round(ctx[f"{prefix}_nx"])),
            int(round(ctx[f"{prefix}_ny"])),
            ctx[f"{prefix}_spacing"],
            ctx[f"{prefix}_spacing"],
            center,
        )
    return bolt_circle_centers(
        int(round(ctx[f"{prefix}_count"])), ctx[f"{prefix}_bc_d"], center
    )


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    choices = resolved.choices
    style = STYLES.get(archetype.surface_style, MOLDED_UTILITY_PART)

    length, width_, t = ctx["plate_l"], ctx["plate_w"], ctx["thickness"]
    corner_r = ctx["corner_r"]
    u0, v0, u1, v1 = -length / 2, -width_ / 2, length / 2, width_ / 2
    loop = rounded_rect_loop(u0, v0, u1, v1, corner_r)
    profile = SectionProfile(
        name=SECTION_NAME, outer=loop, plane="XY", width_axis="Z"
    )

    holes = []
    zones: list[Region] = []
    for prefix in ("a", "b"):
        centers = _pattern_centers(prefix, ctx, choices)
        if not centers:
            continue
        screw = choices.get(f"{prefix}_screw", "M4")
        cs_face = choices.get(f"{prefix}_cs_face", "top")
        holes.extend(holes_from_centers(centers, t, t, screw, cs_face))
        head_r = screw_spec(screw)["head"] / 2.0
        # Per-hole keepout regions — a bounding box around a bolt CIRCLE
        # would falsely wall off the whole center of the plate.
        for i, (hx, hy) in enumerate(centers):
            zones.append(
                Region(
                    f"pattern_{prefix}_hole_{i}",
                    RegionRole.FASTENER_KEEPOUT,
                    Box3(hx - head_r - KEEPOUT_CLEARANCE, hy - head_r - KEEPOUT_CLEARANCE, 0.0,
                         hx + head_r + KEEPOUT_CLEARANCE, hy + head_r + KEEPOUT_CLEARANCE, t),
                )
            )

    bores = []
    bore_d = ctx.get("bore_d", 0.0)
    if bore_d > 1e-6:
        bores.append(
            BoreFeature("central_bore", "Z", (0.0, 0.0, 0.0), bore_d, (0.0, t))
        )

    regions = [
        Region("plate_face", RegionRole.MOUNTING_SURFACE, Box3(u0, v0, 0.0, u1, v1, t)),
        # Always present (the archetype declares it); with a central bore
        # the bore itself becomes a keepout, so fields flow around it.
        Region(
            "center_zone",
            RegionRole.AESTHETIC_LIGHTENING,
            Box3(-length / 6, -width_ / 6, 0.0, length / 6, width_ / 6, t),
        ),
        *zones,
    ]

    screws = [choices.get("a_screw", "M4"), choices.get("b_screw", "M3")]
    max_head_r = max(screw_spec(s)["head"] for s in screws) / 2.0

    frame = {
        "outline_u0": u0,
        "outline_v0": v0,
        "outline_u1": u1,
        "outline_v1": v1,
        "outline_corner_r": corner_r,
        "screw_head_r": max_head_r,
        "report_plate_l": length,
        "report_plate_w": width_,
        "report_bore_d": bore_d,
    }

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=t,  # extrusion span along Z
        style=style,
        kind="section_extrude",
        holes=holes,
        bores=bores,
        regions=regions,
        datums={"center": {"at": [0.0, 0.0, t], "rotate": [0.0, 0.0, 0.0]}},
    )
