"""VF-4 carrier verification — the row-level support truth, measured in
GLOBAL poses (the per-joint IR sees only relative datum math):

- every water rail in a carried row rests on the profile's sloped support
  line at its own station, on EVERY profile present — no cell hangs on a
  fluid joint;
- adjacent rails march at the module pitch and the stations land under
  their grooves;
- the carrier's global slope matches the fluid cascade, so the profile
  preserves every downhill handover.

The profile part is a REFERENCE PROXY: a standard straight 2020/3030
extrusion mounted at the global row slope, modeled with a sloped top
because AF poses are quarter-turn only. Contact is verified at each
groove's UPSTREAM edge (a flat groove meets a falling line there first);
the growing gap along the span is REPORTED, not failed — anti-slide
clips / pads / full seating are VF-4.1 territory.
"""

from __future__ import annotations

import math
from typing import Any

from ..core.findings import Finding, Level, Status

CONTACT_TOL = 0.4  # groove ceiling vs support line at the station
PITCH_TOL = 0.5
STATION_TOL = 1.5
SLOPE_GRADE_TOL = 0.005  # |tan(profile) - cascade dz/dy|


def _finding(check: str, ok: bool, message: str, *, measured: float | None = None,
             limit: float | None = None, warn: bool = False) -> Finding:
    status = Status.PASS if ok else (Status.WARN if warn else Status.FAIL)
    return Finding(
        check=check, status=status, level=Level.ASSEMBLY, message=message,
        critical=not ok and not warn, measured=measured, limit=limit,
        unit="mm" if measured is not None else "",
    )


def _profile_refs(asm: Any, states: dict[str, Any]) -> list[str]:
    return [
        p.ref for p in asm.parts
        if states.get(p.ref) is not None
        and states[p.ref].form is not None
        and "profile_slope_deg" in states[p.ref].form.frame
        and "profile_len" in states[p.ref].form.frame
    ]


def _rail_refs(asm: Any, states: dict[str, Any]) -> list[str]:
    return [
        p.ref for p in asm.parts
        if states.get(p.ref) is not None
        and getattr(states[p.ref].archetype, "object_class", "") == "water_rail"
    ]


def _top_z_at(state: Any, pose: Any, y_global: float) -> float:
    """The profile's sloped support line in the ROOT frame."""
    f = state.form.frame
    y_local = y_global - pose.translate[1]
    return (pose.translate[2] + f["profile_top_z_low"]
            + (y_local - f["profile_y_low"])
            * math.tan(math.radians(f["profile_slope_deg"])))


def carrier_findings(
    asm: Any, states: dict[str, Any], poses: dict[str, Any]
) -> list[Finding]:
    perch_joints = [j for j in asm.joints if j.type == "profile_perch"]
    if not perch_joints:
        return []  # not a carried assembly — no carrier story to tell
    profiles = _profile_refs(asm, states)
    rails = _rail_refs(asm, states)
    findings: list[Finding] = []

    # -- assembly.row_supported ------------------------------------------------
    problems: list[str] = []
    worst_contact = 0.0
    span_gap = None
    for rail in rails:
        rail_pose = poses.get(rail)
        rail_state = states[rail]
        if rail_pose is None or rail_state.form is None:
            problems.append(f"{rail}: not posed")
            continue
        perched = {j.b_ref for j in perch_joints if j.a_ref == rail}
        missing = [p for p in profiles if p not in perched]
        if missing:
            problems.append(
                f"{rail} is not perched on {', '.join(missing)} — the cell "
                "hangs on its fluid joint, not on the carrier")
            continue
        for joint in (j for j in perch_joints if j.a_ref == rail):
            prof = joint.b_ref
            prof_pose = poses.get(prof)
            if prof_pose is None:
                problems.append(f"{prof}: profile not posed")
                continue
            datum_name = joint.a.split(".", 1)[1]
            datum = rail_state.form.datums.get(datum_name)
            if datum is None:
                # port-id anchor — resolve through the interface entry
                spec = next((s for s in rail_state.archetype.interfaces
                             if s.id == datum_name), None)
                datum = (rail_state.form.datums.get(spec.datum)
                         if spec is not None else None)
            if datum is None:
                problems.append(f"{rail}.{datum_name}: no seat datum")
                continue
            seat = rail_pose.apply(tuple(datum["at"]))
            support = _top_z_at(states[prof], prof_pose, seat[1])
            gap = seat[2] - support
            worst_contact = max(worst_contact, abs(gap))
            if gap < -0.05:
                problems.append(
                    f"{rail} groove PENETRATES the {prof} support line by "
                    f"{-gap:.2f} — slope/station desync")
            elif gap > CONTACT_TOL:
                problems.append(
                    f"{rail} floats {gap:.2f} above {prof} at its station "
                    f"(> {CONTACT_TOL:g}) — the carrier does not carry it")
            # honest span-gap note: a flat groove on a falling line gains
            # this much daylight at its downstream edge (VF-4.1 closes it)
            fr = rail_state.form.frame
            span = fr.get("rail_y1", 0.0) - fr.get("rail_y0", 0.0)
            slope = states[prof].form.frame["profile_slope_deg"]
            span_gap = round(span * math.tan(math.radians(slope)), 2)
    findings.append(_finding(
        "assembly.row_supported",
        not problems,
        (f"{len(rails)} rail(s) rest on {len(profiles)} profile(s) at their "
         f"stations (contact within {worst_contact:.2f}); flat-groove span "
         f"gap {span_gap} at the downstream edge — upstream-edge contact, "
         "anti-slide/full seating deferred to VF-4.1")
        if not problems else "; ".join(problems),
        measured=span_gap, limit=CONTACT_TOL,
    ))

    # -- assembly.row_pitch_aligned ---------------------------------------------
    pitch_problems: list[str] = []
    posed_rails = [(r, poses[r]) for r in rails if poses.get(r) is not None]
    for (r1, p1), (r2, p2) in zip(posed_rails, posed_rails[1:]):
        dy = abs(p1.translate[1] - p2.translate[1])
        fr = states[r1].form.frame
        module = fr.get("rail_y1", 0.0) - fr.get("rail_y0", 0.0)
        if abs(dy - module) > PITCH_TOL:
            pitch_problems.append(
                f"{r1}->{r2} march {dy:.2f} != module {module:g}")
    for joint in perch_joints:
        prof = joint.b_ref
        prof_pose = poses.get(prof)
        rail_pose = poses.get(joint.a_ref)
        if prof_pose is None or rail_pose is None:
            continue
        station_name = joint.b.split(".", 1)[1]
        prof_state = states[prof]
        datum = prof_state.form.datums.get(station_name)
        if datum is None:
            spec = next((s for s in prof_state.archetype.interfaces
                         if s.id == station_name), None)
            datum = (prof_state.form.datums.get(spec.datum)
                     if spec is not None else None)
        if datum is None:
            continue
        station_y = prof_pose.apply(tuple(datum["at"]))[1]
        seat_name = joint.a.split(".", 1)[1]
        rail_state = states[joint.a_ref]
        seat_datum = rail_state.form.datums.get(seat_name)
        if seat_datum is None:
            spec = next((s for s in rail_state.archetype.interfaces
                         if s.id == seat_name), None)
            seat_datum = (rail_state.form.datums.get(spec.datum)
                          if spec is not None else None)
        if seat_datum is None:
            continue
        seat_y = rail_pose.apply(tuple(seat_datum["at"]))[1]
        if abs(station_y - seat_y) > STATION_TOL:
            pitch_problems.append(
                f"{prof} station under {joint.a_ref} off by "
                f"{abs(station_y - seat_y):.2f}")
    findings.append(_finding(
        "assembly.row_pitch_aligned",
        not pitch_problems,
        "rails march at the module pitch, stations land under their grooves"
        if not pitch_problems else "; ".join(pitch_problems),
    ))

    # -- assembly.profile_slope_feeds_downhill ------------------------------------
    slope_problems: list[str] = []
    if len(posed_rails) >= 2:
        (r1, p1), (r2, p2) = posed_rails[0], posed_rails[1]
        dy = p1.translate[1] - p2.translate[1]
        dz = p1.translate[2] - p2.translate[2]
        cascade_grade = dz / dy if abs(dy) > 1e-9 else 0.0
        for prof in profiles:
            grade = math.tan(math.radians(
                states[prof].form.frame["profile_slope_deg"]))
            if abs(grade - cascade_grade) > SLOPE_GRADE_TOL:
                slope_problems.append(
                    f"{prof} grade {grade:.4f} vs cascade {cascade_grade:.4f} "
                    "— the carrier fights the water")
    findings.append(_finding(
        "assembly.profile_slope_feeds_downhill",
        not slope_problems,
        "the carrier's global slope matches the cascade — every downhill "
        "handover is preserved on the profile"
        if not slope_problems else "; ".join(slope_problems),
    ))
    return findings
