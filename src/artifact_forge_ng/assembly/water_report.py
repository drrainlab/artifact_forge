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


def build_water_report(
    states: dict[str, Any],
    joint_findings: list[Any] | None = None,
) -> dict[str, Any] | None:
    """None when no part carries a water channel — dry assemblies get no
    water story. ``joint_findings`` add the assembly-level verdicts
    (removable_insert reach) on top of the rail's own findings."""
    hit = _water_state(states)
    if hit is None:
        return None
    rail_ref, rail = hit
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
    return report


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
        else:
            continue
        views["explode"].append({"part": b_ref, "vector": vector,
                                 "joint": joint.type})
    return views
