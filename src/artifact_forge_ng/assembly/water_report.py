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
        "overflow": {
            "lip_r_assumed_mm": round(f.get("lip_r_assumed", 0.0), 2),
            "lip_h_mm": round(f.get("lip_h", 0.0), 2),
            "air_gap_mm": round(f.get("air_gap", 0.0), 2),
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
    """The VF-3 row story: the handover chain in joint order, per-cell
    drops, the global top-to-bottom drop through the cascade, adapter
    verdicts and the orphan-port rollup. Skipped for single-part builds
    (no asm) and non-fluid assemblies (no fluid joints)."""
    fluid_joints = [j for j in asm.joints if j.type == "fluid_joint"]
    if not fluid_joints:
        return None
    fluid_findings = [j for j in joint_findings
                      if j.check == "assembly.fluid_joint_ir"]
    handovers = []
    for i, joint in enumerate(fluid_joints):
        finding = fluid_findings[i] if i < len(fluid_findings) else None
        handovers.append({
            "from": joint.a_ref,
            "to": joint.b_ref,
            "status": finding.status.value if finding else "unchecked",
            "drop_mm": round(finding.measured, 2)
            if finding and finding.measured is not None else None,
        })
    insert_findings = [j for j in joint_findings
                       if j.check == "assembly.removable_insert_ir"]
    insert_joints = [j for j in asm.joints if j.type == "removable_insert"]
    cell_rows = []
    for ref, state in cells:
        fr = state.form.frame
        entry: dict[str, Any] = {
            "ref": ref,
            "slope_deg": round(fr[WATER_KEY], 3),
            "drop_mm": round(
                fr["channel_floor_z_inlet"] - fr["channel_floor_z_outlet"], 2),
        }
        for k, joint in enumerate(insert_joints):
            if joint.a_ref == ref and k < len(insert_findings):
                fi = insert_findings[k]
                entry["cassette_contact"] = (
                    "pulse_only" if fi.status.value == "pass" else "FAILED")
        cell_rows.append(entry)
    # global drop through the cascade: first cell's inlet floor down to the
    # last cell's outlet floor, both in the ROOT frame via the poses
    total = None
    chain_refs = [r for r, _ in cells]
    if chain_refs and poses:
        def gz(ref: str, key: str) -> float | None:
            pose = poses.get(ref)
            state = states[ref]
            if pose is None or state.form is None:
                return None
            return state.form.frame[key] + pose.translate[2]

        top = gz(chain_refs[0], "channel_floor_z_inlet")
        bottom = gz(chain_refs[-1], "channel_floor_z_outlet")
        if top is not None and bottom is not None:
            total = round(top - bottom, 2)
    orphan = [j for j in joint_findings
              if j.check == "assembly.no_orphan_ports"]
    saddles = [j for j in joint_findings
               if j.check == "assembly.saddle_hang_ir"]
    meta = getattr(asm, "meta", {}) or {}
    return {
        "kind": meta.get("row_kind", "fluid_cascade"),
        "z_step_policy": "datum_handover",
        "rack_mounting": "deferred",
        "cells": len(cells),
        "cell_details": cell_rows,
        "total_drop_mm": total,
        "handovers": handovers,
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
    section shows the slope, the cross section shows the U and the seat;
    explode direction comes from the joint type (inserts and snaps stack
    +Z, line joints spread along X)."""
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
             "shows": "channel slope, overflow lip, air gap"},
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
        else:
            continue  # auxiliary joints (saddle_hang) explode nothing
        views["explode"].append({"part": b_ref, "vector": vector,
                                 "joint": joint.type})
    return views
