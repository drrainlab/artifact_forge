"""phone_stand_v1 — free-standing tilted phone stand with a charging
cutout through the lip center and a cable trough across the slot floor
(one CutBoxFeature, keepout-checked against the rest root)."""

from __future__ import annotations

from ..form.part import CutBoxFeature, FaceWindow, PartForm, RibFeature
from ..form.profiles_stand import StandParams, build_stand_profile
from ..form.section import ArcSeg
from ..form.regions import Box3, Rect2D, Region
from ..form.style import resolve_style
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
    style = resolve_style(instance, archetype)

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

    # Biomech vein ridges on the back face (biomorphic style only): thin
    # bars welded ACROSS the rest, positions read from the PROFILE'S OWN
    # back segment — so they sit on the bowed face exactly, however the
    # organic pass curved it. Purely decorative: the device side, the slot
    # and the base are untouched.
    ribs = []
    if style.vein_rhythm > 1e-6:
        backs = [
            s for s in profile.outer.tagged("rest_back") if s.length > 10.0
        ]
        if backs:
            back = max(backs, key=lambda s: s.length)
            count = int(round(2 + style.vein_rhythm * 6))
            vein_w = 3.0
            a = vein_w / 2.0 + style.vein_relief / 2.0
            for i in range(count):
                s_t = 0.1 + 0.8 * (i + 1) / (count + 1)
                p = back.point_at(s_t)
                ribs.append(
                    RibFeature(
                        f"vein_{i}",
                        Box3(3.0, p.u - a, p.v - a, width - 3.0, p.u + a, p.v + a),
                    )
                )

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
        # Rear base deck behind the rest foot: the one big horizontal face
        # that is safe to lighten — the rim stays solid, the rest root is a
        # keepout right next door. Removing mass HERE shifts the part's COM
        # forward, i.e. away from the rear-tipping edge.
        Region("base_lightening", RegionRole.AESTHETIC_LIGHTENING,
               Box3(5.0, frame["rest_foot_end"] + 3.0, 0.0,
                    width - 5.0, ctx["base_depth"] - 6.0, bt)),
        # The tilted back of the rest — the ORIENTED canvas (FaceWindow
        # below carries the exact local frame). AABB here is the envelope
        # for schema-level targeting only.
        Region("rest_lightening", RegionRole.AESTHETIC_LIGHTENING,
               Box3(0.0, u_rest, bt, width,
                    frame["rest_top_u"] + ctx["rest_t"] / frame["tilt_sin"],
                    frame["rest_top_v"])),
    ]
    if cutboxes:
        regions.append(
            Region("cutout_zone", RegionRole.AESTHETIC_LIGHTENING,
                   cutboxes[0].box)
        )

    # Oriented modifier canvas on the back face: local a = X across the
    # stand, local b = up the slope from the face's bottom edge. Solid
    # bands are kept at the root (12 mm) and at the top (14 mm — the
    # phone's upper edge often rests there); depth is the PERPENDICULAR
    # rest thickness, so cut_mode 'through' pierces exactly the slab.
    # A biomorphically BOWED back is a curved face — no flat canvas; the
    # window is declared unusable and any field on it fails honestly.
    back_is_straight = all(
        not isinstance(s, ArcSeg)
        for s in profile.outer.tagged("rest_back")
    )
    windows = {
        "rest_lightening": FaceWindow(
            origin=(0.0, u_rest + ctx["rest_t"] / frame["tilt_sin"], bt),
            tilt_deg=ctx["tilt_deg"],
            window=Rect2D(6.0, 12.0, width - 6.0, ctx["rest_len"] - 14.0),
            depth=ctx["rest_t"],
            usable=back_is_straight,
            note="" if back_is_straight else
                 "the biomorphic bow curved the back — no flat field canvas",
        )
    }

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
        ribs=ribs,
        windows=windows,
        regions=regions,
        datums={
            "device_seat": {
                "at": [width / 2.0, u_rest, bt],
                "rotate": [0.0, 0.0, 0.0],
            }
        },
    )
