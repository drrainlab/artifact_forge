"""Structural-feature topology probes — hex fields, ribs, arcs, pins,
seats, pockets, dovetail rails, exoskeleton and organic windows.
"""
from __future__ import annotations

from ..cad.geometry import Geometry
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from .probes import register_probe
from .topology_common import _finding, box_probe, channel_probe, solid_fraction


@register_probe("topology.hex_field_present")
def hex_field_present(geometry: Geometry, form: PartForm) -> Finding:
    if not form.fields:
        return Finding(
            check="topology.hex_field_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no field declared (nothing to verify)",
        )
    import math

    empty = []
    # A declared field that produced ZERO cells is a failed field, not a
    # vacuous pass — every cell got vetoed by keepouts and the requested
    # feature simply does not exist on the part.
    for field in form.fields:
        if not field.centers and not field.polygons:
            empty.append(f"{field.pattern} (zero cells survived the keepouts)")
    fields = [f for f in form.fields if f.centers or f.polygons]
    # EVERY cell is probed (user-reported defect): a printed part arrived with
    # 1-3 random solid cells — a single-sample probe statistically never
    # lands on them. All per-cell probe boxes fuse into ONE compound, so
    # the whole-field verdict still costs a single boolean; the per-cell
    # pass then names the exact uncut cells (only runs when the fast
    # whole-field intersect says something is solid).
    import cadquery as cq

    for field in fields:
        cells: list[tuple[float, float, float]] = []  # (cu, cv, r)
        if field.centers:
            r = field.cell / math.sqrt(3.0) * 0.4
            cells = [(cu, cv, r) for cu, cv in field.centers]
        else:
            for poly in field.polygons:
                cu = sum(p[0] for p in poly) / len(poly)
                cv = sum(p[1] for p in poly) / len(poly)
                # Probe must fit INSIDE the cell — bound by the cell's TRUE
                # narrow dimension (min extent across any edge normal), not
                # the axis-aligned bbox: a ROTATED slot (a radial tie slot)
                # has a fat bbox but stays 4 mm wide, and a bbox-sized probe
                # would poke into the ligaments and cry wolf.
                width = None
                n = len(poly)
                for i in range(n):
                    x0, y0 = poly[i]
                    x1, y1 = poly[(i + 1) % n]
                    ex, ey = x1 - x0, y1 - y0
                    edge_l = math.hypot(ex, ey)
                    if edge_l < 1e-9:
                        continue
                    nx, ny = -ey / edge_l, ex / edge_l
                    ds = [(px - x0) * nx + (py - y0) * ny for px, py in poly]
                    span = max(ds) - min(ds)
                    width = span if width is None else min(width, span)
                cells.append((cu, cv, 0.3 * max(0.5, width or 0.5)))

        def _cell_probe(cu: float, cv: float, r: float):
            # World-space probe box at the cell's mid-depth — works for
            # both horizontal and oriented (tilted-face) fields.
            wx, wy, wz = field.local_to_world(cu, cv, field.depth * 0.45)
            half = max(0.6, min(r, field.depth * 0.4))
            return box_probe(
                wx - r, wy - half, wz - half, wx + r, wy + half, wz + half)

        probes = [_cell_probe(cu, cv, r) for cu, cv, r in cells]
        compound = cq.Workplane(obj=cq.Compound.makeCompound(
            [s for p in probes for s in p.solids().vals()]))
        frac = solid_fraction(geometry.workplane, compound)
        # any single solid cell contributes ~1/N to the compound fraction
        if frac > 0.3 / max(1, len(cells)):
            uncut = []
            for i, probe in enumerate(probes):
                if solid_fraction(geometry.workplane, probe) > 0.3:
                    uncut.append(i)
            if uncut:
                empty.append(
                    f"{field.pattern}: {len(uncut)}/{len(cells)} cell(s) "
                    f"SOLID (indices {uncut[:6]}{'…' if len(uncut) > 6 else ''})")
            elif frac > 0.3:
                empty.append(f"{field.pattern} (fill {frac:.2f})")
    return _finding(
        "topology.hex_field_present",
        not empty,
        f"all fields cut real material (every cell probed)"
        if not empty else "uncut: " + ", ".join(empty),
    )
@register_probe("topology.ribs_present")
def ribs_present(geometry: Geometry, form: PartForm) -> Finding:
    if not form.ribs:
        return Finding(
            check="topology.ribs_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no ribs declared",
        )
    import math

    missing = []
    for rib in form.ribs:
        b = rib.box
        mx, my = (b.x1 - b.x0) * 0.2, (b.y1 - b.y0) * 0.2
        core = box_probe(
            b.x0 + mx, b.y0 + my, b.z0 + 0.3, b.x1 - mx, b.y1 - my, b.z1 - 0.3
        )
        # A rib may legitimately host declared Z-bores (a boss's pilot):
        # discount their area from the expected fill instead of failing.
        area = (b.x1 - b.x0 - 2 * mx) * (b.y1 - b.y0 - 2 * my)
        bored = sum(
            math.pi * (bore.d / 2.0) ** 2
            for bore in form.bores
            if bore.axis == "Z"
            and b.x0 <= bore.center[0] <= b.x1
            and b.y0 <= bore.center[1] <= b.y1
            and bore.span[1] > b.z0 and bore.span[0] < b.z1
        )
        expected = max(0.2, 1.0 - bored / max(area, 1e-9))
        frac = solid_fraction(geometry.workplane, core)
        if frac < expected * 0.85:
            missing.append(f"{rib.name} (fill {frac:.2f} < {expected * 0.85:.2f})")
    return _finding(
        "topology.ribs_present",
        not missing,
        "all ribs welded" if not missing else "missing ribs: " + ", ".join(missing),
    )
@register_probe("topology.bar_follows_arc")
def bar_follows_arc(geometry: Geometry, form: PartForm) -> Finding:
    """The swept bar must be solid along the WHOLE declared arc — sampled
    on the same three-point arc the compiler swept, so a sweep that
    silently failed (or drifted) cannot pass."""
    import math

    f = form.frame
    needed = ("sweep_span", "sweep_rise", "bar_d")
    if any(k not in f for k in needed):
        return _finding("topology.bar_follows_arc", False, "no sweep frame keys")
    span, rise, bar_d = (f[k] for k in needed)
    half = span / 2.0
    cz = (rise * rise - half * half) / (2.0 * rise)
    radius = rise - cz
    a0 = math.atan2(0.0 - cz, 0.0 - half)
    a1 = math.atan2(0.0 - cz, span - half)
    # walk the upper arc from end to end through the apex (pi/2)
    apex = math.pi / 2.0
    pts = []
    n = 10
    for i in range(n + 1):
        t = i / n
        # two symmetric halves via the apex to avoid wrap ambiguity
        ang = a0 + (apex - a0) * min(1.0, t * 2.0) if t <= 0.5 else (
            apex + (a1 - apex) * (t - 0.5) * 2.0
        )
        pts.append((half + radius * math.cos(ang), 0.0, cz + radius * math.sin(ang)))
    probe = channel_probe(pts, d=bar_d * 0.5)
    frac = solid_fraction(geometry.workplane, probe)
    return _finding(
        "topology.bar_follows_arc",
        frac > 0.95,
        f"bar fill along the declared arc {frac:.3f}",
        measured=frac,
        limit=0.95,
    )
@register_probe("topology.pins_present")
def pins_present(geometry: Geometry, form: PartForm) -> Finding:
    """Every declared pin must be real material along its length."""
    if not form.pins:
        return _finding("topology.pins_present", True, "no pins declared")
    missing = []
    for pin in form.pins:
        sx, sy, sz = pin.start_point()
        ex, ey, ez = pin.end_point()
        # inset the probe 0.4 from each end along the axis
        t0, t1 = 0.4 / pin.length, 1.0 - 0.3 / pin.length
        a = (sx + (ex - sx) * t0, sy + (ey - sy) * t0, sz + (ez - sz) * t0)
        b = (sx + (ex - sx) * t1, sy + (ey - sy) * t1, sz + (ez - sz) * t1)
        if pin.bore_d > 0.0:
            # a declared tube: probe the WALL at mid-length, four radial
            # stations on the mid-wall circle (the core is void by design)
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
            r_wall = (pin.d / 2.0 + pin.bore_d / 2.0) / 2.0
            half = min(0.5, (pin.d - pin.bore_d) / 4.0 * 0.8)
            # horizontal tubes skip the +Z station: their bore prints with
            # a teardrop roof that legitimately reaches into that band
            offsets = {
                "Z": ((r_wall, 0, 0), (-r_wall, 0, 0), (0, r_wall, 0), (0, -r_wall, 0)),
                "X": ((0, r_wall, 0), (0, -r_wall, 0), (0, 0, -r_wall)),
                "Y": ((r_wall, 0, 0), (-r_wall, 0, 0), (0, 0, -r_wall)),
            }[pin.axis]
            broken = False
            for dx, dy, dz in offsets:
                probe = box_probe(
                    mid[0] + dx - half, mid[1] + dy - half, mid[2] + dz - half,
                    mid[0] + dx + half, mid[1] + dy + half, mid[2] + dz + half)
                if solid_fraction(geometry.workplane, probe) < 0.9:
                    broken = True
                    break
            if broken:
                missing.append(f"{pin.name} (tube wall broken)")
            continue
        probe = channel_probe([a, b], d=pin.d * 0.7)
        frac = solid_fraction(geometry.workplane, probe)
        if frac < 0.9:
            missing.append(f"{pin.name} (fill {frac:.2f})")
    return _finding(
        "topology.pins_present",
        not missing,
        "all pins welded" if not missing else "missing pins: " + ", ".join(missing),
    )
@register_probe("topology.arm_reaches_tip")
def arm_reaches_tip(geometry: Geometry, form: PartForm) -> Finding:
    """Every lofted arm must be solid at its TIP — a loft that welded at
    the root but never reached its declared end is a stub, not an arm."""
    if not form.lofts:
        return _finding("topology.arm_reaches_tip", True, "no lofted arms")
    problems = []
    for loft in form.lofts:
        cx, cy = loft.base_center
        tl, tw = loft.tip
        z_tip = loft.z0 + loft.length
        probe = box_probe(
            cx - tl * 0.3, cy - tw * 0.3, z_tip - 3.0,
            cx + tl * 0.3, cy + tw * 0.3, z_tip - 0.3,
        )
        frac = solid_fraction(geometry.workplane, probe)
        if frac < 0.6:
            problems.append(f"{loft.name} (tip fill {frac:.2f})")
    return _finding(
        "topology.arm_reaches_tip",
        not problems,
        "all arms solid to the tip" if not problems
        else "stub arms: " + ", ".join(problems),
    )
@register_probe("topology.seat_lips_present")
def seat_lips_present(geometry: Geometry, form: PartForm) -> Finding:
    """Every bearing seat's retaining lip ring must be real material —
    probed at four points around the ring the outer race will sit on."""
    seats = [k[: -len("_lip_r")] for k in form.frame if k.endswith("_lip_r")]
    if not seats:
        return _finding("topology.seat_lips_present", True, "no bearing seats")
    problems = []
    for name in seats:
        f = form.frame
        cx, cy, r = f[f"{name}_cx"], f[f"{name}_cy"], f[f"{name}_lip_r"]
        z0, z1 = f[f"{name}_lip_z0"] + 0.2, f[f"{name}_lip_z1"] - 0.2
        if z1 - z0 < 0.3:
            problems.append(f"{name}: lip too thin to probe")
            continue
        for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r)):
            probe = box_probe(cx + dx - 0.5, cy + dy - 0.5, z0,
                              cx + dx + 0.5, cy + dy + 0.5, z1)
            if solid_fraction(geometry.workplane, probe) < 0.9:
                problems.append(f"{name}: lip broken at ({dx:+.1f},{dy:+.1f})")
                break
    return _finding(
        "topology.seat_lips_present",
        not problems,
        "all bearing lips solid" if not problems else "; ".join(problems),
    )
@register_probe("topology.text_relief_present")
def text_relief_present(geometry: Geometry, form: PartForm) -> Finding:
    """Every text relief left its mark on the solid: material above the
    face for emboss (glyphs are sparse — any real fill counts), material
    removed inside the band for engrave."""
    if not form.text_reliefs:
        return Finding(
            check="topology.text_relief_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no text reliefs declared",
        )
    problems = []
    for tr in form.text_reliefs:
        w, h = tr.footprint()
        cx, cy = tr.at
        sign = 1.0 if tr.direction == "up" else -1.0
        outside = tr.mode == "emboss"  # emboss band sits outside the face
        lo = tr.plane_z + (0.1 if outside else -tr.depth + 0.1) * sign
        hi = tr.plane_z + (tr.depth - 0.1 if outside else -0.1) * sign
        band = box_probe(cx - w / 2, cy - h / 2, min(lo, hi),
                         cx + w / 2, cy + h / 2, max(lo, hi))
        frac = solid_fraction(geometry.workplane, band)
        if tr.mode == "emboss" and frac < 0.02:
            problems.append(f"{tr.name}: no raised glyph material (fill {frac:.3f})")
        if tr.mode == "engrave" and frac > 0.98:
            problems.append(f"{tr.name}: nothing engraved (fill {frac:.3f})")
    return _finding(
        "topology.text_relief_present",
        not problems,
        "all text reliefs materialized" if not problems else "; ".join(problems),
    )
@register_probe("topology.pockets_present")
def pockets_present(geometry: Geometry, form: PartForm) -> Finding:
    """Blind pockets (bores with a zero-overshoot end): void along the
    pocket, but the skin PAST the blind end must still be solid."""
    pockets = [b for b in form.bores if 0.0 in b.overshoot]
    if not pockets:
        return Finding(
            check="topology.pockets_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no blind pockets declared",
        )
    problems = []
    for pocket in pockets:
        probe = channel_probe(pocket.path(), d=pocket.d * 0.8)
        frac = solid_fraction(geometry.workplane, probe)
        if frac > 0.1:
            problems.append(f"{pocket.name} not cut (fill {frac:.2f})")
            continue
        # skin check: 0.4mm past the blind end must be material
        x, y, z = pocket.center
        if pocket.axis == "Z":
            blind_hi = pocket.overshoot[1] == 0.0
            z_probe = pocket.span[1] + 0.3 if blind_hi else pocket.span[0] - 0.3
            skin = box_probe(
                x - pocket.d * 0.2, y - pocket.d * 0.2, z_probe - 0.15,
                x + pocket.d * 0.2, y + pocket.d * 0.2, z_probe + 0.15,
            )
            if solid_fraction(geometry.workplane, skin) < 0.7:
                problems.append(f"{pocket.name} pierced through its skin")
    return _finding(
        "topology.pockets_present",
        not problems,
        "all pockets cut, skins intact" if not problems else "; ".join(problems),
    )
@register_probe("topology.rail_present")
def rail_present(geometry: Geometry, form: PartForm) -> Finding:
    """The dovetail rail core must be solid material along the body — a
    rail the compiler dropped (or a cut that severed it) is a missing
    mounting interface, not a style defect. Probes the rail's inner core
    only (frame keys rail_root_w / rail_v0 / rail_v1; part frame: x =
    extrusion axis, y = profile u, z = profile v)."""
    f = form.frame
    if "rail_v0" not in f or "rail_root_w" not in f:
        return Finding(
            check="topology.rail_present",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no rail declared",
        )
    half_u = 0.3 * f["rail_root_w"]
    zone = box_probe(
        form.width * 0.25, -half_u, f["rail_v0"] + 0.2,
        form.width * 0.75, half_u, f["rail_v1"] - 0.2,
    )
    frac = solid_fraction(geometry.workplane, zone)
    return _finding(
        "topology.rail_present",
        frac > 0.9,
        f"rail core solid fraction {frac:.3f}",
        measured=frac,
        limit=0.9,
    )
@register_probe("topology.exoskeleton_ribs_materialized")
def exoskeleton_ribs_materialized(geometry: Geometry, form: PartForm) -> Finding:
    """Bio-3: every rib graph edge must be REAL material on the compiled
    part. A small cube probe sits in the PROUD half of each capsule —
    centered 0.5*r outside the panel plane at the edge midpoint (fully
    inside the tube by construction), plus probes in 2-3 node spheres.
    An IR that was never welded (or a weld OCC dropped) fails here."""
    ir = form.exoskeleton
    if ir is None:
        return Finding(
            check="topology.exoskeleton_ribs_materialized",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no exoskeleton declared",
        )
    graph = ir.graph
    if not graph.edges:
        return _finding(
            "topology.exoskeleton_ribs_materialized", False,
            "exoskeleton declared but its graph has no edges",
        )
    radii = graph.edge_radius or tuple(ir.min_rib_d / 2.0 for _ in graph.edges)
    missing: list[str] = []
    worst = 1.0
    for (i, j), r in zip(graph.edges, radii):
        na, nb = graph.nodes[i], graph.nodes[j]
        mid = ((na[0] + nb[0]) / 2.0, (na[1] + nb[1]) / 2.0,
               (na[2] + nb[2]) / 2.0)
        # proud half: n is INTO the material, so -0.5*r is 0.5*r above the
        # surface; a cube of half-size 0.25*r there lies inside the tube.
        cx, cy, cz = ir.local_to_world(mid[0], mid[1], mid[2] - 0.5 * r)
        h = max(0.2, 0.25 * r)
        probe = box_probe(cx - h, cy - h, cz - h, cx + h, cy + h, cz + h)
        frac = solid_fraction(geometry.workplane, probe)
        worst = min(worst, frac)
        if frac < 0.5:
            missing.append(f"edge ({i},{j}) fill {frac:.2f}")
    # node blends: the roots plus a mid node must be spherical material
    node_idxs = list(graph.root_nodes[:2])
    mid_idx = len(graph.nodes) // 2
    if mid_idx not in node_idxs:
        node_idxs.append(mid_idx)
    blends = graph.node_blend_radius
    for idx in node_idxs:
        r = blends[idx] if idx < len(blends) else ir.min_rib_d / 2.0
        if r < 0.4:
            continue
        node = graph.nodes[idx]
        cx, cy, cz = ir.local_to_world(node[0], node[1], node[2] - 0.4 * r)
        h = max(0.2, 0.25 * r)
        probe = box_probe(cx - h, cy - h, cz - h, cx + h, cy + h, cz + h)
        frac = solid_fraction(geometry.workplane, probe)
        worst = min(worst, frac)
        if frac < 0.5:
            missing.append(f"node {idx} fill {frac:.2f}")
    return _finding(
        "topology.exoskeleton_ribs_materialized",
        not missing,
        f"all {len(graph.edges)} rib edges + {len(node_idxs)} node blends "
        "are solid material"
        if not missing else "ribs missing on the solid: " + ", ".join(missing[:6]),
        measured=worst,
        limit=0.5,
    )
@register_probe("topology.organic_windows_open")
def organic_windows_open(geometry: Geometry, form: PartForm) -> Finding:
    """Bio-3: every organic window polygon must have removed material —
    probed at the polygon centroid at mid-depth (through-cut semantics;
    probe sized by the NARROW bbox dimension, the hex_field_present
    lesson). A declared organic field with zero polygons is a failed
    field, not a vacuous pass."""
    organic = [f for f in form.fields if f.pattern == "organic"]
    if not organic:
        return Finding(
            check="topology.organic_windows_open",
            status=Status.PASS,
            level=Level.TOPOLOGY,
            message="no organic windows declared",
        )
    import math

    def _centroid_clearance(poly, cu, cv):
        """Min distance from the centroid to the polygon boundary — the
        probe must fit INSIDE the cell, and a clipped slender cell is much
        narrower at its centroid than its bbox hints."""
        best = math.inf
        for p, q in zip(poly, list(poly[1:]) + [poly[0]]):
            dx, dy = q[0] - p[0], q[1] - p[1]
            l2 = dx * dx + dy * dy
            if l2 < 1e-18:
                continue
            t = max(0.0, min(1.0, ((cu - p[0]) * dx + (cv - p[1]) * dy) / l2))
            best = min(best, math.hypot(cu - (p[0] + t * dx), cv - (p[1] + t * dy)))
        return best

    problems: list[str] = []
    worst = 0.0
    total = 0
    for f in organic:
        if not f.polygons:
            problems.append("organic field has zero window polygons")
            continue
        for k, poly in enumerate(f.polygons):
            total += 1
            cu = sum(p[0] for p in poly) / len(poly)
            cv = sum(p[1] for p in poly) / len(poly)
            # in-plane half-extent: a box of half-diagonal <= the centroid
            # clearance stays inside the (convex) cell by construction
            h = max(0.3, 0.65 * _centroid_clearance(poly, cu, cv))
            wx, wy, wz = f.local_to_world(cu, cv, f.depth * 0.45)
            zh = max(0.5, f.depth * 0.4)
            probe = box_probe(
                wx - h, wy - h, wz - zh, wx + h, wy + h, wz + zh
            )
            frac = solid_fraction(geometry.workplane, probe)
            worst = max(worst, frac)
            if frac > 0.1:
                problems.append(f"window {k} still solid (fill {frac:.2f})")
    return _finding(
        "topology.organic_windows_open",
        not problems,
        f"all {total} organic windows are open voids"
        if not problems else "; ".join(problems[:6]),
        measured=worst,
        limit=0.1,
    )
