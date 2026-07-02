"""zip_tie_anchor_v1 — adhesive/screw zip-tie anchor: an omega bridge whose
tunnel the tie threads through along the extrusion axis."""

from __future__ import annotations

from ..core.fasteners import screw_spec
from ..form.part import HoleFeature, PartForm
from ..form.profiles_omega import OmegaParams, build_omega_profile
from ..form.regions import Box3, Region
from ..form.style import resolve_style
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "omega_tunnel"

KEEPOUT_CLEARANCE = 2.0


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    choices = resolved.choices
    style = resolve_style(instance, archetype)

    params = OmegaParams(
        tie_w=ctx["tie_w"],
        tie_t=ctx["tie_t"],
        clearance=ctx["clearance"],
        wall=ctx["wall"],
        flange_w=ctx["flange_w"],
        base_t=ctx["base_t"],
    )
    profile, frame = build_omega_profile(params, style)
    width = ctx["width"]  # anchor length along the tie (extrusion X)
    hs, base_t = frame["half_span"], frame["base_t"]

    holes: list[HoleFeature] = []
    regions = [
        # Plane YZ, width X: (u, v, w) -> (w, u, v).
        Region("base_faces", RegionRole.MOUNTING_SURFACE,
               Box3(0.0, -hs, 0.0, width, hs, base_t)),
        Region("tunnel", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(0.0, -frame["tunnel_w"] / 2, 0.0, width,
                    frame["tunnel_w"] / 2, frame["tunnel_h"])),
        Region("bridge", RegionRole.HIGH_STRESS_REGION,
               Box3(0.0, -frame["tunnel_w"] / 2 - ctx["wall"], frame["tunnel_h"] * 0.5,
                    width, frame["tunnel_w"] / 2 + ctx["wall"], frame["bridge_top_v"])),
    ]

    if choices.get("mount", "adhesive") == "screw":
        screw = choices.get("screw", "M3")
        head_r = screw_spec(screw)["head"] / 2.0
        flange_center = frame["tunnel_w"] / 2 + ctx["wall"] + ctx["flange_w"] / 2
        for side in (-1.0, 1.0):
            y = side * flange_center
            holes.append(
                HoleFeature(
                    at=(width / 2.0, y, base_t),
                    screw=screw,
                    through=base_t,
                    countersink_face="top",
                )
            )
            regions.append(
                Region(
                    f"screw_zone_{'l' if side < 0 else 'r'}",
                    RegionRole.FASTENER_KEEPOUT,
                    Box3(width / 2 - head_r - KEEPOUT_CLEARANCE, y - head_r - KEEPOUT_CLEARANCE, 0.0,
                         width / 2 + head_r + KEEPOUT_CLEARANCE, y + head_r + KEEPOUT_CLEARANCE, base_t),
                )
            )

    frame = dict(frame)
    frame.update(width=width, screw_head_r=screw_spec(choices.get("screw", "M3"))["head"] / 2.0)

    return PartForm(
        name=instance.id,
        params=dict(ctx),
        frame=frame,
        section=profile,
        width=width,
        style=style,
        holes=holes,
        regions=regions,
        datums={
            "tunnel_entry": {
                "at": [0.0, 0.0, frame["tunnel_h"] / 2.0],
                "rotate": [0.0, 0.0, 0.0],
            }
        },
    )
