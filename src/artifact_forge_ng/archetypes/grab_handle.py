"""grab_handle_v1 — the first section_sweep archetype: a round bar swept
along a planar arc (the bow you grab), welded into two flat screw pads.
Drawer/door/case handle. Printed as modeled (pads on the bed, bow rising);
the arc's end slope stays steeper than 45 degrees for typical rises, so
the bar is self-supporting.

Part frame: X = across the handle (pad to pad), Z up; the arc runs from
(0,0,0) through (span/2, 0, rise) to (span, 0, 0); pads under the ends.
"""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import HoleFeature, PartForm, PlateFeature
from ..form.profiles_plate import rounded_rect_loop
from ..form.regions import Box3, Region
from ..form.section import SectionProfile
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "arc_bar_sweep"

KEEPOUT_CLEARANCE = 2.0


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = resolve_style(instance, archetype)

    span, rise, bar_d = ctx["span"], ctx["rise"], ctx["bar_d"]
    pad_l, pad_w, pad_t = ctx["pad_l"], ctx["pad_w"], ctx["pad_t"]

    # The IR "section" records the bar's circular cross-section for the
    # report; the compiler sweeps it along the frame-declared arc.
    r = bar_d / 2.0
    profile = SectionProfile(
        name=SECTION_NAME,
        outer=rounded_rect_loop(-r, -r, r, r, r * 0.98),
        plane="YZ",
        width_axis="X",
    )

    screw = resolved.choices.get("screw", "M4")
    spec = screw_spec(screw)
    head_r = spec["head"] / 2.0
    pads = [
        PlateFeature(name="pad_a", x0=-pad_l, y0=-pad_w / 2.0,
                     x1=r + 2.0, y1=pad_w / 2.0,
                     z_bottom=-pad_t, thickness=pad_t + r * 0.6,
                     corner_r=style.external_edge_r),
        PlateFeature(name="pad_b", x0=span - r - 2.0, y0=-pad_w / 2.0,
                     x1=span + pad_l, y1=pad_w / 2.0,
                     z_bottom=-pad_t, thickness=pad_t + r * 0.6,
                     corner_r=style.external_edge_r),
    ]
    hole_xs = [-pad_l / 2.0 - r / 2.0, span + pad_l / 2.0 + r / 2.0]
    holes = [
        HoleFeature(at=(x, 0.0, pads[0].z_top), screw=screw,
                    through=pads[0].thickness, countersink_face="top")
        for x in hole_xs
    ]

    regions = [
        Region("grip", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -r, r, span, r, rise + r)),
        Region("pads", RegionRole.MOUNTING_SURFACE,
               Box3(-pad_l, -pad_w / 2.0, -pad_t, span + pad_l, pad_w / 2.0, 0.6)),
    ] + [
        Region(f"screw_keep_{i}", RegionRole.FASTENER_KEEPOUT,
               Box3(x - head_r - KEEPOUT_CLEARANCE, -head_r - KEEPOUT_CLEARANCE,
                    -pad_t,
                    x + head_r + KEEPOUT_CLEARANCE, head_r + KEEPOUT_CLEARANCE,
                    pads[0].z_top))
        for i, x in enumerate(hole_xs)
    ]

    frame = {
        "sweep_span": span,
        "sweep_rise": rise,
        "bar_d": bar_d,
        "width": span,
        "screw_head_r": head_r,
        "screw_clear_d": spec["clear"],
    }
    for i, x in enumerate(hole_xs):
        frame[f"screw_x_{i}"] = x

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=span,
        style=style,
        kind="section_sweep",
        plates=pads,
        holes=holes,
        regions=regions,
        datums={
            "grip_apex": {"at": [span / 2.0, 0.0, rise], "rotate": [0.0, 0.0, 0.0]},
        },
    )
