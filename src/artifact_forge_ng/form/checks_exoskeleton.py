"""IR checks for the Bio-2 exoskeleton — connectivity, islands, root
landing, rib diameter, window safety, and the declared load-path checks.
Everything is measured on the frozen ExoskeletonIR / the organic
FieldFeatures; a form without an exoskeleton (or without declared load
paths) passes vacuously with an explicit message. Self-registers.
"""

from __future__ import annotations

import math

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .exoskeleton.graph import graph_components
from .exoskeleton.masks import point_clear
from .part import PartForm

#: A root must land within this distance of an anchor point (mm).
ROOT_ANCHOR_TOL = 1.5
#: Absolute floor for a printable rib (mm) — two nozzle widths of PETG.
ABS_MIN_RIB_D = 1.6
#: Load-path polylines are sampled roughly this often (mm).
LOAD_PATH_STEP = 2.0


def _finding(check: str, ok: bool, message: str, *,
             measured: float | None = None,
             limit: float | None = None,
             suggestion: str = "") -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=not ok,
        measured=measured,
        limit=limit,
        suggestion=suggestion,
        unit="mm" if measured is not None else "",
    )


def _no_exo(check: str) -> Finding:
    return Finding(check=check, status=Status.PASS, level=Level.FORM,
                   message="no exoskeleton declared")


def check_rib_graph_connected(form: PartForm) -> Finding:
    check = "form.rib_graph_connected"
    ir = form.exoskeleton
    if ir is None:
        return _no_exo(check)
    if not ir.graph.root_nodes:
        return _finding(check, False, "rib graph has no root nodes")
    comps = graph_components(ir.graph)
    rooted = [c for c in comps if any(r in c for r in ir.graph.root_nodes)]
    ok = len(rooted) == 1
    return _finding(
        check, ok,
        f"{len(ir.graph.nodes)} nodes, {len(ir.graph.edges)} edges, "
        f"all {len(ir.graph.root_nodes)} roots in one component"
        if ok else
        f"roots are split across {len(rooted)} components "
        f"({len(comps)} total) — the exoskeleton is not one skeleton",
        suggestion="" if ok else "raise rib_density or relax the masks so "
                                 "a clear bridge edge exists",
    )


def check_no_rib_islands(form: PartForm) -> Finding:
    check = "form.no_rib_islands"
    ir = form.exoskeleton
    if ir is None:
        return _no_exo(check)
    degree = [0] * len(ir.graph.nodes)
    for i, j in ir.graph.edges:
        degree[i] += 1
        degree[j] += 1
    isolated = [i for i, d in enumerate(degree) if d == 0]
    roots = set(ir.graph.root_nodes)
    rootless = [
        c for c in graph_components(ir.graph)
        if not (c & roots) and len(c) > 1
    ]
    problems: list[str] = []
    if isolated:
        problems.append(f"{len(isolated)} isolated node(s) (degree 0)")
    if rootless:
        problems.append(
            f"{len(rootless)} component(s) reach no root — floating ribs"
        )
    ok = not problems
    return _finding(
        check, ok,
        "every node is wired and every component reaches a root"
        if ok else "; ".join(problems),
    )


def check_rib_roots_touch_substrate(form: PartForm) -> Finding:
    check = "form.rib_roots_touch_substrate"
    ir = form.exoskeleton
    if ir is None:
        return _no_exo(check)
    if not ir.graph.root_nodes:
        return _finding(check, False, "rib graph has no root nodes")
    if not ir.anchors:
        return _finding(check, False, "exoskeleton has no anchor points")
    worst = 0.0
    strays: list[int] = []
    for r in ir.graph.root_nodes:
        node = ir.graph.nodes[r]
        d = min(
            math.hypot(node[0] - a[0], node[1] - a[1]) for a in ir.anchors
        )
        worst = max(worst, d)
        if d > ROOT_ANCHOR_TOL:
            strays.append(r)
    ok = not strays
    return _finding(
        check, ok,
        f"{len(ir.graph.root_nodes)} root(s) within "
        f"{ROOT_ANCHOR_TOL:g}mm of an anchor"
        if ok else
        f"{len(strays)} root(s) miss every anchor by up to {worst:.2f}mm",
        measured=worst, limit=ROOT_ANCHOR_TOL,
    )


def check_min_rib_diameter_ok(form: PartForm) -> Finding:
    check = "form.min_rib_diameter_ok"
    ir = form.exoskeleton
    if ir is None:
        return _no_exo(check)
    if not ir.graph.edge_radius:
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="no rib edges to measure (connectivity "
                               "checks report the empty graph)")
    min_d = min(ir.graph.edge_radius) * 2.0
    floor = max(ir.min_rib_d - 0.05, ABS_MIN_RIB_D)
    ok = min_d >= ir.min_rib_d - 0.05 and min_d >= ABS_MIN_RIB_D
    return _finding(
        check, ok,
        f"thinnest rib {min_d:.2f}mm vs declared {ir.min_rib_d:g}mm "
        f"(abs floor {ABS_MIN_RIB_D}mm)",
        measured=min_d, limit=floor,
        suggestion="" if ok else "raise rib_d_tip — the taper bottomed out "
                                 "below the printable floor",
    )


def _seg_dist(p: tuple[float, float],
              a: tuple[float, float, float],
              b: tuple[float, float, float]) -> float:
    """In-plane distance from point p to the rib segment (a, b)."""
    ax, ay = a[0], a[1]
    dx, dy = b[0] - ax, b[1] - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-18:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / l2))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def check_windows_inside_safe_regions(form: PartForm) -> Finding:
    """Every organic window polygon (exoskeleton AND add_bone_windows —
    both emit pattern="organic" fields) edge-samples inside its window and
    clear of its keepouts. When the form carries an exoskeleton the
    windows/ribs invariant is MEASURED, not assumed: every polygon sample
    must keep at least (edge_radius + min_ligament/2) from every rib
    segment — exactly the clearance windows.py clips to."""
    check = "form.windows_inside_safe_regions"
    organic = [f for f in form.fields if f.pattern == "organic"]
    if not organic:
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="no organic windows declared")
    ir = form.exoskeleton
    ribs: list[tuple] = []
    if ir is not None and ir.graph.edges:
        radii = ir.graph.edge_radius or tuple(0.0 for _ in ir.graph.edges)
        ribs = [
            (ir.graph.nodes[i], ir.graph.nodes[j],
             r + ir.min_ligament / 2.0 - 0.05, (i, j))
            for (i, j), r in zip(ir.graph.edges, radii)
        ]
    problems: list[str] = []
    total = 0
    for f in organic:
        for wi, poly in enumerate(f.polygons):
            total += 1
            samples = []
            for p, q in zip(poly, poly[1:] + poly[:1]):
                for t in (0.0, 0.5):
                    samples.append(
                        (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
                    )
            if f.window is not None:
                outside = [
                    s for s in samples
                    if not (f.window.u0 - 1e-6 <= s[0] <= f.window.u1 + 1e-6
                            and f.window.v0 - 1e-6 <= s[1] <= f.window.v1 + 1e-6)
                ]
                if outside:
                    problems.append(
                        f"window polygon leaves its field window at "
                        f"({outside[0][0]:.1f},{outside[0][1]:.1f})"
                    )
                    continue
            if not all(point_clear(s, f.keepouts) for s in samples):
                problems.append("window polygon violates a keepout")
                continue
            for a, b, clearance, edge in ribs:
                worst = min(_seg_dist(s, a, b) for s in samples)
                if worst < clearance:
                    problems.append(
                        f"window {wi} runs {worst:.2f}mm from rib edge "
                        f"{edge} (needs {clearance + 0.05:.2f}mm = radius "
                        "+ ligament/2) — a rib crosses the window"
                    )
                    break
    ok = not problems
    return _finding(
        check, ok,
        f"{total} organic window(s), all inside their windows, clear of "
        "keepouts and clear of every rib" if ok else "; ".join(problems[:5]),
    )


def check_load_paths_connected(form: PartForm) -> Finding:
    check = "form.load_paths_connected"
    ir = form.exoskeleton
    if ir is None:
        return _no_exo(check)
    if not ir.load_paths:
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="no load paths declared")
    comps = graph_components(ir.graph)
    roots = set(ir.graph.root_nodes)
    broken: list[str] = []
    for lp in ir.load_paths:
        node = _nearest_node(ir.graph.nodes, lp.seed)
        comp = next((c for c in comps if node in c), set())
        if not (comp & roots):
            broken.append(f"{lp.from_region} -> {lp.to_region} ({lp.priority})")
    ok = not broken
    return _finding(
        check, ok,
        f"all {len(ir.load_paths)} declared load path(s) route through "
        "the graph to a root" if ok else
        "no rib route to a root for: " + "; ".join(broken),
    )


def check_no_load_path_through_keepout(form: PartForm) -> Finding:
    """Samples the ACTUAL routed load paths (ir.graph.load_path_routes —
    the Dijkstra node sequences), never the straight seed->nearest-root
    chord: the real route may reach a different root or detour around a
    keepout, and the straight chord would both false-FAIL valid designs
    and false-PASS dirty ones."""
    check = "form.no_load_path_through_keepout"
    ir = form.exoskeleton
    if ir is None:
        return _no_exo(check)
    if not ir.load_paths:
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="no load paths declared")
    routes = ir.graph.load_path_routes
    if not routes:
        return Finding(
            check=check, status=Status.PASS, level=Level.FORM,
            message="no routed load paths to sample "
                    "(connectivity checks own unreachable seeds)",
        )
    dirty: list[str] = []
    for ri, route in enumerate(routes):
        label = (
            f"{ir.load_paths[ri].from_region} -> {ir.load_paths[ri].to_region}"
            if ri < len(ir.load_paths) else f"route {ri}"
        )
        blocked = False
        for ia, ib in zip(route, route[1:]):
            a, b = ir.graph.nodes[ia], ir.graph.nodes[ib]
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            steps = max(1, int(math.ceil(length / LOAD_PATH_STEP)))
            for k in range(steps + 1):
                t = k / steps
                p = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
                if not point_clear(p, ir.masks):
                    dirty.append(
                        f"{label} blocked at ({p[0]:.1f},{p[1]:.1f}) on rib "
                        f"({min(ia, ib)},{max(ia, ib)})"
                    )
                    blocked = True
                    break
            if blocked:
                break
    ok = not dirty
    return _finding(
        check, ok,
        f"all {len(routes)} routed load path(s) clear the masks"
        if ok else "; ".join(dirty),
    )


def _nearest_node(
    nodes: tuple[tuple[float, float, float], ...], p: tuple[float, float]
) -> int:
    return min(
        range(len(nodes)),
        key=lambda i: (nodes[i][0] - p[0]) ** 2 + (nodes[i][1] - p[1]) ** 2,
    )


def check_primary_load_path_has_ribs(form: PartForm) -> Finding:
    """Every PRIMARY declared load path must carry the thickened spine:
    its recorded route's edges are all load-path edges AND their radii
    show the +20% boost — at least 1.1x the tip radius, so a route that
    silently missed the thickening pass cannot claim structural ribs."""
    check = "form.primary_load_path_has_ribs"
    ir = form.exoskeleton
    if ir is None:
        return _no_exo(check)
    primaries = [lp for lp in ir.load_paths if lp.priority == "primary"]
    if not primaries:
        return Finding(check=check, status=Status.PASS, level=Level.FORM,
                       message="no primary load paths declared")
    graph = ir.graph
    lp_edges = set(graph.load_path_edges)
    radius_of = dict(zip(graph.edges, graph.edge_radius))
    threshold = (ir.min_rib_d / 2.0) * 1.1
    problems: list[str] = []
    for lp in primaries:
        label = f"{lp.from_region} -> {lp.to_region}"
        seed_node = _nearest_node(graph.nodes, lp.seed)
        route = next(
            (r for r in graph.load_path_routes if r and r[0] == seed_node), ()
        )
        if not route:
            problems.append(f"{label}: no recorded route through the graph")
            continue
        for a, b in zip(route, route[1:]):
            edge = (min(a, b), max(a, b))
            if edge not in lp_edges:
                problems.append(f"{label}: edge {edge} is not a load-path edge")
                break
            r = radius_of.get(edge)
            if r is None or r < threshold - 1e-9:
                problems.append(
                    f"{label}: edge {edge} radius "
                    f"{0.0 if r is None else r:.2f} < {threshold:.2f} "
                    "(missing the +20% load-path thickening)"
                )
                break
    ok = not problems
    return _finding(
        check, ok,
        f"all {len(primaries)} primary load path(s) ride thickened ribs"
        if ok else "; ".join(problems),
    )


register_probe("form.rib_graph_connected")(
    lambda form, ctx: check_rib_graph_connected(form))
register_probe("form.no_rib_islands")(
    lambda form, ctx: check_no_rib_islands(form))
register_probe("form.rib_roots_touch_substrate")(
    lambda form, ctx: check_rib_roots_touch_substrate(form))
register_probe("form.min_rib_diameter_ok")(
    lambda form, ctx: check_min_rib_diameter_ok(form))
register_probe("form.windows_inside_safe_regions")(
    lambda form, ctx: check_windows_inside_safe_regions(form))
register_probe("form.load_paths_connected")(
    lambda form, ctx: check_load_paths_connected(form))
register_probe("form.no_load_path_through_keepout")(
    lambda form, ctx: check_no_load_path_through_keepout(form))
register_probe("form.primary_load_path_has_ribs")(
    lambda form, ctx: check_primary_load_path_has_ribs(form))
