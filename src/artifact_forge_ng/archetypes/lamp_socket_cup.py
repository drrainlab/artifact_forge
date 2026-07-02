"""lamp_socket_cup_v1 — the first profile_revolve archetype: a cup holding
a standard lamp socket insert (E27/GU10 presets), central cable exit
through the base (profile-native, no bore), bolt-circle mounting holes with
heads seating INSIDE the cup (countersink on the top face)."""

from __future__ import annotations

from ..core.fasteners import screw_spec, socket_insert_spec
from ..form.part import PartForm
from ..form.patterns import bolt_circle_centers, holes_from_centers
from ..form.profiles_cup import CupParams, build_cup_profile
from ..form.regions import Box3, Region
from ..form.style import MOLDED_UTILITY_PART, STYLES
from ..product.archetype import ArchetypeSpec, RegionRole
from ..product.instance import ProductInstance
from ..product.resolve import ResolvedParams

SECTION_NAME = "revolved_cup"

KEEPOUT_CLEARANCE = 2.0


def build_form(
    resolved: ResolvedParams,
    archetype: ArchetypeSpec,
    instance: ProductInstance,
) -> PartForm:
    ctx = resolved.context
    choices = resolved.choices
    style = STYLES.get(archetype.surface_style, MOLDED_UTILITY_PART)

    # Preset resolution: inner_d/depth of 0 are sentinels for "derive from
    # the socket preset (+fit clearance)"; explicit values always win.
    preset = socket_insert_spec(choices.get("socket", "e27"))
    fit = ctx["fit_clearance"]
    inner_d = ctx["inner_d"] if ctx["inner_d"] > 1e-6 else preset["housing_d"] + 2 * fit
    depth = ctx["depth"] if ctx["depth"] > 1e-6 else preset["depth"]

    params = CupParams(
        inner_d=inner_d,
        depth=depth,
        wall=ctx["wall"],
        base_t=ctx["base_t"],
        exit_d=ctx["exit_d"],
    )
    profile, frame = build_cup_profile(params, style)

    screw = choices.get("screw", "M3")
    head_r = screw_spec(screw)["head"] / 2.0
    count = int(round(ctx["screw_count"]))
    centers = bolt_circle_centers(count, ctx["mount_bc"])
    holes = holes_from_centers(
        centers, z_top=ctx["base_t"], through=ctx["base_t"],
        screw=screw, countersink_face="top",
    )

    outer_r, height = frame["outer_r"], frame["height"]
    regions = [
        Region("mount_face", RegionRole.MOUNTING_SURFACE,
               Box3(-outer_r, -outer_r, 0.0, outer_r, outer_r, ctx["base_t"])),
        Region("socket_seat", RegionRole.SOFT_CONTACT_SURFACE,
               Box3(-frame["inner_r"], -frame["inner_r"], ctx["base_t"],
                    frame["inner_r"], frame["inner_r"], height)),
        Region("base_web", RegionRole.HIGH_STRESS_REGION,
               Box3(-frame["inner_r"], -frame["inner_r"], 0.0,
                    frame["inner_r"], frame["inner_r"], ctx["base_t"])),
    ]
    for i, (hx, hy) in enumerate(centers):
        regions.append(
            Region(
                f"screw_zone_{i}",
                RegionRole.FASTENER_KEEPOUT,
                Box3(hx - head_r - KEEPOUT_CLEARANCE, hy - head_r - KEEPOUT_CLEARANCE, 0.0,
                     hx + head_r + KEEPOUT_CLEARANCE, hy + head_r + KEEPOUT_CLEARANCE, ctx["base_t"]),
            )
        )

    # Effective params for downstream checks/reporting: record the ACTUALS.
    effective = dict(ctx)
    effective["inner_d"] = inner_d
    effective["depth"] = depth

    frame = dict(frame)
    frame.update(width=2 * outer_r, screw_head_r=head_r)

    return PartForm(
        name=instance.id,
        params=effective,
        frame=frame,
        section=profile,
        width=2 * outer_r,  # reporting only; the compiler revolves
        style=style,
        kind="profile_revolve",
        holes=holes,
        regions=regions,
        datums={
            "rim": {"at": [0.0, 0.0, height], "rotate": [0.0, 0.0, 0.0]},
            "mount_face": {"at": [0.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]},
        },
    )
