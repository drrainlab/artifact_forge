"""IR check for field ligaments — the webs between cells are a GUARANTEED
minimum, measured on the final cell geometry (centers spacing for hex,
polygon gaps for voronoi/slots). Self-registers.
"""

from __future__ import annotations

import math

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm
from .voronoi import min_polygon_gap


def check_min_ligament_ok(form: PartForm) -> Finding:
    problems: list[str] = []
    checked = 0
    for f in form.fields:
        if f.polygons and f.min_ligament > 0:
            checked += 1
            gap = min_polygon_gap([list(p) for p in f.polygons])
            if len(f.polygons) >= 2 and gap < f.min_ligament - 0.05:
                problems.append(
                    f"{f.pattern}: measured web {gap:.2f} < ligament {f.min_ligament:g}"
                )
        elif f.centers:
            checked += 1
            # hex: measure the web between ACTUAL hexagon polygons of the
            # near neighbour pairs (circumradius alone is falsely
            # pessimistic on the staggered diagonals).
            # Same orientation the compiler cuts: flats along the row axis
            # (vertices at 30 + 60k degrees).
            r_hex = f.cell / math.sqrt(3.0)
            hexes = [
                [
                    (
                        cx + r_hex * math.cos(math.radians(30 + 60 * k)),
                        cy + r_hex * math.sin(math.radians(30 + 60 * k)),
                    )
                    for k in range(6)
                ]
                for cx, cy in f.centers
            ]
            floor = max(f.min_ligament, 1.0)
            near = 2.0 * r_hex + floor + 2.0
            web = math.inf
            for i in range(len(f.centers)):
                for j in range(i + 1, len(f.centers)):
                    a, b = f.centers[i], f.centers[j]
                    if math.hypot(a[0] - b[0], a[1] - b[1]) > near:
                        continue
                    web = min(web, min_polygon_gap([hexes[i], hexes[j]]))
            if len(f.centers) >= 2 and web < floor - 0.05:
                problems.append(f"hex: measured web {web:.2f} < floor {floor:g}")
    if checked == 0:
        return Finding(
            check="form.min_ligament_ok",
            status=Status.PASS,
            level=Level.FORM,
            message="no fields declared",
        )
    ok = not problems
    return Finding(
        check="form.min_ligament_ok",
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message="field webs meet their ligaments" if ok else "; ".join(problems),
        critical=not ok,
    )


def check_field_cells_present(form: PartForm) -> Finding:
    """Pre-CAD mirror of topology.hex_field_present's zero-cell rule: a
    declared field whose every cell was vetoed by margins/keepouts does
    not exist — the requested feature is a lie. Caught at validate time
    (the IR knows the surviving cells), not after a CAD build fails."""
    if not form.fields:
        return Finding(
            check="form.field_cells_present",
            status=Status.PASS,
            level=Level.FORM,
            message="no fields declared",
        )
    dead = []
    for f in form.fields:
        if f.centers or f.polygons:
            continue
        where = f.pattern
        if f.window is not None:
            where += (f" (window {f.window.u1 - f.window.u0:.1f}x"
                      f"{f.window.v1 - f.window.v0:.1f}mm, "
                      f"ligament {f.min_ligament:g})")
        dead.append(where)
    ok = not dead
    return Finding(
        check="form.field_cells_present",
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=(
            f"{sum(len(f.centers) + len(f.polygons) for f in form.fields)} "
            "cells survived across all fields"
            if ok
            else "zero cells survived the keepouts: " + ", ".join(dead)
        ),
        critical=not ok,
        suggestion=""
        if ok
        else "reduce edge_margin (narrow windows want 0.5-0.8mm), lower "
             "sites, or shrink min_ligament — every cell shrinks by "
             "ligament/2 per side and dies when nothing remains",
    )


register_probe("form.min_ligament_ok")(lambda form, ctx: check_min_ligament_ok(form))
register_probe("form.field_cells_present")(lambda form, ctx: check_field_cells_present(form))
