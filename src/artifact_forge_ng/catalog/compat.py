"""The DERIVED compatibility matrix (wave A1) — `forge compat`.

There is no hand-written matrix by design: compatibility is computed from
the archetypes' declared interfaces with the same ``mate_problems`` rule
set the assembly validator uses. What this report cannot know — real
dimensional fits — the joint IR checks measure per assembly; the matrix
answers the CATALOG question: which parts are even candidates to mate,
port by port, and why the rest are not.
"""

from __future__ import annotations

from typing import Any

from ..product.interfaces import INTERFACE_TYPES, mate_problems, types_mate
from .loader import Catalog, load_catalog


def compat_matrix(catalog: Catalog | None = None) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    ports = [
        (spec.id, spec.object_class, iface)
        for spec in catalog.archetypes.values()
        for iface in spec.interfaces
    ]
    mates: list[dict[str, Any]] = []
    # Same-archetype pairs stay in: two INSTANCES of one part may mate
    # (water_rail line_east <-> line_west is the two-rail line).
    for i, (aid, aclass, ai) in enumerate(ports):
        for bid, bclass, bi in ports[i + 1:]:
            if not types_mate(ai.type, bi.type):
                continue
            problems = mate_problems(ai, bi, (aid, aclass), (bid, bclass))
            mates.append({
                "type": ai.type,
                "a": f"{aid}.{ai.id}",
                "b": f"{bid}.{bi.id}",
                "compatible": not problems,
                "problems": problems,
            })
    orphan_types = sorted(
        t for t in INTERFACE_TYPES
        if not any(p[2].type == t for p in ports)
    )
    # v2: required ports must have at least one compatible counterpart
    # SOMEWHERE in the catalog — a standard with a single implementor is
    # a stranded standard.
    matable = {m["a"] for m in mates if m["compatible"]}
    matable |= {m["b"] for m in mates if m["compatible"]}
    stranded = [
        f"{aid}.{i.id}" for aid, _, i in ports
        if i.assembly_role == "required" and f"{aid}.{i.id}" not in matable
    ]
    return {
        "ports": [
            {"part": aid, "id": i.id, "type": i.type, "gender": i.gender,
             "role": i.assembly_role,
             "frame": (f"{i.frame.normal}/{i.frame.up}"
                       + (f"/{i.frame.axis}" if i.frame.axis else "")
                       if i.frame else None)}
            for aid, _, i in ports
        ],
        "mates": mates,
        "stranded_required_ports": stranded,
        "unused_interface_types": orphan_types,
    }


def render_compat(matrix: dict[str, Any]) -> str:
    lines = [f"declared ports: {len(matrix['ports'])}"]
    for p in matrix["ports"]:
        lines.append(
            f"  {p['part'] + '.' + p['id']:<44} {p['type']:<26} "
            f"{p['gender']:<8} {p['role']:<9} "
            f"{p['frame'] or 'NO FRAME'}")
    ok = [m for m in matrix["mates"] if m["compatible"]]
    bad = [m for m in matrix["mates"] if not m["compatible"]]
    lines.append(f"\ncompatible mates: {len(ok)}")
    for m in ok:
        lines.append(f"  [{m['type']}] {m['a']}  <->  {m['b']}")
    if bad:
        lines.append(f"\nsame-type but INCOMPATIBLE: {len(bad)}")
        for m in bad:
            lines.append(f"  [{m['type']}] {m['a']} x {m['b']}: "
                         + "; ".join(m["problems"]))
    if matrix.get("stranded_required_ports"):
        lines.append("\nrequired ports with NO compatible counterpart in "
                     "the catalog:")
        for sp in matrix["stranded_required_ports"]:
            lines.append(f"  !! {sp}")
    if matrix["unused_interface_types"]:
        lines.append("\ninterface types with no declared ports yet: "
                     + ", ".join(matrix["unused_interface_types"]))
    return "\n".join(lines)
