"""cable_raceway_v1 — an open U-channel cable raceway: back screwed flat
to the surface, cables drop into the slot from above. Printed as modeled
(back on the bed, walls rising) — a constant-section extrusion with only
small transverse screw holes, zero overhangs.

Part frame: X = run/length axis, Y = across the channel, Z up; back at
z = 0..wall, slot floor at z = wall.
"""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import BoreFeature, HoleFeature, PartForm, PinFeature
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

    # -- butt-split ends: a run longer than the bed prints as mating
    # halves — pins on one part's end face, receiving sockets on the
    # other's, joined by the butt_pin_joint in an assembly.
    end_joint = resolved.choices.get("end_joint", "none")
    pins: list[PinFeature] = []
    bores: list[BoreFeature] = []
    wall = ctx["wall"]
    interference = 0.1
    pin_d, pin_len = ctx["butt_pin_d"], ctx["butt_pin_len"]
    # Two anchor points in the section: one in each side wall, mid-height.
    ow = ctx["inner_w"] + 2.0 * wall
    anchor_y = (ow - wall) / 2.0
    anchor_z = (ctx["inner_h"] + wall) * 0.5
    if end_joint == "pins":
        pins = [
            PinFeature(name=f"butt_pin_{i}", at=(y, anchor_z), d=pin_d,
                       z0=length - 0.6, length=pin_len + 0.6, axis="X")
            for i, y in enumerate((-anchor_y, anchor_y))
        ]
    elif end_joint == "sockets":
        bores = [
            BoreFeature(name=f"butt_socket_{i}", axis="X",
                        center=(0.0, y, anchor_z), d=pin_d - interference,
                        span=(0.0, pin_len + 0.4), overshoot=(1.0, 0.0))
            for i, y in enumerate((-anchor_y, anchor_y))
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

    frame["butt_anchor_y"] = anchor_y
    frame["butt_anchor_z"] = anchor_z

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=length,
        style=style,
        holes=holes,
        pins=pins,
        bores=bores,
        regions=regions,
        datums={
            "back_face": {"at": [length / 2.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]},
            # butt faces: x=length (where pins grow) and x=0 (sockets)
            "end_face": {"at": [length, 0.0, anchor_z], "rotate": [0.0, 0.0, 0.0]},
            "start_face": {"at": [0.0, 0.0, anchor_z], "rotate": [0.0, 0.0, 0.0]},
        },
    )
