"""pipe_clip_v1_sideprint — symmetric snap C-clip for pipes/rods/handles
with the mounting beam INSIDE the extruded profile (a screw wing on each
side of the hook). Same manufacturing idea as the sideprint cable clip:
constant section, printed profile-on-bed, zero overhangs by construction.

Part frame: X = pipe/width axis, Z = vertical (mount face at z = tongue_t,
snap mouth opens straight DOWN, away from the mounting surface). Screws are
axis Z through the wings, countersunk on the bottom face.
"""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import HoleFeature, PartForm
from ..form.profiles import SnapClipParams, build_snap_c_tongue_profile
from ..form.regions import Box3, Region
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "snap_c_tongue"

SCREW_MARGIN = 4.0


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = resolve_style(instance, archetype)

    clip = SnapClipParams(
        pipe_d=ctx["pipe_d"],
        clearance=ctx["clearance"],
        wall=ctx["wall"],
        arc_deg=ctx["arc_deg"],
        neck_drop=ctx["neck_drop"],
    )
    screw = resolved.choices.get("screw", "M4")
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    setback = head_r + SCREW_MARGIN
    screw_off = clip.r_outer + setback
    beam_half = screw_off + setback
    tongue_t = ctx["tongue_t"]

    profile, frame = build_snap_c_tongue_profile(clip, beam_half, tongue_t, style)

    width = ctx["width"]
    ys = [-screw_off, screw_off]
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
    r_i, r_o = frame["r_cavity"], frame["r_outer"]

    regions = [
        Region("tongue", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -beam_half, 0.0, width, beam_half, tongue_t)),
        Region("screw_zones", RegionRole.FASTENER_KEEPOUT,
               Box3(width / 2.0 - head_r - 2.0, -screw_off - head_r - 2.0, 0.0,
                    width / 2.0 + head_r + 2.0, screw_off + head_r + 2.0, tongue_t)),
        Region("pipe_contact", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -r_i, vc - r_i, width, r_i, vc + r_i)),
        Region("snap_arms", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, -r_o - 1.0, vc - r_o - 1.0, width, r_o + 1.0, vc + 1.0)),
    ]

    datums = {
        "mount_face": {"at": [width / 2.0, 0.0, tongue_t], "rotate": [0.0, 0.0, 0.0]},
        "pipe_axis": {"at": [width / 2.0, 0.0, vc], "rotate": [0.0, 0.0, 0.0]},
    }

    frame = dict(frame)
    frame.update(width=width, screw_head_r=head_r, screw_clear_d=spec["clear"])
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
