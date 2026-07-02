"""lamp_bracket_v1 — ceiling/under-shelf lamp bracket: mounting plate,
cantilever arm with optional root gusset, and a continuous wiring channel
(vertical entry through the plate near the root, horizontal run to the arm
tip) built from two intersecting BoreFeatures and verified along the full
L-path. The arm tip carries the datum a lamp_socket_cup mounts onto."""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import BlendDirective, BoreFeature, HoleFeature, PartForm, PlateFeature
from ..form.profiles_bracket import BracketArmParams, build_bracket_arm_profile
from ..form.regions import Box3, Region
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "bracket_arm_side"

KEEPOUT_CLEARANCE = 2.0


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = resolve_style(instance, archetype)

    arm = BracketArmParams(
        arm_len=ctx["arm_len"],
        arm_h=ctx["arm_h"],
        plate_w=ctx["plate_w"],
        gusset=ctx.get("gusset", 1.0) >= 0.5,
        gusset_len=ctx["gusset_len"],
        gusset_drop=ctx["gusset_drop"],
    )
    profile, frame = build_bracket_arm_profile(arm, style)

    width = ctx["arm_w"]  # arm extrusion along X
    pl, pw, pt = ctx["plate_l"], ctx["plate_w"], ctx["plate_t"]
    fx0, fx1 = width / 2.0 - pl / 2.0, width / 2.0 + pl / 2.0
    plate = PlateFeature(
        name="plate",
        x0=fx0,
        y0=-pw / 2.0,
        x1=fx1,
        y1=pw / 2.0,
        z_bottom=0.0,
        thickness=pt,
        corner_r=style.external_edge_r,
    )

    screw = resolved.choices.get("screw", "M4")
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    count = int(round(ctx["screw_count"]))
    spacing = ctx["screw_spacing"]
    span = spacing * (count - 1)
    xs = [width / 2.0 - span / 2.0 + i * spacing for i in range(count)]
    holes = [
        HoleFeature(at=(x, 0.0, plate.z_top), screw=screw, through=pt,
                    countersink_face="bottom")
        for x in xs
    ]

    # -- wiring channel: L of two bores, one frame-declared probe path -----
    channel_d = ctx["channel_d"]
    z_c = frame["arm_center_v"]
    entry_u = frame["root_u"] + max(channel_d, 6.0)
    bores = [
        BoreFeature(
            "channel_entry", axis="Z",
            center=(width / 2.0, entry_u, 0.0),
            d=channel_d, span=(z_c, pt),
        ),
        BoreFeature(
            "channel_run", axis="Y",
            center=(width / 2.0, 0.0, z_c),
            d=channel_d, span=(entry_u, ctx["arm_len"]),
        ),
    ]

    regions = [
        Region("plate", RegionRole.MOUNTING_SURFACE,
               Box3(fx0, -pw / 2.0, 0.0, fx1, pw / 2.0, plate.z_top)),
        Region("screw_zones", RegionRole.FASTENER_KEEPOUT,
               Box3(min(xs) - head_r - KEEPOUT_CLEARANCE, -head_r - KEEPOUT_CLEARANCE, 0.0,
                    max(xs) + head_r + KEEPOUT_CLEARANCE, head_r + KEEPOUT_CLEARANCE, plate.z_top)),
        # High-stress root zone: bottom fiber + gusset. Deliberately stops
        # BELOW the channel centerline band — the wiring channel is an
        # intended cut, keepouts are never declared over intended cuts.
        Region("arm_root", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, frame["root_u"] - 1.0, frame["bot_v"] - frame["gusset_drop"] - 1.0,
                    width, frame["gusset_len"] + 2.0, z_c - channel_d / 2.0 - 0.5)),
        Region("arm_tip_face", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, ctx["arm_len"] - 2.0, frame["bot_v"], width, ctx["arm_len"] + 0.5, 0.0)),
        Region("channel_zone", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(width / 2.0 - channel_d, frame["root_u"], z_c - channel_d,
                    width / 2.0 + channel_d, ctx["arm_len"] + 0.5, z_c + channel_d)),
    ]

    blends = [
        BlendDirective(
            zone=Box3(-1.0, frame["root_u"] - 2.0, -2.0,
                      width + 1.0, frame["weld_pad_end"] + 2.0, 2.0),
            radius=style.root_blend_r,
            fallback_ladder=(style.root_blend_r * 0.6, style.root_blend_r * 0.3),
        )
    ]

    frame = dict(frame)
    frame.update(
        width=width, flange_t=pt, flange_x0=fx0, flange_x1=fx1,
        screw_head_r=head_r, screw_clear_d=spec["clear"],
        channel_x=width / 2.0, channel_entry_u=entry_u,
        channel_z=z_c, channel_exit_u=ctx["arm_len"],
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
        bores=bores,
        regions=regions,
        blends=blends,
        datums={
            "arm_tip": {
                "at": [width / 2.0, ctx["arm_len"], frame["arm_center_v"]],
                "rotate": [0.0, 0.0, 0.0],
            }
        },
    )
