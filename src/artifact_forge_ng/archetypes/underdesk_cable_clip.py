"""Flagship form builder: underdesk_cable_clip_v2_molded.

Turns a resolved parameter context into a :class:`PartForm`. Never invents
positions: everything derives from the profile frame, and the same frame is
what every validator measures against.

Part frame: X = cable/width axis (section extruded 0..width), Y = mouth
direction (+Y), Z = vertical (flange underside z=0, slab z in [0, flange_t],
hook below). Screw axis is Z; screws are spaced ALONG X — the flange is a
plate running along the cable axis, wider than the hook, so each screw sits
BESIDE the hook and a screwdriver approaches from below unobstructed. The
countersinks are on the BOTTOM face: the head enters from below, the
desk-side face stays flat.
"""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import BlendDirective, HoleFeature, PartForm, PlateFeature
from ..form.profiles import SideHookParams, build_molded_side_hook_profile
from ..form.regions import Box3, Region
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "molded_side_hook"

#: Extra clearance a hex cell must keep from a screw keepout's boundary.
KEEPOUT_CLEARANCE = 2.0


def _screw_positions(ctx: dict[str, float]) -> list[float]:
    count = int(round(ctx.get("screw_count", 2)))
    spacing = ctx["screw_spacing"]
    if count <= 1:
        return [0.0]
    span = spacing * (count - 1)
    return [-span / 2.0 + i * spacing for i in range(count)]


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = resolve_style(instance, archetype)

    hook = SideHookParams(
        bundle_d=ctx["bundle_d"],
        clearance=ctx["clearance"],
        wall=ctx["wall"],
        mouth_gap=ctx["mouth_gap"],
        upper_lip_len=ctx["upper_lip_len"],
        lower_lip_len=ctx["lower_lip_len"],
        neck_drop=ctx["neck_drop"],
        cavity_roof=resolved.choices.get("cavity_roof", "round"),
    )
    profile, frame = build_molded_side_hook_profile(hook, style)

    width = ctx["flange_w"]  # hook width along X == flange width across Y
    fl, ft = ctx["flange_l"], ctx["flange_t"]
    # The flange runs ALONG the cable axis (X), centered on the hook, so the
    # screws land beside the hook where a driver can actually reach them.
    fx0, fx1 = width / 2.0 - fl / 2.0, width / 2.0 + fl / 2.0
    flange = PlateFeature(
        name="flange",
        x0=fx0,
        y0=-ctx["flange_w"] / 2.0,
        x1=fx1,
        y1=ctx["flange_w"] / 2.0,
        z_bottom=0.0,
        thickness=ft,
        corner_r=style.external_edge_r,
    )

    screw = resolved.choices.get("screw", "M4")
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    xs = [width / 2.0 + offset for offset in _screw_positions(ctx)]
    holes = [
        HoleFeature(
            at=(x, 0.0, flange.z_top),
            screw=screw,
            through=ft,
            countersink_face="bottom",
        )
        for x in xs
    ]

    # Fields (hex perforation etc.) are no longer hand-wired here: the
    # generic modifier kernel applies them to the perforation_safe_zone,
    # deriving keepouts from the protected regions below (incl. neck_weld).
    vc = frame["cavity_center_v"]
    r_i = frame["r_cavity"]
    wall_u = frame["wall_outer_u"]
    band = frame["lip_band"]
    m = frame["mouth_half"]

    regions = [
        Region("flange", RegionRole.MOUNTING_SURFACE,
               Box3(fx0, flange.y0, 0.0, fx1, flange.y1, flange.z_top)),
        Region("screw_zones", RegionRole.FASTENER_KEEPOUT,
               Box3(min(xs) - head_r - KEEPOUT_CLEARANCE, -head_r - KEEPOUT_CLEARANCE, 0.0,
                    max(xs) + head_r + KEEPOUT_CLEARANCE, head_r + KEEPOUT_CLEARANCE, flange.z_top)),
        Region("cable_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -r_i, vc - r_i, width, wall_u, vc + r_i)),
        Region("snap_root", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, wall_u - ctx["wall"], vc - band - 2.0, width, wall_u + 2.0, vc - m)),
        Region("lower_lip", RegionRole.RETAINING_FLEXURE,
               Box3(0.0, wall_u, vc - band - 1.0, width, frame["lower_lip_tip_u"], vc - m + 0.5)),
        # The neck welds into the flange underside — never perforate into
        # it. Declared as a real region so the modifier kernel's generic
        # keepout derivation protects it.
        Region("neck_weld", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, frame["neck_u0"] - 1.0, -2.0, width,
                    frame["neck_u1"] + 1.0, flange.z_top)),
        Region("perforation_safe_zone", RegionRole.AESTHETIC_LIGHTENING,
               Box3(fx0, flange.y0, flange.z_top - ft, fx1, flange.y1, flange.z_top)),
    ]

    blends = [
        BlendDirective(
            zone=Box3(-1.0, frame["neck_u0"] - 2.0, -2.0, width + 1.0, frame["neck_u1"] + 2.0, 2.0),
            radius=style.root_blend_r,
            fallback_ladder=(style.root_blend_r * 0.6, style.root_blend_r * 0.3),
        )
    ]

    datums = {
        "flange_face": {"at": [width / 2.0, 0.0, flange.z_top], "rotate": [0.0, 0.0, 0.0]},
        "mouth_center": {"at": [width / 2.0, wall_u, vc], "rotate": [0.0, 0.0, 0.0]},
    }

    frame = dict(frame)
    frame.update(
        flange_l=fl, flange_t=ft, width=width,
        flange_x0=fx0, flange_x1=fx1,
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
        plates=[flange],
        holes=holes,
        regions=regions,
        blends=blends,
        datums=datums,
    )
