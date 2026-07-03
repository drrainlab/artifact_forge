"""shelf_bracket_v1 — wall plate + tapered lofted arm + gusset webs
(wave R4: strength). Part frame: the WALL is the z=0 plane — the plate lies
in XY with countersunk screws along Z (driver approaches from +Z, the free
side), and the arm lofts straight out of the wall along +Z, tapering
root -> tip so the standing print is self-supporting. Gusset webs (box
ribs, honest v1 of a triangular gusset) tie the arm root into the plate on
both bending sides.
"""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import HoleFeature, LoftFeature, PartForm, RibFeature
from ..form.profiles_plate import rounded_rect_loop
from ..form.regions import Box3, Region
from ..form.section import SectionProfile
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "plate_loft_arm"

KEEPOUT_CLEARANCE = 2.0


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = resolve_style(instance, archetype)

    pl, pw, pt = ctx["plate_l"], ctx["plate_w"], ctx["plate_t"]
    u0, v0, u1, v1 = -pw / 2.0, -pl / 2.0, pw / 2.0, pl / 2.0
    profile = SectionProfile(
        name=SECTION_NAME,
        outer=rounded_rect_loop(u0, v0, u1, v1, ctx["corner_r"]),
        plane="XY",
        width_axis="Z",
    )

    arm_len = ctx["arm_len"]
    root_l, root_w = ctx["arm_root_l"], ctx["arm_root_w"]
    tip_l, tip_w = ctx["arm_tip_l"], ctx["arm_tip_w"]
    arm = LoftFeature(
        name="arm",
        base_center=(0.0, 0.0),
        z0=pt - 0.6,  # weld overlap into the plate
        length=arm_len + 0.6,
        root=(root_l, root_w),
        tip=(tip_l, tip_w),
    )

    g_h, g_t = ctx["gusset_h"], ctx["gusset_t"]
    g_len = ctx["gusset_len"]
    # Web gussets: thin (g_t) vertical webs on both bending sides, welded
    # into plate AND arm root by the overlap rule.
    gussets = [
        RibFeature(
            name=f"gusset_{side}",
            box=Box3(-g_t / 2.0, y0, pt - 0.6, g_t / 2.0, y1, pt + g_h),
        )
        for side, (y0, y1) in (
            ("pos", (root_w / 2.0 - 0.6, root_w / 2.0 + g_len)),
            ("neg", (-root_w / 2.0 - g_len, -root_w / 2.0 + 0.6)),
        )
    ]

    screw = resolved.choices.get("screw", "M5")
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    spacing = ctx["screw_spacing"]
    ys = [-spacing / 2.0, spacing / 2.0]
    holes = [
        HoleFeature(at=(0.0, y, pt), screw=screw, through=pt,
                    countersink_face="top")
        for y in ys
    ]

    regions = [
        Region("plate", RegionRole.MOUNTING_SURFACE,
               Box3(u0, v0, 0.0, u1, v1, pt)),
        Region("arm_root", RegionRole.HIGH_STRESS_REGION,
               Box3(-root_l / 2.0 - 2.0, -root_w / 2.0 - g_len - 1.0, 0.0,
                    root_l / 2.0 + 2.0, root_w / 2.0 + g_len + 1.0,
                    pt + g_h + 2.0)),
    ] + [
        Region(f"screw_keep_{i}", RegionRole.FASTENER_KEEPOUT,
               Box3(-head_r - KEEPOUT_CLEARANCE, y - head_r - KEEPOUT_CLEARANCE,
                    0.0,
                    head_r + KEEPOUT_CLEARANCE, y + head_r + KEEPOUT_CLEARANCE,
                    pt))
        for i, y in enumerate(ys)
    ]

    frame = {
        "outline_u0": u0, "outline_v0": v0, "outline_u1": u1, "outline_v1": v1,
        "outline_corner_r": ctx["corner_r"],
        "arm_tip_z": pt - 0.6 + arm_len + 0.6,
        "arm_root_w": root_w,
        "screw_head_r": head_r,
        "screw_clear_d": spec["clear"],
    }
    for i, y in enumerate(ys):
        frame[f"screw_y_{i}"] = y

    datums = {
        "wall_face": {"at": [0.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]},
        "arm_tip": {"at": [0.0, 0.0, frame["arm_tip_z"]], "rotate": [0.0, 0.0, 0.0]},
    }

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=pt,
        style=style,
        holes=holes,
        ribs=gussets,
        lofts=[arm],
        regions=regions,
        datums=datums,
    )
