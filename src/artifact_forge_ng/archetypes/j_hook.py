"""The J-hook family builder — wall_hook_v1 and headphone_hook_v1 are two
YAML archetypes over this one builder (FORM_BUILDERS is keyed by section
name). Plate + screws follow the flagship layout: plate along X, screws
beside the hook, countersinks on the bottom face."""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import BlendDirective, HoleFeature, PartForm, PlateFeature
from ..form.profiles_jhook import JHookParams, build_j_hook_profile
from ..form.regions import Box3, Region
from ..form.style import MOLDED_UTILITY_PART, STYLES
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "j_hook"

KEEPOUT_CLEARANCE = 2.0


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = STYLES.get(archetype.surface_style, MOLDED_UTILITY_PART)

    hook = JHookParams(
        bay_w=ctx["bay_w"],
        bay_depth=ctx["bay_depth"],
        wall=ctx["wall"],
        lip_h=ctx["lip_h"],
    )
    profile, frame = build_j_hook_profile(hook, style)

    width = ctx["band_w"]
    pl, pw, pt = ctx["plate_l"], ctx["plate_w"], ctx["plate_t"]
    fx0, fx1 = width / 2.0 - pl / 2.0, width / 2.0 + pl / 2.0
    # Plate straddles the hook's u-extent: spine at u=0, lip at lip_outer_u.
    py0 = -pw / 2.0
    py1 = pw / 2.0
    plate = PlateFeature(
        name="plate",
        x0=fx0,
        y0=py0,
        x1=fx1,
        y1=py1,
        z_bottom=0.0,
        thickness=pt,
        corner_r=style.external_edge_r,
    )

    screw = resolved.choices.get("screw", "M4")
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    count = int(round(ctx.get("screw_count", 2)))
    spacing = ctx["screw_spacing"]
    span = spacing * (count - 1)
    xs = [width / 2.0 - span / 2.0 + i * spacing for i in range(count)]
    holes = [
        HoleFeature(at=(x, 0.0, plate.z_top), screw=screw, through=pt,
                    countersink_face="bottom")
        for x in xs
    ]

    c_v = frame["bay_center_v"]
    regions = [
        Region("plate", RegionRole.MOUNTING_SURFACE,
               Box3(fx0, py0, 0.0, fx1, py1, plate.z_top)),
        Region("screw_zones", RegionRole.FASTENER_KEEPOUT,
               Box3(min(xs) - head_r - KEEPOUT_CLEARANCE, -head_r - KEEPOUT_CLEARANCE, 0.0,
                    max(xs) + head_r + KEEPOUT_CLEARANCE, head_r + KEEPOUT_CLEARANCE, plate.z_top)),
        Region("bay_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, ctx["wall"], c_v - frame["r_in"], width,
                    frame["lip_inner_u"], frame["lip_tip_v"])),
        Region("hook_root", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, 0.0, -2.0, width, ctx["wall"] + 1.0, plate.z_top)),
        Region("tip_lip", RegionRole.RETAINING_FLEXURE,
               Box3(0.0, frame["lip_inner_u"] - 0.5, c_v, width,
                    frame["lip_outer_u"] + 0.5, frame["lip_tip_v"] + 0.5)),
    ]

    blends = [
        BlendDirective(
            zone=Box3(-1.0, -1.0, -2.0, width + 1.0, ctx["wall"] + 2.0, 2.0),
            radius=style.root_blend_r,
            fallback_ladder=(style.root_blend_r * 0.6, style.root_blend_r * 0.3),
        )
    ]

    frame = dict(frame)
    frame.update(
        width=width, flange_x0=fx0, flange_x1=fx1,
        screw_head_r=head_r, screw_clear_d=spec["clear"],
    )
    for i, x in enumerate(xs):
        frame[f"screw_x_{i}"] = x

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=width,
        style=style,
        plates=[plate],
        holes=holes,
        regions=regions,
        blends=blends,
        datums={
            "bay_center": {
                "at": [width / 2.0, frame["bay_center_u"], c_v],
                "rotate": [0.0, 0.0, 0.0],
            }
        },
    )
