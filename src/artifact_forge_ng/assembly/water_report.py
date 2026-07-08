"""The water contract report — the transient-pulse story of a build, told
in numbers derived from frame keys and check verdicts (never re-measured
here): where the water enters, how it falls, where it detaches, and the
two honesty flags (dead pockets, permanent substrate contact).

Also derives the section/exploded VIEW METADATA for the assembly report:
cut planes that show the slope and the seat, and explode vectors read
mechanically off the joint types. Metadata only — rendering is a later
wave.
"""

from __future__ import annotations

from typing import Any

WATER_KEY = "channel_slope_deg"


def _water_state(states: dict[str, Any]) -> tuple[str, Any] | None:
    for ref, state in states.items():
        if state.form is not None and WATER_KEY in state.form.frame:
            return ref, state
    return None


def _rail_cells(states: dict[str, Any]) -> list[tuple[str, Any]]:
    """Every WATER RAIL cell (adapters carry channel keys too — the
    archetype's object_class tells them apart)."""
    return [
        (ref, state) for ref, state in states.items()
        if state.form is not None and WATER_KEY in state.form.frame
        and getattr(state.archetype, "object_class", "") == "water_rail"
    ]


def build_water_report(
    states: dict[str, Any],
    joint_findings: list[Any] | None = None,
    asm: Any = None,
    poses: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """None when no part carries a water channel — dry assemblies get no
    water story. ``joint_findings`` add the assembly-level verdicts
    (removable_insert reach, fluid handovers); ``asm``/``poses`` unlock the
    row-level rollup (VF-3): per-cell drops, handover chain, total drop."""
    hit = _water_state(states)
    if hit is None:
        return None
    cells = _rail_cells(states)
    rail_ref, rail = cells[0] if cells else hit
    f = rail.form.frame

    def passed(check: str) -> bool | None:
        verdicts = [j.status.value == "pass"
                    for j in (joint_findings or []) if j.check == check]
        if verdicts:
            return all(verdicts)
        if rail.report.findings and any(
            fd.check == check for fd in rail.report.findings
        ):
            return rail.report.passed(check)
        return None

    insert = [j for j in (joint_findings or [])
              if j.check == "assembly.removable_insert_ir"]
    report: dict[str, Any] = {
        "mode": "transient_pulse",
        "storage": "forbidden",
        "rail": rail_ref,
        "flow_axis": "Y",
        "inlet_edge": "back (+Y)",
        "outlet_edge": "front (-Y)",
        "channel": {
            "w_mm": round(f["channel_w"], 2),
            "depth_inlet_mm": round(f["channel_top_z"] - f["channel_floor_z_inlet"], 2),
            "depth_outlet_mm": round(f["channel_top_z"] - f["channel_floor_z_outlet"], 2),
            "bottom_r_mm": round(f.get("channel_bottom_r", 0.0), 2),
            "slope_deg": round(f[WATER_KEY], 3),
            "drop_mm": round(
                f["channel_floor_z_inlet"] - f["channel_floor_z_outlet"], 2),
            "floor_margin_mm": round(f.get("channel_floor_margin", 0.0), 2),
        },
        "lap_handover": {
            "lip_len_mm": round(f.get("lap_lip_len", 0.0), 2),
            "lip_t_mm": round(f.get("lap_lip_t", 0.0), 2),
            "receiver_len_mm": round(f.get("lap_pocket_len", 0.0), 2),
            "face_gap_mm": round(f.get("face_gap", 0.0), 2),
            "seam": "controlled open slot — never the primary water path",
        },
        "dead_pockets": _verdict(passed("form.no_standing_water_ir")),
        "permanent_substrate_contact": _contact_verdict(insert),
        "dry_zone_assumptions": [
            "aluminum profile slots verified outside the wet regions "
            "(form.profile_seat_dry_ok)",
        ],
    }
    if insert and insert[0].measured is not None:
        report["contact_window"] = {
            "reach_into_channel_mm": round(insert[0].measured, 2),
            "verdict": "pulse_only" if insert[0].status.value == "pass" else "FAILED",
        }
    if asm is not None:
        row = _row_rollup(states, cells, joint_findings or [], asm, poses or {})
        if row is not None:
            report["row"] = row
    return report


def _row_rollup(
    states: dict[str, Any],
    cells: list[tuple[str, Any]],
    joint_findings: list[Any],
    asm: Any,
    poses: dict[str, Any],
) -> dict[str, Any] | None:
    """The tilted-flush-row story (VF correction): drip handovers at the
    cap and collector, lap-flow handovers between LEVEL modules, and the
    virtual drop under the DECLARED mount — the geometry is horizontal,
    v = z + y*tan(slope). Skipped for single-part builds (no asm) and dry
    assemblies (no water joints)."""
    import math

    lap_joints = [j for j in asm.joints if j.type == "lap_flow_joint"]
    fluid_joints = [j for j in asm.joints if j.type == "fluid_joint"]
    if not lap_joints and not fluid_joints:
        return None

    def findings_for(check: str) -> list[Any]:
        return [j for j in joint_findings if j.check == check]

    handovers: list[dict[str, Any]] = []
    lap_findings = findings_for("assembly.lap_flow_ir")
    for i, joint in enumerate(lap_joints):
        finding = lap_findings[i] if i < len(lap_findings) else None
        handovers.append({
            "type": "lap_flow",
            "from": joint.a_ref,
            "to": joint.b_ref,
            "status": finding.status.value if finding else "unchecked",
            "dz_mm": round(finding.measured, 2)
            if finding and finding.measured is not None else None,
        })
    fluid_findings = findings_for("assembly.fluid_joint_ir")
    for i, joint in enumerate(fluid_joints):
        finding = fluid_findings[i] if i < len(fluid_findings) else None
        handovers.append({
            "type": "drip",
            "from": joint.a_ref,
            "to": joint.b_ref,
            "status": finding.status.value if finding else "unchecked",
            "drop_mm": round(finding.measured, 2)
            if finding and finding.measured is not None else None,
        })

    insert_findings = findings_for("assembly.removable_insert_ir")
    insert_joints = [j for j in asm.joints if j.type == "removable_insert"]
    cell_rows = []
    for ref, state in cells:
        entry: dict[str, Any] = {"ref": ref, "channel": "level"}
        for k, joint in enumerate(insert_joints):
            if joint.a_ref == ref and k < len(insert_findings):
                fi = insert_findings[k]
                entry["cassette_contact"] = (
                    "pulse_only" if fi.status.value == "pass" else "FAILED")
        cell_rows.append(entry)

    mount = getattr(asm, "mount_context", None)
    slope = mount.slope_deg if mount is not None else None
    total_virtual = None
    posed = [(r, poses.get(r)) for r, _ in cells if poses.get(r) is not None]
    if posed and slope is not None:
        grade = math.tan(math.radians(slope))
        posed.sort(key=lambda rp: -rp[1].translate[1])
        (first_ref, p0), (last_ref, p1) = posed[0], posed[-1]
        f0 = states[first_ref].form.frame
        f1 = states[last_ref].form.frame
        v_top = (f0["channel_floor_z_inlet"] + p0.translate[2]
                 + (f0["rail_y1"] + p0.translate[1]) * grade)
        v_bot = (f1["channel_floor_z_outlet"] + p1.translate[2]
                 + (f1["rail_y0"] + p1.translate[1]) * grade)
        total_virtual = round(v_top - v_bot, 2)

    drains = findings_for("assembly.row_drains_under_mount")
    flush = findings_for("assembly.row_flush_aligned")
    leak: bool | None = None
    for ref, state in cells:
        if state.report.findings and any(
                fd.check == "form.lap_slot_leak_path_controlled"
                for fd in state.report.findings):
            ok = state.report.passed("form.lap_slot_leak_path_controlled")
            leak = ok if leak is None else (leak and ok)
    orphan = findings_for("assembly.no_orphan_ports")
    saddles = findings_for("assembly.saddle_hang_ir")
    meta = getattr(asm, "meta", {}) or {}
    return {
        "kind": meta.get("row_kind", "tilted_flush_row"),
        "slope_source": ("mounted_profile" if mount is not None
                         else "UNDECLARED — no mount_context"),
        "slope_deg": slope,
        "modules_flush": bool(flush) and all(
            f.status.value == "pass" for f in flush),
        "stair_step": False,
        "cells": len(cells),
        "cell_details": cell_rows,
        "total_virtual_drop_mm": total_virtual,
        "handovers": handovers,
        "standing_water_under_mount": (
            "none" if drains and all(d.status.value == "pass" for d in drains)
            else "NOT PROVEN" if drains else "unchecked"),
        "lap_seam_leak": ("controlled" if leak else
                          "UNCONTROLLED" if leak is False else "unchecked"),
        "drips_clear_of": ["profiles", "magnets", "dry_zones"],
        "saddle_mounts": [
            {"status": s.status.value, "note": s.message} for s in saddles
        ],
        "orphan_fluid_ports": (
            "none" if orphan and all(o.status.value == "pass" for o in orphan)
            else "PRESENT" if orphan else "unchecked"
        ),
    }


def _verdict(ok: bool | None) -> str:
    if ok is None:
        return "unchecked"
    return "none found" if ok else "PRESENT"


def _contact_verdict(insert_findings: list[Any]) -> str | bool:
    if not insert_findings:
        return "unchecked (no cassette seated)"
    return not all(j.status.value == "pass" for j in insert_findings)


def build_views(
    asm: Any, states: dict[str, Any], poses: dict[str, Any]
) -> dict[str, Any] | None:
    """Section planes + explode vectors, derived mechanically: the flow
    section shows the level channel and the lap handover, the cross
    section shows the U and the seat; explode direction comes from the
    joint type (inserts and snaps stack +Z, line joints spread along X,
    lap neighbours pull apart along the flow)."""
    hit = _water_state(states)
    if hit is None:
        return None
    _, rail = hit
    f = rail.form.frame
    views: dict[str, Any] = {
        "section_planes": [
            {"name": "flow_section",
             "origin": [round(f["channel_center_x"], 2), 0.0, 0.0],
             "normal": [1, 0, 0],
             "shows": "level channel, lap lip and receiver, feed drop"},
            {"name": "cross_section",
             "origin": [0.0, 0.0, 0.0],
             "normal": [0, 1, 0],
             "shows": "U-profile, cassette seat, contact window reach"},
        ],
        "explode": [],
    }
    lift = f.get("body_h", 30.0) + 30.0
    for joint in asm.joints:
        b_ref = joint.b_ref
        pose = poses.get(b_ref)
        if pose is None:
            continue
        if joint.type == "removable_insert":
            vector = [0.0, 0.0, lift]
        elif joint.type == "snap_joint":
            vector = [0.0, 0.0, lift + 40.0]
        elif joint.type == "tongue_groove":
            sign = 1.0 if pose.translate[0] >= 0 else -1.0
            vector = [sign * f.get("module_pitch", 250.0) / 2.0, 0.0, 0.0]
        elif joint.type == "fluid_joint":
            # pull the downstream part further along the flow axis
            vector = [0.0, -60.0, -10.0]
        elif joint.type == "lap_flow_joint":
            # flush neighbours separate by a straight pull along the flow
            vector = [0.0, -60.0, 0.0]
        else:
            continue  # auxiliary joints (saddle_hang) explode nothing
        views["explode"].append({"part": b_ref, "vector": vector,
                                 "joint": joint.type})
    return views
