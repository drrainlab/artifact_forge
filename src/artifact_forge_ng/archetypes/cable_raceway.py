"""cable_raceway_v1 — an open U-channel cable raceway: back screwed flat
to the surface, cables drop into the slot from above. Printed as modeled
(back on the bed, walls rising) — a constant-section extrusion with only
small transverse screw holes, zero overhangs.

Part frame: X = run/length axis, Y = across the channel, Z up; back at
z = 0..wall, slot floor at z = wall.
"""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import HoleFeature, PartForm
from ..form.profiles import build_open_c_channel_profile
from ..form.regions import Box3, Region
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "open_c_channel"

KEEPOUT_CLEARANCE = 2.0


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = resolve_style(instance, archetype)

    profile, frame = build_open_c_channel_profile(
        ctx["inner_w"], ctx["inner_h"], ctx["wall"], style
    )

    length = ctx["length"]
    screw = resolved.choices.get("screw", "M4")
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    count = int(round(ctx["screw_count"]))
    spacing = ctx["screw_spacing"]
    span = spacing * (count - 1)
    xs = [length / 2.0 - span / 2.0 + i * spacing for i in range(count)]
    # Screws through the slot FLOOR (the back), heads inside the channel —
    # countersunk so cables never snag on them.
    holes = [
        HoleFeature(at=(x, 0.0, ctx["wall"]), screw=screw, through=ctx["wall"],
                    countersink_face="top")
        for x in xs
    ]

    regions = [
        Region("back", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -frame["outer_w"] / 2.0, 0.0,
                    length, frame["outer_w"] / 2.0, ctx["wall"])),
        Region("channel", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, frame["slot_u0"], ctx["wall"],
                    length, frame["slot_u1"], frame["outer_h"])),
    ] + [
        Region(f"screw_keep_{i}", RegionRole.FASTENER_KEEPOUT,
               Box3(x - head_r - KEEPOUT_CLEARANCE, -head_r - KEEPOUT_CLEARANCE,
                    0.0,
                    x + head_r + KEEPOUT_CLEARANCE, head_r + KEEPOUT_CLEARANCE,
                    ctx["wall"]))
        for i, x in enumerate(xs)
    ]

    frame = dict(frame)
    frame.update(
        width=length,
        screw_head_r=head_r,
        screw_clear_d=spec["clear"],
    )
    for i, x in enumerate(xs):
        frame[f"screw_x_{i}"] = x

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=length,
        style=style,
        holes=holes,
        regions=regions,
        datums={
            "back_face": {"at": [length / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]},
        },
    )
