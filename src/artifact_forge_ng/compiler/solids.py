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

from ..cad.booleans import cut_keep_solid, keep_largest, weld
from ..cad.bores import cut_bore, cut_box, cut_channel, cut_funnel
from ..cad.fillets import safe_fillet_edges, safe_fillet_ladder
from ..cad.geometry import Geometry
from ..cad.holes import cut_countersunk_hole
from ..form.part import PartForm, PlateFeature
from .exoskeleton import build_exoskeleton_solid
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
    channels_cut: int = 0
    ribs_welded: int = 0
    #: Bio-3: rib/node solids of the exoskeleton graph welded onto the body.
    exoskeleton_ribs_welded: int = 0
    field_cut: bool = False
    text_reliefs_built: int = 0
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


def _sweep_arc_bar(form: PartForm) -> cq.Workplane:
    """Sweep a circular section along a planar arc in the XZ plane — the
    grab-handle/bow primitive. Frame contract: ``sweep_span`` (chord along
    X), ``sweep_rise`` (arc apex height above the ends), ``bar_d``. The
    path runs from (0,0,0) through the apex (span/2, 0, rise) to (span,0,0);
    the probes sample the same three-point arc, so declared and swept
    geometry cannot drift."""
    f = form.frame
    span, rise, bar_d = f["sweep_span"], f["sweep_rise"], f["bar_d"]
    path = (
        cq.Workplane("XZ")
        .moveTo(0.0, 0.0)
        .threePointArc((span / 2.0, rise), (span, 0.0))
    )
    return (
        cq.Workplane("YZ")
        .center(0.0, 0.0)
        .circle(bar_d / 2.0)
        .sweep(path)
    )


def _loft_polygons(bottom, z0: float, top, z1: float) -> cq.Workplane:
    """Ruled loft between two horizontal polygon sections (equal point
    counts — PolyLoftFeature enforces it)."""
    wp = cq.Workplane("XY", origin=(0.0, 0.0, z0)).polyline(list(bottom)).close()
    wp = wp.workplane(offset=z1 - z0).polyline(list(top)).close()
    return wp.loft(ruled=True, combine=False)


def _loft_body(form: PartForm, log: CompileLog) -> cq.Workplane:
    """section_loft kernel: additive PolyLofts fuse into the base body,
    subtractive ones carve it (a superellipse pot's cavity/foot void)."""
    mass: cq.Workplane | None = None
    for pl in form.poly_lofts:
        if pl.cut:
            continue
        piece = _loft_polygons(pl.bottom, pl.z0, pl.top, pl.z1)
        mass = piece if mass is None else weld(mass, piece, what=pl.name)
    if mass is None:
        raise ValueError("section_loft body declares no additive poly loft")
    for pl in form.poly_lofts:
        if not pl.cut:
            continue
        cutter = _loft_polygons(pl.bottom, pl.z0, pl.top, pl.z1)
        mass, cut = cut_keep_solid(mass, cutter)
        if not cut:
            log.notes.append(f"poly loft cut {pl.name!r} could not be applied")
    return mass


def compile_part(form: PartForm) -> tuple[Geometry, CompileLog]:
    log = CompileLog()

    if form.kind == "profile_revolve":
        mass = revolve_section_profile(form.section)
    elif form.kind == "section_sweep":
        mass = _sweep_arc_bar(form)
    elif form.kind == "section_loft":
        mass = _loft_body(form, log)
    else:
        mass = extrude_section_profile(form.section, form.width)

    for plate in form.plates:
        mass = weld(mass, _build_plate(plate), what=plate.name)

    # PolyLofts as FEATURES on a non-loft base (a conical vessel's collar
    # whose front face follows the wall arc): additive lofts weld like
    # plates — before the box cuts, so a channel can pierce them.
    if form.kind != "section_loft":
        for pl in form.poly_lofts:
            piece = _loft_polygons(pl.bottom, pl.z0, pl.top, pl.z1)
            if pl.cut:
                mass, applied_cut = cut_keep_solid(mass, piece)
                if not applied_cut:
                    log.notes.append(
                        f"poly loft cut {pl.name!r} could not be applied")
            else:
                mass = weld(mass, piece, what=pl.name)

    for pin in form.pins:
        sx, sy, sz = pin.start_point()
        if pin.axis == "ANGLED":
            plane_obj = cq.Plane(origin=(sx, sy, sz), normal=pin.direction)
            post = cq.Workplane(plane_obj).circle(pin.d / 2.0).extrude(pin.length)
        else:
            plane = {"Z": "XY", "X": "YZ", "Y": "XZ"}[pin.axis]
            post = (
                cq.Workplane(plane, origin=(sx, sy, sz))
                .circle(pin.d / 2.0)
                .extrude(pin.length if pin.axis != "Y" else -pin.length)
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

    # Channel cuts are base-level like box cuts: they run before additive
    # ribs so a rib declared inside the module (the cassette's contact
    # window slab) survives the water path subtraction.
    for channel in form.channels:
        mass, cut = cut_channel(mass, channel)
        log.channels_cut += int(cut)
        if not cut:
            log.notes.append(f"channel cut {channel.name!r} could not be applied")

    # Funnel cuts are base-level like box/channel cuts: the radial sloped sump
    # floor is carved before additive ribs.
    for funnel in form.funnel_cuts:
        mass, cut = cut_funnel(mass, funnel)
        log.channels_cut += int(cut)
        if not cut:
            log.notes.append(f"funnel cut {funnel.name!r} could not be applied")

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

    # Bio-3: the exoskeleton welds AFTER the field cuts — windows first,
    # then ribs. The IR clearance guarantee means they never fight, but
    # this order makes the rib material immune to the window cutters by
    # construction, not by luck.
    # Text reliefs land after the field cuts: raised glyphs weld on,
    # engraved ones cut in — either way the glyph solid comes from ONE
    # bundled font (cad/text.py), never a machine-dependent lookup.
    if form.text_reliefs:
        from ..cad.text import build_text_solid

        for tr in form.text_reliefs:
            try:
                glyphs = build_text_solid(tr)
            except Exception as exc:  # noqa: BLE001 — a note, not a crash
                log.notes.append(f"text relief {tr.name!r} failed to render: {exc}")
                continue
            if tr.mode == "emboss":
                mass = weld(mass, glyphs, what=tr.name)
                log.text_reliefs_built += 1
            else:
                mass, cut = cut_keep_solid(mass, glyphs)
                if cut:
                    log.text_reliefs_built += 1
                else:
                    log.notes.append(
                        f"text relief {tr.name!r} engrave reverted (would fragment)")

    # Modeled threads: external ridges weld, internal grooves cut —
    # the helix solid comes from cad/threads.py.
    if form.threads:
        from ..cad.threads import build_thread_solid

        for tr in form.threads:
            try:
                helix = build_thread_solid(tr)
            except Exception as exc:  # noqa: BLE001 — a note, not a crash
                log.notes.append(f"thread {tr.name!r} failed to sweep: {exc}")
                continue
            if tr.internal:
                mass, cut = cut_keep_solid(mass, helix)
                if not cut:
                    log.notes.append(
                        f"thread {tr.name!r} groove reverted (would fragment)")
            else:
                mass = weld(mass, helix, what=tr.name)

    exo_solids = build_exoskeleton_solid(form)
    if form.exoskeleton is not None and exo_solids is None:
        log.notes.append(
            "exoskeleton declared but produced no rib solids — "
            "topology probes will fail honestly"
        )
    if exo_solids is not None:
        mass = _weld_exoskeleton(mass, exo_solids, log)

    mass = keep_largest(mass)
    return Geometry(mass), log


def _weld_exoskeleton(
    mass: cq.Workplane, solids: list[cq.Solid], log: CompileLog
) -> cq.Workplane:
    """Weld the whole rib network in ONE boolean (a compound of every
    tube and node sphere — per-tube booleans are OCC fragility bait).
    If that one fuse fails, retry in three batches; if OCC still refuses,
    report honestly and ship NO ribs — the materialization probes fail
    loudly instead of a workaround hack shipping garbage."""
    try:
        compound = cq.Compound.makeCompound(solids)
        mass = weld(mass, cq.Workplane(obj=compound), what="exoskeleton ribs")
        log.exoskeleton_ribs_welded = len(solids)
        log.notes.append(
            f"exoskeleton: {len(solids)} rib/node solids welded in one boolean"
        )
        return mass
    except Exception as exc:  # noqa: BLE001 — OCC raises anything
        log.notes.append(
            f"one-boolean exoskeleton weld failed ({exc}); retrying in batches"
        )
    n = 3
    chunks = [solids[i::n] for i in range(n) if solids[i::n]]
    current = mass
    welded = 0
    try:
        for k, chunk in enumerate(chunks):
            compound = cq.Compound.makeCompound(chunk)
            current = weld(
                current, cq.Workplane(obj=compound),
                what=f"exoskeleton batch {k + 1}/{len(chunks)}",
            )
            welded += len(chunk)
    except Exception as exc:  # noqa: BLE001
        log.exoskeleton_ribs_welded = 0
        log.notes.append(
            f"exoskeleton batch weld failed ({exc}) — ribs NOT materialized"
        )
        return mass
    log.exoskeleton_ribs_welded = welded
    log.notes.append(
        f"exoskeleton: {welded} rib/node solids welded in {len(chunks)} batches"
    )
    return current
