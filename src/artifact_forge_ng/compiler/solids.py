"""compile_part — PartForm -> Geometry, with the OCC-fragility policy.

Rule: edges parallel to the width axis are NEVER 3D-filleted — their
roundness lives in the 2D profile. The remaining 3D work, in order:

1. extrude the (already molded) section;
2. build the flange plate, corner-rounded in isolation;
3. weld them (assert one solid — the generalized lip-overlap lesson);
4. the one mandatory 3D fillet: the neck<->flange root blend, applied via
   the safe-fillet ladder (blend or WARN, never a broken solid);
5. cut countersunk holes (per-hole revert-if-broken);
6. cut the hex field (one compound cutter, revert-if-broken);
7. keep-largest + validity -> Geometry.

``compile_part`` is a pure function of the PartForm — the seam a future
subprocess runner isolates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq

from ..cad.booleans import keep_largest, weld
from ..cad.bores import cut_bore, cut_box
from ..cad.fillets import safe_fillet_edges, safe_fillet_ladder
from ..cad.geometry import Geometry
from ..cad.holes import cut_countersunk_hole
from ..form.part import PartForm, PlateFeature
from .fields import cut_field
from .wires import extrude_section_profile, revolve_section_profile


@dataclass
class CompileLog:
    """What actually happened during compilation — feeds honesty, never
    silently swallowed."""

    holes_bored: int = 0
    holes_countersunk: int = 0
    bores_cut: int = 0
    boxes_cut: int = 0
    ribs_welded: int = 0
    field_cut: bool = False
    blends_applied: list[float] = field(default_factory=list)
    blends_skipped: int = 0
    notes: list[str] = field(default_factory=list)


def _build_plate(plate: PlateFeature) -> cq.Workplane:
    cx, cy = (plate.x0 + plate.x1) / 2.0, (plate.y0 + plate.y1) / 2.0
    body = (
        cq.Workplane("XY", origin=(cx, cy, plate.z_bottom))
        .rect(plate.x1 - plate.x0, plate.y1 - plate.y0)
        .extrude(plate.thickness)
    )
    if plate.corner_r > 0.05:
        body, _ = safe_fillet_edges(
            body, body.edges("|Z").vals(), plate.corner_r,
            min_length=plate.thickness * 0.5,
        )
    return body


def compile_part(form: PartForm) -> tuple[Geometry, CompileLog]:
    log = CompileLog()

    if form.kind == "profile_revolve":
        mass = revolve_section_profile(form.section)
    else:
        mass = extrude_section_profile(form.section, form.width)

    for plate in form.plates:
        mass = weld(mass, _build_plate(plate), what=plate.name)

    for pin in form.pins:
        px, py = pin.at
        post = (
            cq.Workplane("XY", origin=(px, py, pin.z0))
            .circle(pin.d / 2.0)
            .extrude(pin.length)
        )
        mass = weld(mass, post, what=pin.name)

    for loft in form.lofts:
        cx, cy = loft.base_center
        arm = (
            cq.Workplane("XY", origin=(cx, cy, loft.z0))
            .rect(loft.root[0], loft.root[1])
            .workplane(offset=loft.length)
            .rect(loft.tip[0], loft.tip[1])
            .loft(combine=False)
        )
        mass = weld(mass, arm, what=loft.name)

    # Box cuts run BEFORE additive ribs: a shell's interior cavity must not
    # mow down the bosses that stand inside it (additive features survive
    # subtractive volumes declared by the base).
    for cutbox in form.cutboxes:
        mass, cut = cut_box(mass, cutbox)
        log.boxes_cut += int(cut)
        if not cut:
            log.notes.append(f"box cut {cutbox.name!r} could not be applied")

    for rib in form.ribs:
        b = rib.box
        bar = (
            cq.Workplane(
                "XY", origin=((b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2, b.z0)
            )
            .rect(b.x1 - b.x0, b.y1 - b.y0)
            .extrude(b.z1 - b.z0)
        )
        mass = weld(mass, bar, what=rib.name)
    log.ribs_welded = len(form.ribs)

    for blend in form.blends:
        mass, applied = safe_fillet_ladder(
            mass,
            blend.zone,
            (blend.radius, *blend.fallback_ladder),
            min_length=1.0,
        )
        if applied is not None:
            log.blends_applied.append(applied)
        else:
            log.blends_skipped += 1
            log.notes.append(
                f"root blend skipped in zone {blend.zone} — style defect, not fatal"
            )

    for bore in form.bores:
        mass, cut = cut_bore(mass, bore)
        log.bores_cut += int(cut)
        if not cut:
            log.notes.append(f"bore {bore.name!r} could not be cut")

    for hole in form.holes:
        mass, bored, sunk = cut_countersunk_hole(mass, hole)
        log.holes_bored += int(bored)
        log.holes_countersunk += int(sunk)
        if not bored:
            log.notes.append(f"hole at {hole.at} could not be bored")

    for f in form.fields:
        mass, cut = cut_field(mass, f)
        log.field_cut = log.field_cut or cut
        if f.centers and not cut:
            log.notes.append("hex field cut reverted (would fragment the body)")

    mass = keep_largest(mass)
    return Geometry(mass), log
