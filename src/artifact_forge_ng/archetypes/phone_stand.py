"""phone_stand_v1 — free-standing tilted phone stand with a charging
cutout through the lip center and a cable trough across the slot floor
(one CutBoxFeature, keepout-checked against the rest root)."""

from __future__ import annotations

from ..form.part import CutBoxFeature, PartForm
from ..form.profiles_stand import StandParams, build_stand_profile
from ..form.regions import Box3, Region
from ..form.style import MOLDED_UTILITY_PART, STYLES
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "phone_stand_side"


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    style = STYLES.get(archetype.surface_style, MOLDED_UTILITY_PART)

    params = StandParams(
        device_thickness=ctx["device_thickness"],
        tilt_deg=ctx["tilt_deg"],
        fit_clearance=ctx["fit_clearance"],
        lip_t=ctx["lip_t"],
        lip_h=ctx["lip_h"],
        base_t=ctx["base_t"],
        base_depth=ctx["base_depth"],
        rest_len=ctx["rest_len"],
        rest_t=ctx["rest_t"],
    )
    profile, frame = build_stand_profile(params, style)
    width = ctx["width"]
    bt = ctx["base_t"]
    u_rest = frame["u_rest"]

    cutboxes = []
    if ctx.get("charging_cutout", 1.0) >= 0.5:
        cw = ctx["cutout_w"]
        cutboxes.append(
            CutBoxFeature(
                "charging_cutout",
                Box3(
                    width / 2.0 - cw / 2.0, -1.0, bt - ctx["cutout_drop"],
                    width / 2.0 + cw / 2.0, u_rest - 1.5, bt + ctx["lip_h"] + 1.0,
                ),
            )
        )

    regions = [
        Region("base_bottom", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, 0.0, 0.0, width, ctx["base_depth"], bt)),
        Region("device_rest", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, ctx["lip_t"], bt, width, frame["rest_top_u"],
                    frame["rest_top_v"])),
        Region("lip", RegionRole.RETAINING_FLEXURE,
               Box3(0.0, 0.0, bt, width, ctx["lip_t"] + 0.5, bt + ctx["lip_h"] + 0.5)),
        # The rest root must never be cut — the cutout stops short of it.
        Region("rest_root", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, u_rest - 0.5, bt - 1.0, width,
                    frame["rest_foot_end"] + 2.0, bt + 6.0)),
    ]
    if cutboxes:
        regions.append(
            Region("cutout_zone", RegionRole.AESTHETIC_LIGHTENING,
                   cutboxes[0].box)
        )

    frame = dict(frame)
    frame["width"] = width

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=width,
        style=style,
        cutboxes=cutboxes,
        regions=regions,
        datums={
            "device_seat": {
                "at": [width / 2.0, u_rest, bt],
                "rotate": [0.0, 0.0, 0.0],
            }
        },
    )
