"""Sideprint variant builder: underdesk_cable_clip_v3_sideprint.

Same hook, different manufacturing identity. The v2 clip carries its screws
on a welded flange plate BESIDE the hook (along X), which makes the part a
non-constant solid: printed flange-down the lips cantilever, printed hook-
down the flange is a table on a post — either way the slicer wants supports.

Here the mounting flange is a TONGUE inside the extruded profile, running
behind the hook (−Y), with the screws spaced ALONG the tongue. Every feature
lives in one section, so the part is a true constant-section extrusion and
``print_orientation = side_profile`` bakes the support-free orientation into
the export: profile on the bed, extrusion axis up, every layer identical.

Part frame (same as v2): X = cable/width axis, Y = mouth direction (+Y),
Z = vertical; mount face at z = tongue_t, hook below z = 0. Screw axis is Z;
countersinks on the BOTTOM face (head enters from below, desk face flat).
"""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import HoleFeature, PartForm
from ..form.profiles import SideHookParams, build_tongue_side_hook_profile
from ..form.regions import Box3, Region
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "tongue_side_hook"

#: Clear tongue length kept around each screw center: head seat plus driver
#: wobble on both sides of the hole.
SCREW_MARGIN = 4.0


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
    )

    screw = resolved.choices.get("screw", "M4")
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    count = int(round(ctx.get("screw_count", 2)))
    spacing = ctx["screw_spacing"]
    # First screw sits clear of the hook's back edge; the rest march down
    # the tongue. The tongue then auto-sizes to cover the last screw — the
    # screws define the tongue, never the other way around.
    setback = head_r + SCREW_MARGIN
    first_y = -(hook.r_outer + setback)
    ys = [first_y - i * spacing for i in range(count)]
    tongue_u0 = ys[-1] - setback
    tongue_t = ctx["tongue_t"]

    profile, frame = build_tongue_side_hook_profile(
        hook, tongue_u0, tongue_t, style
    )

    width = ctx["width"]
    holes = [
        HoleFeature(
            at=(width / 2.0, y, tongue_t),
            screw=screw,
            through=tongue_t,
            countersink_face="bottom",
        )
        for y in ys
    ]

    vc = frame["cavity_center_v"]
    r_i = frame["r_cavity"]
    wall_u = frame["wall_outer_u"]
    band = frame["lip_band"]
    m = frame["mouth_half"]

    regions = [
        Region("tongue", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, tongue_u0, 0.0, width, frame["beam_u1"], tongue_t)),
        Region("screw_zones", RegionRole.FASTENER_KEEPOUT,
               Box3(width / 2.0 - head_r - 2.0, ys[-1] - head_r - 2.0, 0.0,
                    width / 2.0 + head_r + 2.0, ys[0] + head_r + 2.0, tongue_t)),
        Region("cable_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -r_i, vc - r_i, width, wall_u, vc + r_i)),
        Region("snap_root", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, wall_u - ctx["wall"], vc - band - 2.0,
                    width, wall_u + 2.0, vc - m)),
        Region("lower_lip", RegionRole.RETAINING_FLEXURE,
               Box3(0.0, wall_u, vc - band - 1.0,
                    width, frame["lower_lip_tip_u"], vc - m + 0.5)),
    ]

    datums = {
        "mount_face": {"at": [width / 2.0, (tongue_u0 + frame["beam_u1"]) / 2.0, tongue_t],
                       "rotate": [0.0, 0.0, 0.0]},
        "mouth_center": {"at": [width / 2.0, wall_u, vc], "rotate": [0.0, 0.0, 0.0]},
    }

    frame = dict(frame)
    frame.update(
        width=width,
        screw_head_r=head_r,
        screw_clear_d=spec["clear"],
    )
    for i, y in enumerate(ys):
        frame[f"screw_y_{i}"] = y

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=width,
        style=style,
        print_orientation="side_profile",
        holes=holes,
        regions=regions,
        datums=datums,
    )
