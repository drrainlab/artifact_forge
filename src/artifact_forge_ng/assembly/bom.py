"""BOM-lite (A2-lite) — a DERIVED build package summary, never a declared
one: printed parts aggregate from the assembly's own part list, hardware
lines derive from what the design actually references (hose ports carry a
tube spec, screw joints carry screws, profile slots reference aluminum
rail), and the print block rolls up materials and bed needs.

Deliberately minimal: no HardwareSpec class, no catalog/data/hardware/ —
those names belong to wave A2 (docs/ROADMAP.md). VF-3 needed a bill of
materials, not an ontology; when A2 lands, these derivations become its
first clients.
"""

from __future__ import annotations

from typing import Any

from ..core.fasteners import screw_spec


def build_bom(asm: Any, states: dict[str, Any], catalog: Any) -> dict[str, Any]:
    printed: dict[str, dict[str, Any]] = {}
    reference_parts: list[tuple[str, Any]] = []
    for part in asm.parts:
        ref = part.ref
        state = states.get(ref)
        if state is None:
            continue
        if state.instance.manufacturing.process == "reference":
            # external hardware modeled as reference geometry — never a
            # printed part; it becomes a hardware line below
            reference_parts.append((ref, state))
            continue
        aid = state.archetype.id
        entry = printed.setdefault(aid, {
            "archetype": aid,
            "object_class": state.archetype.object_class,
            "qty": 0,
            "refs": [],
            "material": state.instance.manufacturing.material,
        })
        entry["qty"] += 1
        entry["refs"].append(ref)

    hardware: list[dict[str, Any]] = []

    # reference geometry -> hardware lines (STANDARD parts, cut to length;
    # the sloped model face is a reference PROXY of a straight profile
    # mounted at the global row slope, never a wedge-cut part)
    ref_lines: dict[str, dict[str, Any]] = {}
    for ref, state in reference_parts:
        fr = state.form.frame if state.form is not None else {}
        size = fr.get("profile_size")
        if size is not None:
            key = f"{int(size)}{int(size)}"
            line = ref_lines.setdefault(key, {
                "item": f"aluminum profile {key}, standard straight, cut to length",
                "qty": 0,
                "length_mm": round(fr.get("profile_len", 0.0), 1),
                "note": (
                    f"mounted at global row slope "
                    f"{fr.get('profile_slope_deg', 0.0):g} deg (frame's "
                    "responsibility); the sloped model face is a reference "
                    "proxy, NOT a wedge-cut part; anti-slide clips/stops — "
                    "VF-4.1"
                ),
            })
            line["qty"] += 1
        else:
            ref_lines.setdefault(ref, {
                "item": f"reference hardware: {state.archetype.id}",
                "qty": 1,
                "note": "external part — spec external",
            })
    hardware.extend(ref_lines.values())

    # screws: derived from screw joints, never declared
    screw_lines: dict[str, int] = {}
    for joint in asm.joints:
        if joint.type != "screw_joint":
            continue
        screw = str(joint.params.get("screw", "M4"))
        count = int(float(joint.params.get("count", 2)))
        screw_lines[screw] = screw_lines.get(screw, 0) + count
    for screw, qty in sorted(screw_lines.items()):
        spec = screw_spec(screw)
        hardware.append({
            "item": f"{screw} screw",
            "qty": qty,
            "note": f"head d {spec['head']:g} mm; length per joint stack",
        })

    # silicone tubing: derived from declared hose ports
    tube_ports = 0
    tube_od = None
    for ref, state in states.items():
        for spec in getattr(state.archetype, "interfaces", []):
            if spec.type == "hose_port":
                tube_ports += 1
                od = state.resolved.context.get("tube_od")
                if od is not None:
                    tube_od = od
    if tube_ports:
        hardware.append({
            "item": "silicone tube",
            "qty": tube_ports,
            "note": (
                f"push-in, OD {tube_od:g} mm (6 mm ID typical); one per "
                "hose port (feed + drain); lengths external"
                if tube_od is not None else "one per hose port; spec external"
            ),
        })

    # aluminum profile slot heuristic — ONLY when no reference profile
    # parts exist in the assembly (otherwise the reference geometry above
    # already carries the real profile line; double counting is a lie)
    if not ref_lines:
        profiles: dict[str, int] = {}
        for ref, state in states.items():
            if state.instance.manufacturing.process == "reference":
                continue
            size = (state.form.frame.get("profile_size")
                    if state.form is not None else None)
            if size:
                key = f"{int(size)}{int(size)}"
                profiles[key] = profiles.get(key, 0) + 2  # two slots per module
        for key, slots in sorted(profiles.items()):
            hardware.append({
                "item": f"aluminum profile {key}",
                "qty": slots,
                "note": "profile seats per module (2 rails under each); "
                        "lengths and rack layout external — the row is a fluid "
                        "cascade proof, not the final rack (VF-4/VF-5)",
            })

    fdm_states = [s for s in states.values()
                  if s.instance.manufacturing.process != "reference"]
    beds = [s.instance.manufacturing.bed for s in fdm_states]
    bed_min = [max(b[i] for b in beds) for i in range(3)] if beds else None
    return {
        "printed_parts": sorted(printed.values(), key=lambda e: e["archetype"]),
        "hardware": hardware,
        "print": {
            "materials": sorted({s.instance.manufacturing.material
                                 for s in fdm_states}),
            "bed_min_mm": bed_min,
            "support_policy": sorted({s.instance.manufacturing.support_policy
                                      for s in fdm_states}),
        },
    }
