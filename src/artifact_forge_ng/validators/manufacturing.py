"""Manufacturing validators — FAILs here cap the grade but do not trip the
critical product-identity gate (that's contract/topology/region territory).
"""

from __future__ import annotations

from ..cad.geometry import Geometry
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from .probes import register_probe

BED = (220.0, 220.0, 250.0)


def _finding(check: str, status: Status, message: str, *, measured: float | None = None,
             limit: float | None = None, suggestion: str = "") -> Finding:
    return Finding(
        check=check, status=status, level=Level.MANUFACTURING, message=message,
        measured=measured, limit=limit, suggestion=suggestion,
        unit="mm" if measured is not None else "",
    )


@register_probe("manufacturing.bed_fit")
def bed_fit(geometry: Geometry, form: PartForm) -> Finding:
    bb = geometry.bounding_box()
    size = sorted(bb.size, reverse=True)
    declared = (
        form.params.get("bed_x"), form.params.get("bed_y"), form.params.get("bed_z")
    )
    bed = sorted(
        (d if d is not None else b for d, b in zip(declared, BED)), reverse=True
    )
    ok = all(s <= b + 1e-6 for s, b in zip(size, bed))
    return _finding(
        "manufacturing.bed_fit",
        Status.PASS if ok else Status.FAIL,
        f"part {size[0]:.0f}x{size[1]:.0f}x{size[2]:.0f} vs bed {bed[0]:.0f}x{bed[1]:.0f}x{bed[2]:.0f}",
        measured=size[0],
        limit=bed[0],
    )


@register_probe("manufacturing.min_wall")
def min_wall(geometry: Geometry, form: PartForm) -> Finding:
    """Thinnest designed feature vs the printer's wall floor. Analytic (the
    IR knows its own thinnest member — the tapered lower lip tip); a mesh
    raycast can replace this later without changing the check name."""
    wall = form.params.get("wall")
    floor = form.params.get("printer_min_wall", 1.2)
    if wall is None:
        return _finding("manufacturing.min_wall", Status.WARN, "wall unknown")
    thinnest = min(wall, wall * 0.7)  # lower lip tip taper
    ok = thinnest >= floor - 1e-6
    return _finding(
        "manufacturing.min_wall",
        Status.PASS if ok else Status.FAIL,
        f"thinnest designed wall {thinnest:.2f} vs printer floor {floor:.2f}",
        measured=thinnest,
        limit=floor,
        suggestion="" if ok else "increase wall or use a larger nozzle",
    )


#: Lip ledges shorter than this print acceptably without support even as
#: horizontal cantilevers (a few sagging perimeter loops, cosmetic only).
LIP_CANTILEVER_OK = 8.0


@register_probe("manufacturing.overhang")
def overhang(geometry: Geometry, form: PartForm) -> Finding:
    """Overhang honesty, per PRINT ORIENTATION.

    side_profile: a constant-section extrusion printed profile-on-bed has
    zero overhangs BY CONSTRUCTION — every layer is the same shape. The
    claim is only made when the section really is constant (no plates,
    ribs, cuts or fields; small transverse holes bridge natively).

    flange-down (the side-hook family default): two distinct problems —
    the cavity roof (round = bridged circular span, teardrop = self-
    supporting 45deg) AND the lips, which print as horizontal cantilever
    ledges hanging over the mouth. A slicer will ask for supports under a
    long lower lip no matter what the cavity roof does; the honest fix is
    the sideprint variant, not more chamfers. Lesson from a real slicer
    session: the first version of this check modeled only the cavity."""
    if form.print_orientation == "side_profile":
        breakers = [
            label
            for label, items in (
                ("plates", form.plates), ("ribs", form.ribs),
                ("cutboxes", form.cutboxes), ("bores", form.bores),
                ("fields", form.fields),
            )
            if items
        ]
        if form.kind != "section_extrude" or breakers:
            return _finding(
                "manufacturing.overhang", Status.WARN,
                "side-print orientation, but the part is not a pure "
                f"extrusion ({', '.join(breakers) or form.kind}) — "
                "overhangs unverified",
                suggestion="keep sideprint parts constant-section",
            )
        return _finding(
            "manufacturing.overhang", Status.PASS,
            "profile-on-bed: constant section along the vertical axis — no "
            "overhangs by construction; screw holes print as short "
            "horizontal bores. Note: lip flexure crosses layers in this "
            "orientation — use 3+ perimeters",
            measured=0.0, limit=45.0,
        )

    problems: list[str] = []
    worst = Status.PASS
    suggestion = ""

    span = 2.0 * form.frame.get("r_cavity", 0.0)
    if span > 0.0:
        if form.frame.get("cavity_teardrop", 0.0) >= 0.5:
            problems.append("teardrop cavity roof self-supporting at 45deg")
        elif span <= 12.0:
            problems.append(f"round cavity span {span:.1f} mm — trivial bridge")
        elif span <= 35.0:
            problems.append(
                f"round cavity roof spans {span:.1f} mm — relies on bridging "
                "(near-90deg local overhang at the roof sides)"
            )
            worst = Status.WARN
            suggestion = "cavity_roof: teardrop, or the sideprint variant"
        else:
            problems.append(f"round cavity span {span:.1f} mm needs support")
            worst = Status.FAIL
            suggestion = "the sideprint variant, or support_policy: allow"

    lip = form.frame.get("lower_lip_tip_u", 0.0) - form.frame.get(
        "wall_outer_u", 0.0
    )
    if form.frame.get("lower_lip_tip_u") is not None and lip > LIP_CANTILEVER_OK:
        problems.append(
            f"the {lip:.0f} mm lower lip prints as a horizontal cantilever "
            "flange-down — slicers will ask for supports under the lips"
        )
        if worst is Status.PASS:
            worst = Status.WARN
        if not suggestion:
            suggestion = (
                "the sideprint variant prints this hook support-free "
                "(intent make_support_free)"
            )

    if not problems:
        return _finding(
            "manufacturing.overhang", Status.PASS, "no overhang-prone features"
        )
    return _finding(
        "manufacturing.overhang", worst,
        "; ".join(problems),
        measured=span if span > 0 else None,
        suggestion=suggestion,
    )


@register_probe("manufacturing.max_opening_span")
def max_opening_span(geometry: Geometry, form: PartForm) -> Finding:
    """Support-free is a TARGET, never a promise: for through-wall fields
    on a vertical wall (a ring band printed flat) every opening roof is a
    bridge — measure the widest span and say whether it bridges."""
    spans = []
    for f in form.fields:
        if f.mapping != "cylindrical":
            continue
        for poly in f.polygons:
            spans.append(max(p[0] for p in poly) - min(p[0] for p in poly))
        if f.centers:
            spans.append(f.cell)
    if not spans:
        return _finding(
            "manufacturing.max_opening_span", Status.PASS,
            "no through-wall openings to bridge",
        )
    worst = max(spans)
    ok = worst <= 12.0
    return _finding(
        "manufacturing.max_opening_span",
        Status.PASS if ok else Status.WARN,
        f"widest opening spans {worst:.1f} mm "
        + ("— bridges fine, supports unlikely" if ok
           else "— roof bridging is doubtful, supports likely"),
        measured=worst,
        limit=12.0,
    )


# -- vertical farm cleanability (docs/VERTICAL_FARM_PACK.md) -----------------
# These run on EVERY part (the always-on manufacturing suite), so each one
# short-circuits to PASS "not applicable" when the form carries no water
# geometry — a cable clip must never pay for the water contract.

BRUSH_D = 8.0
BRUSH_MIN_CHANNEL_W = 10.0
CREVICE_MIN_OPENING = 2.0


@register_probe("manufacturing.brush_access_to_water_channel")
def brush_access_to_water_channel(geometry: Geometry, form: PartForm) -> Finding:
    if not form.channels:
        return _finding(
            "manufacturing.brush_access_to_water_channel", Status.PASS,
            "not applicable — no water channel on this part",
        )
    from ..cad.probes import channel_probe, solid_fraction

    ch = form.channels[0]
    if ch.width < BRUSH_MIN_CHANNEL_W:
        return _finding(
            "manufacturing.brush_access_to_water_channel", Status.FAIL,
            f"channel {ch.width:g} narrower than a {BRUSH_MIN_CHANNEL_W:g} brush",
            measured=ch.width, limit=BRUSH_MIN_CHANNEL_W,
        )
    top = form.frame.get("channel_top_z", ch.z_top)
    worst = 0.0
    for x, y, floor_z in ch.centerline(lift=1.0):
        probe = channel_probe([(x, y, floor_z), (x, y, top + 14.0)], d=BRUSH_D)
        worst = max(worst, solid_fraction(geometry.workplane, probe))
    ok = worst < 0.05
    return _finding(
        "manufacturing.brush_access_to_water_channel",
        Status.PASS if ok else Status.FAIL,
        f"vertical brush path worst solid fraction {worst:.3f} along the run"
        + ("" if ok else " — something roofs the channel"),
        measured=worst, limit=0.05,
    )


#: The flush water path where a downward through-hole is a leak (VF-9). The
#: collector drain is a BORE (not a cutbox) and lives outside these regions, so
#: it is the sanctioned exception by construction.
FLUSH_WET_REGION_NAMES = ("water_channel", "lap_receiver", "lap_lip")


@register_probe("manufacturing.no_through_holes_in_wet_lap_zone")
def no_through_holes_in_wet_lap_zone(geometry: Geometry, form: PartForm) -> Finding:
    """VF-9 invariant: NO cutbox with an open bottom may sit under the active
    flush water path (the channel + lap seam) — that is a leak straight down.
    The only sanctioned downward exit is the collector drain (a bore, outside
    these regions). n/a on parts with no flush water path."""
    from ..product.archetype import RegionRole
    check = "manufacturing.no_through_holes_in_wet_lap_zone"
    wet = [r for r in form.regions
           if r.role is RegionRole.TRANSIENT_WATER_PATH
           and r.name in FLUSH_WET_REGION_NAMES]
    if not wet:
        return _finding(check, Status.PASS, "not applicable — no flush water path")

    def _overlaps(b, w) -> bool:
        return (b.x0 <= w.x1 and w.x0 <= b.x1 and b.y0 <= w.y1
                and w.y0 <= b.y1 and b.z0 <= w.z1 and w.z0 <= b.z1)

    offenders = []
    for cut in form.cutboxes:
        b = cut.box
        if b.z0 > 0.05:
            continue  # closed bottom — no downward path
        if "drain" in cut.name:
            continue  # the sanctioned collector drain
        if any(_overlaps(b, w.box) for w in wet):
            offenders.append(
                f"cut {cut.name!r} is open-bottom (z0={b.z0:g}) under the water path")
    ok = not offenders
    return _finding(
        check, Status.PASS if ok else Status.FAIL,
        "no through hole under the active water path — nothing leaks straight down"
        if ok else "; ".join(offenders),
    )


@register_probe("manufacturing.no_hidden_wet_crevices")
def no_hidden_wet_crevices(geometry: Geometry, form: PartForm) -> Finding:
    from ..product.archetype import RegionRole

    wet = [r for r in form.regions if r.role is RegionRole.TRANSIENT_WATER_PATH]
    if not wet:
        return _finding(
            "manufacturing.no_hidden_wet_crevices", Status.PASS,
            "not applicable — no wet regions on this part",
        )

    def _overlaps(b, w) -> bool:
        return (b.x0 <= w.x1 and w.x0 <= b.x1 and b.y0 <= w.y1
                and w.y0 <= b.y1 and b.z0 <= w.z1 and w.z0 <= b.z1)

    offenders: list[str] = []
    for cut in form.cutboxes:
        b = cut.box
        if not any(_overlaps(b, w.box) for w in wet):
            continue
        # VF-9: the floored lap lip-seat is a WIDE, open-top, shallow step (its
        # narrowest dim is the vertical depth, not a crevice mouth) — a brush
        # reaches it from above and the neighbour's lip lifts straight out. Not
        # a hidden crevice as long as the lateral footprint is brush-wide.
        if ("lap_receiver" in cut.name
                and (b.x1 - b.x0) >= CREVICE_MIN_OPENING
                and (b.y1 - b.y0) >= CREVICE_MIN_OPENING):
            continue
        narrowest = min(b.x1 - b.x0, b.y1 - b.y0, b.z1 - b.z0)
        if narrowest < CREVICE_MIN_OPENING:
            offenders.append(
                f"cut {cut.name!r} opens only {narrowest:.2f} in the wet path")
    for bore in form.bores:
        x, y, z = bore.center
        r = bore.d / 2.0
        from ..form.regions import Box3

        lo, hi = bore.span
        if bore.axis == "Z":
            bbox = Box3(x - r, y - r, lo, x + r, y + r, hi)
        elif bore.axis == "Y":
            bbox = Box3(x - r, lo, z - r, x + r, hi, z + r)
        else:
            bbox = Box3(lo, y - r, z - r, hi, y + r, z + r)
        if bore.d < CREVICE_MIN_OPENING and any(_overlaps(bbox, w.box) for w in wet):
            offenders.append(f"bore {bore.name!r} d={bore.d:g} in the wet path")
    ok = not offenders
    return _finding(
        "manufacturing.no_hidden_wet_crevices",
        Status.PASS if ok else Status.FAIL,
        "every wet-path opening admits a brush"
        if ok else "; ".join(offenders),
        measured=None if ok else CREVICE_MIN_OPENING,
        suggestion="" if ok else "widen the opening past 2 mm or move it out of the wet path",
    )


@register_probe("manufacturing.no_unwashable_snap_pockets")
def no_unwashable_snap_pockets(geometry: Geometry, form: PartForm) -> Finding:
    windows = [c for c in form.cutboxes if "snap_window" in c.name]
    if not windows:
        return _finding(
            "manufacturing.no_unwashable_snap_pockets", Status.PASS,
            "not applicable — no snap windows on this part",
        )
    from ..cad.probes import box_probe, solid_fraction

    blocked: list[str] = []
    for win in windows:
        b = win.box
        probe = box_probe(
            b.x0 + 0.2, b.y0 + 0.2, b.z0 + 0.2,
            b.x1 - 0.2, b.y1 - 0.2, b.z1 - 0.2,
        )
        frac = solid_fraction(geometry.workplane, probe)
        if frac > 0.05:
            blocked.append(f"{win.name!r} solid fraction {frac:.2f}")
    ok = not blocked
    return _finding(
        "manufacturing.no_unwashable_snap_pockets",
        Status.PASS if ok else Status.FAIL,
        f"{len(windows)} snap window(s) verified void through the wall"
        if ok else "; ".join(blocked),
    )


# -- VF-4.1 printability: bottom pockets and horizontal bores -------------------

#: FDM bridging bands for a flat ceiling over a bottom-entered pocket,
#: printing as-modeled (bottom down): short bridges print clean, medium
#: ones sag cosmetically, long ones need support.
CEILING_BRIDGE_OK = 25.0
CEILING_BRIDGE_FAIL = 35.0
#: A horizontal circular bore prints acceptably up to this diameter; above
#: it the round ceiling sags — use a teardrop roof or a vertical bore.
H_BORE_OK_D = 8.0


@register_probe("manufacturing.supportless_lightweight_windows_ok")
def supportless_lightweight_windows_ok(geometry: Geometry, form: PartForm) -> Finding:
    """No blind bottom pocket may hide a support-critical flat ceiling
    (VF-4.1). Every cutbox entered from BELOW whose footprint could bridge
    is probed ON THE SOLID just above its ceiling: void above (a through
    opening into another cavity — the open-skeleton case) passes; material
    above is a real bridge, graded by span. n/a fast-path: parts without
    bottom-entered pockets never touch the geometry."""
    check = "manufacturing.supportless_lightweight_windows_ok"
    if form.print_orientation != "as_modeled":
        return _finding(check, Status.PASS,
                        "n/a — sideprint part; ceilings print vertical")
    top = form.width or 0.0
    candidates = [
        c for c in form.cutboxes
        if c.box.z0 <= 0.05 and c.box.z1 < top - 0.05
        and min(c.box.x1 - c.box.x0, c.box.y1 - c.box.y0) > CEILING_BRIDGE_OK
    ]
    if not candidates:
        return _finding(check, Status.PASS,
                        "no bottom-entered pockets that could bridge — n/a")
    from ..cad.probes import box_probe, solid_fraction

    problems: list[str] = []
    worst = 0.0
    for cut in candidates:
        b = cut.box
        probe = box_probe(b.x0 + 0.3, b.y0 + 0.3, b.z1 + 0.2,
                          b.x1 - 0.3, b.y1 - 0.3, b.z1 + 1.2)
        if solid_fraction(geometry.workplane, probe) <= 0.5:
            continue  # through into another cavity — no ceiling, no bridge
        span = min(b.x1 - b.x0, b.y1 - b.y0)
        worst = max(worst, span)
        if span > CEILING_BRIDGE_FAIL:
            problems.append(
                f"pocket {cut.name!r} bridges a {span:.0f} flat ceiling "
                f"(> {CEILING_BRIDGE_FAIL:g}) — make it through, vaulted or a "
                "rib skeleton")
    if problems:
        return _finding(check, Status.FAIL, "; ".join(problems),
                        measured=worst, limit=CEILING_BRIDGE_FAIL,
                        suggestion="through-open the pocket or vault its roof")
    if worst > 0.0:
        return _finding(
            check, Status.WARN,
            f"flat ceiling bridges up to {worst:.0f} over bottom pockets — "
            "prints, expect sag", measured=worst, limit=CEILING_BRIDGE_FAIL)
    return _finding(check, Status.PASS,
                    "every wide bottom pocket is through-open — no ceiling "
                    "bridges, supportless by construction")


@register_probe("manufacturing.horizontal_bore_supportless")
def horizontal_bore_supportless(geometry: Geometry, form: PartForm) -> Finding:
    """A HORIZONTAL circular bore wider than H_BORE_OK_D prints a sagging
    round ceiling as-modeled; a teardrop roof (or a vertical bore) is
    self-supporting. Purely IR — the roof is a declared feature."""
    check = "manufacturing.horizontal_bore_supportless"
    if form.print_orientation != "as_modeled":
        return _finding(check, Status.PASS,
                        "n/a — sideprint part; bore axes rotate with it")
    horizontal = [b for b in form.bores
                  if b.axis in ("X", "Y") and b.d > H_BORE_OK_D]
    if not horizontal:
        return _finding(check, Status.PASS,
                        f"no horizontal bores over {H_BORE_OK_D:g} — n/a")
    sagging = [b for b in horizontal if b.roof != "teardrop"]
    if sagging:
        names = ", ".join(f"{b.name!r} d{b.d:g}" for b in sagging[:4])
        return _finding(
            check, Status.WARN,
            f"horizontal circular bore(s) {names} sag without support — "
            "give them roof: teardrop, or run them vertical",
            measured=max(b.d for b in sagging), limit=H_BORE_OK_D,
            suggestion="BoreFeature(roof=\"teardrop\")")
    return _finding(
        check, Status.PASS,
        f"{len(horizontal)} horizontal bore(s) over {H_BORE_OK_D:g} — all "
        "teardrop-roofed, self-supporting")


CAP_ROOF_OVERHANG_MAX = 5.0  # mm — a printable one-sided ledge, not a cantilever


@register_probe("manufacturing.cap_supportless_verified")
def cap_supportless_verified(geometry: Geometry, form: PartForm) -> Finding:
    """VF-9 Part B: closes the VF-7c blind spot (manufacturing.overhang never
    modelled the inlet cap's saddle-slot roof, so the old flat cantilever passed
    only because it flipped for print). The cap must print support-free
    AS-MODELED: the rest-ledge roof over the open saddle slot must be a SHORT
    one-sided overhang (<= CAP_ROOF_OVERHANG_MAX), not a deep floating
    cantilever, and a nose column must reach the bed to anchor the roof over the
    channel. n/a on parts without a cap saddle slot + hose bore."""
    check = "manufacturing.cap_supportless_verified"
    slots = [c for c in form.cutboxes if "saddle_slot" in c.name]
    has_hose = any("hose" in b.name for b in form.bores)
    if not slots or not has_hose:
        return _finding(check, Status.PASS, "not an inlet cap — n/a")
    slot = slots[0].box
    overhang = slot.y1 - slot.y0  # inboard reach of the rest ledge over open air
    nose = [r for r in form.ribs if "nose" in r.name and r.box.z0 <= 0.05]
    problems: list[str] = []
    if overhang > CAP_ROOF_OVERHANG_MAX + 1e-6:
        problems.append(
            f"saddle-slot roof overhangs {overhang:.1f} inboard over open air "
            f"(> {CAP_ROOF_OVERHANG_MAX:g}) — a floating cantilever; shorten "
            "hook_reach or anchor the inboard side")
    if not nose:
        problems.append(
            "no nose column reaches the bed to anchor the roof over the channel")
    ok = not problems
    return _finding(
        check, Status.PASS if ok else Status.FAIL,
        f"support-free Г-hook: {overhang:.1f}mm rest ledge, the nose column "
        "anchors the roof — nothing floats as-modeled"
        if ok else "; ".join(problems),
        measured=overhang, limit=CAP_ROOF_OVERHANG_MAX)


@register_probe("manufacturing.print_orientation_declared")
def print_orientation_declared(geometry: Geometry, form: PartForm) -> Finding:
    """The instance may PIN its print orientation (VF-4.1 contract:
    manufacturing.print_orientation on the instance). The builder's actual
    orientation must match — a silent flip invalidates every supportless
    guarantee. n/a when nothing is declared."""
    check = "manufacturing.print_orientation_declared"
    declared = form.frame.get("declared_print_orientation")
    if declared is None:
        return _finding(check, Status.PASS,
                        "no declared print orientation — builder's choice")
    ok = declared == form.print_orientation
    return _finding(
        check, Status.PASS if ok else Status.FAIL,
        f"declared {declared!r} == built {form.print_orientation!r}" if ok else
        f"instance declares {declared!r} but the part is built "
        f"{form.print_orientation!r} — the supportless contract is void",
        suggestion="" if ok else "align manufacturing.print_orientation with the builder",
    )


def _nonmanifold_edges(verts, faces) -> int:
    """Count undirected edges NOT shared by exactly two triangles, after
    WELDING coincident vertices by position. OCC tessellates per-face, so
    vertices on a shared edge carry different indices in the two faces — the
    raw index space is never manifold. We quantize to 1 micron and rebuild
    the edge incidence on merged positions (the same test a slicer applies
    to the STL it loads)."""
    import numpy as np
    if len(faces) == 0:
        return 0
    q = np.round(np.asarray(verts) * 1000.0).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    tri = inv[np.asarray(faces)]
    e = np.sort(np.concatenate(
        [tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]], axis=0), axis=1)
    e = e[e[:, 0] != e[:, 1]]  # drop degenerate edges
    _, counts = np.unique(e, axis=0, return_counts=True)
    return int(np.count_nonzero(counts != 2))


@register_probe("manufacturing.mesh_manifold")
def mesh_manifold(geometry: Geometry, form: PartForm) -> Finding:
    """The EXPORTED mesh must be edge-manifold watertight — every edge shared
    by exactly two triangles (after welding coincident vertices, the way a
    slicer loads the STL). A perfectly valid BRep can still tessellate into a
    torn mesh: OCC BRepMesh drops hole-triangulations on a single planar face
    that carries hundreds of openings, leaving non-manifold edges and cells
    that read as solid. Field-reported on a printed cassette (the slicer
    flagged '16 non-manifold edges'; cells looked filled). Only field-bearing
    parts (holey faces) can hit it, so the check meshes at the export
    tolerance ONLY for them; everything else is trivially manifold."""
    check = "manufacturing.mesh_manifold"
    # Only the ORTHOGONAL slot mesh (mesh_floor, pattern="slots") packs
    # hundreds of coplanar square holes into one planar face — the shape OCC
    # BRepMesh tears. Organic / hex / voronoi fields have curved or sparse
    # openings, their own integrity probes, and (for exoskeletons) a BRep
    # that legitimately tessellates with weld-junction seams; meshing them
    # here would false-positive.
    if not any(getattr(f, "pattern", "") == "slots" for f in form.fields):
        return _finding(check, Status.PASS, "no orthogonal slot mesh — n/a")
    try:
        verts, faces = geometry.mesh(0.05)  # match export_stl's linear tolerance
    except Exception as exc:  # pragma: no cover - tooling guard
        return _finding(check, Status.WARN, f"could not tessellate for the check: {exc}")
    if len(faces) == 0:
        return _finding(check, Status.WARN, "empty tessellation")
    bad = _nonmanifold_edges(verts, faces)
    return _finding(
        check, Status.PASS if bad == 0 else Status.FAIL,
        f"exported mesh is edge-manifold watertight ({len(faces)} triangles)"
        if bad == 0 else
        f"{bad} non-manifold edge(s) in the exported STL — the slicer rejects "
        "it; a holey planar face out-ran BRepMesh (too many cells in one face)",
        measured=float(bad), limit=0.0,
        suggestion="" if bad == 0 else
        "coarsen the field (larger cell / fewer openings) so each holey face "
        "tessellates cleanly",
    )
