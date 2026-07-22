"""Manufacturing validators — FAILs here cap the grade but do not trip the
critical product-identity gate (that's contract/topology/region territory).
"""

from __future__ import annotations

import math

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


#: Layer-overlap self-support model. A downward face sloped alpha degrees
#: from VERTICAL steps every new layer out by h*tan(alpha); the fresh
#: track keeps f = 1 - h*tan(alpha)/w of its width bonded to the layer
#: below (w = extruded line width ~ nozzle). Under ~40-50% bonded width
#: the strand has nothing to sit on and sags/curls. The folklore "45 deg
#: rule" is exactly f = 0.5 at h0.2/w0.4 — this check derives the limit
#: from the instance's REAL print profile instead: 0.1 mm layers earn
#: ~63 deg, 0.3 mm layers only ~34 deg.
F_SAFE = 0.50
F_CRIT = 0.40
#: Faces steeper than this from vertical are near-horizontal undersides —
#: bridge/cantilever territory (macro beam physics, judged by span checks),
#: NOT the micro overlap regime. Gating them here would double-punish
#: legitimate short bridges.
FLAT_ALPHA = 80.0
#: Sag needs ROOM to develop: what fails is a CONTIGUOUS under-overlapped
#: surface, not the sum of scattered slivers. A connected at-risk patch no
#: bigger than a perforation-cell roof (hex/voronoi field openings — a
#: strip one wall deep, anchored on both cell walls) prints in the
#: cooling-dominated micro regime and is reported, never gated. Bounded
#: v1: area is the scale proxy; strip depth would be sharper.
MICRO_ROOF_AREA = 120.0
#: A contiguous unsafe region beyond this is support territory (FAIL);
#: smaller contiguous regions and marginal-band regions WARN.
OVERLAP_FAIL_AREA = 300.0


def alpha_crit(h: float, w: float) -> float:
    """The angle from vertical where the overlap fraction crosses F_CRIT
    for a given layer height / line width."""
    return math.degrees(math.atan(w * (1.0 - F_CRIT) / h))


def _surface_patches(V, tris):
    """Group triangles into connected surface patches (shared welded
    edges — the same 1-micron weld the manifold check uses). Returns
    lists of indices INTO the passed ``tris`` array."""
    import numpy as np

    q = np.round(np.asarray(V) * 1000.0).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    welded = inv[np.asarray(tris)]
    parent = list(range(len(welded)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edge_owner: dict[tuple[int, int], int] = {}
    for k, t in enumerate(welded):
        for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            e = (min(e), max(e))
            if e in edge_owner:
                a, b = find(edge_owner[e]), find(k)
                if a != b:
                    parent[a] = b
            else:
                edge_owner[e] = k
    groups: dict[int, list[int]] = {}
    for k in range(len(welded)):
        groups.setdefault(find(k), []).append(k)
    return list(groups.values())


def _print_pose(A, orientation: str):
    """Rotate (n,3) points or normals from the part frame into the PRINT
    pose — the same bake orient_for_print applies to exports (validators
    measure in the part frame; gravity acts in the print frame). Pure
    rotation, so one function serves both points and normals."""
    if orientation == "side_profile":     # -90 deg about Y: X points up
        return A[:, [2, 1, 0]] * (-1, 1, 1)
    if orientation == "saddle_up":        # 180 deg about X
        return A * (1, -1, -1)
    return A


@register_probe("manufacturing.overhang_overlap")
def overhang_overlap(geometry: Geometry, form: PartForm) -> Finding:
    """Micro-scale self-support: every sloped downward face of the real
    tessellated solid must keep enough fresh-layer overlap to print. The
    check measures in the print pose, buckets area by overlap fraction and
    honestly hands near-horizontal undersides to the span checks."""
    import numpy as np

    check = "manufacturing.overhang_overlap"
    h = float(form.params.get("layer_height", 0.2))
    w = float(form.params.get("nozzle_d", 0.4))
    alpha_safe = math.degrees(math.atan(w * (1.0 - F_SAFE) / h))
    profile = f"h{h:g}/w{w:g} -> self-support limit {alpha_safe:.0f}deg from vertical"
    try:
        V, T = geometry.mesh(0.2)
    except Exception as exc:  # pragma: no cover - tooling guard
        return _finding(check, Status.WARN, f"could not tessellate: {exc}")
    if len(T) == 0:
        return _finding(check, Status.WARN, "empty tessellation")

    p = V[T]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area2 = np.linalg.norm(n, axis=1)
    keep = area2 > 1e-9
    unit = _print_pose(n[keep] / area2[keep, None], form.print_orientation)
    area = 0.5 * area2[keep]
    cz = _print_pose(p[keep].mean(axis=1), form.print_orientation)[:, 2]
    zmin = _print_pose(V, form.print_orientation)[:, 2].min()

    hang = (unit[:, 2] < -0.03) & (cz > zmin + 1e-3)
    if not hang.any():
        return Finding(
            check=check, status=Status.PASS, level=Level.MANUFACTURING,
            message=f"no downward faces above the bed — self-supporting by "
                    f"construction ({profile})",
            measured=0.0, limit=alpha_safe, unit="deg")

    alpha = np.degrees(np.arcsin(np.clip(-unit[:, 2], 0.0, 1.0)))
    sloped = hang & (alpha <= FLAT_ALPHA)
    flat_area = float(area[hang & (alpha > FLAT_ALPHA)].sum())
    f = 1.0 - h * np.tan(np.radians(np.minimum(alpha, 89.9))) / w
    risk = sloped & (f < F_SAFE - 1e-9)
    safe_area = float(area[sloped & ~risk].sum())

    micro = 0.0
    regions: list[tuple[float, float]] = []  # (area, worst alpha) per patch
    if risk.any():
        for tris in _surface_patches(V, T[keep][risk]):
            patch_area = float(area[np.nonzero(risk)[0][tris]].sum())
            patch_worst = float(alpha[np.nonzero(risk)[0][tris]].max())
            if patch_area <= MICRO_ROOF_AREA:
                micro += patch_area
            else:
                regions.append((patch_area, patch_worst))

    unsafe_regions = [(pa, pw) for pa, pw in regions if pw > alpha_crit(h, w)]
    status = Status.PASS
    if any(pa > OVERLAP_FAIL_AREA for pa, _ in unsafe_regions):
        status = Status.FAIL
    elif regions:
        status = Status.WARN
    worst = float(alpha[risk].max()) if risk.any() else (
        float(alpha[sloped].max()) if sloped.any() else 0.0)

    msg = f"sloped undersides ({profile}): {safe_area:.0f} mm2 self-supporting"
    if regions:
        big_a, big_w = max(regions)
        msg += (f"; {len(regions)} contiguous at-risk region(s), largest "
                f"{big_a:.0f} mm2 at {big_w:.0f}deg")
    if micro > 0.0:
        msg += (f"; {micro:.0f} mm2 in micro roofs (<= {MICRO_ROOF_AREA:g} "
                "mm2 each — perforation-scale, anchored and cooling-"
                "dominated, not gated)")
    if flat_area > 0.0:
        msg += (f"; {flat_area:.0f} mm2 near-horizontal underside — "
                "bridge/support domain, judged by span checks")
    return Finding(
        check=check, status=status, level=Level.MANUFACTURING, message=msg,
        measured=worst, limit=alpha_safe, unit="deg",
        suggestion="" if status is Status.PASS else
        "steepen/chamfer the underside past the overlap limit, print "
        "thinner layers (they earn steeper faces), or accept supports")


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



H_BORE_OK_D = 8.0


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



@register_probe("manufacturing.print_orientation_declared")
def print_orientation_declared(geometry: Geometry, form: PartForm) -> Finding:
    """The instance may PIN its print orientation (the contract:
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
