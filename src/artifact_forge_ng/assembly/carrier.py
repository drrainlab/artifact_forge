"""VF-correction row verification — the tilted-flush-row truth, measured
in GLOBAL poses (the per-joint IR sees only relative datum math):

- the modules form ONE plane: dZ = 0, marching at module_w + face_gap
  (assembly.row_flush_aligned);
- the whole water path descends monotonically under the DECLARED mount
  slope — no mount_context, an out-of-band slope or a reversed row FAILS
  (assembly.row_drains_under_mount); the rails themselves are level, the
  mount is the pump;
- every rail rests on every STRAIGHT profile over its full groove length —
  span gap ZERO, a checked contract, not a note
  (assembly.profile_support_full_length);
- optional alignment magnets face each other across every lap seam
  (assembly.magnet_alignment_ok) — alignment only, never seal or support;
- every cassette stays hand-removable with the row mounted
  (assembly.cassettes_removable_under_mount) — a rollup note over the
  removable_insert verdicts.

The profile part is reference geometry of a STANDARD STRAIGHT 2020/3030
extrusion, cut to length, modeled straight and horizontal — the physical
slope lives ONLY in the assembly's mount_context, never in the geometry
and never in a pose.
"""

from __future__ import annotations

import math
from typing import Any

from ..core.findings import Finding, Level, Status

#: The operational mount band — schema allows 0..3, operation demands this.
MOUNT_SLOPE_BAND = (1.0, 2.0)
FLUSH_DZ_TOL = 0.1
FLUSH_PITCH_TOL = 0.3
SEAT_CONTACT_TOL = 0.3   # groove ceiling vs straight profile top
MAGNET_COAX_TOL = 0.5
VIRTUAL_DESCENT_TOL = 0.05


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
        and "profile_len" in states[p.ref].form.frame
    ]


def _rail_refs(asm: Any, states: dict[str, Any]) -> list[str]:
    return [
        p.ref for p in asm.parts
        if states.get(p.ref) is not None
        and getattr(states[p.ref].archetype, "object_class", "") == "water_rail"
    ]


def _datum_of(state: Any, name: str):
    datum = state.form.datums.get(name)
    if datum is None:
        spec = next((s for s in state.archetype.interfaces if s.id == name), None)
        datum = state.form.datums.get(spec.datum) if spec is not None else None
    return datum


def carrier_findings(
    asm: Any, states: dict[str, Any], poses: dict[str, Any],
    joint_findings: list[Finding] | None = None,
) -> list[Finding]:
    lap_joints = [j for j in asm.joints if j.type == "lap_flow_joint"]
    perch_joints = [j for j in asm.joints if j.type == "profile_perch"]
    if not lap_joints and not perch_joints:
        return []  # not a row — no row story to tell
    rails = _rail_refs(asm, states)
    profiles = _profile_refs(asm, states)
    # upstream -> downstream: the JOINT CHAIN is the truth (a hands to b).
    # Ordering by pose would silently forgive a row built backwards —
    # exactly the defect row_drains_under_mount must catch.
    downstream_of = {j.a_ref: j.b_ref for j in lap_joints}
    receivers = {j.b_ref for j in lap_joints}
    order: list[str] = []
    for head in [r for r in rails if r not in receivers] or rails[:1]:
        ref = head
        while ref in states and ref not in order:
            order.append(ref)
            ref = downstream_of.get(ref, "")
    order.extend(r for r in rails if r not in order)
    posed_rails = [(r, poses[r]) for r in order
                   if poses.get(r) is not None and states[r].form is not None]
    findings: list[Finding] = []

    findings.append(_row_flush_aligned(posed_rails, states))
    findings.append(_row_drains_under_mount(asm, states, posed_rails, poses))
    if perch_joints:
        findings.append(_profile_support_full_length(
            asm, states, poses, perch_joints, rails, profiles))
    findings.append(_magnet_alignment(lap_joints, states, poses))
    if any(j.type == "removable_insert" for j in asm.joints):
        findings.append(_cassettes_removable(asm, joint_findings or []))
    return findings


# -- assembly.row_flush_aligned -------------------------------------------------


def _row_flush_aligned(posed_rails, states) -> Finding:
    check = "assembly.row_flush_aligned"
    if len(posed_rails) < 2:
        return _finding(check, True, "single module — trivially flush")
    problems: list[str] = []
    worst_dz = 0.0
    for (r1, p1), (r2, p2) in zip(posed_rails, posed_rails[1:]):
        dz = p2.translate[2] - p1.translate[2]
        worst_dz = max(worst_dz, abs(dz))
        if abs(dz) > FLUSH_DZ_TOL:
            problems.append(
                f"{r1}->{r2} dZ = {dz:+.2f} — a stair step; flush rows live "
                "in ONE plane")
        fr = states[r1].form.frame
        want = fr.get("flush_pitch",
                      (fr.get("rail_y1", 0.0) - fr.get("rail_y0", 0.0))
                      + fr.get("face_gap", 0.0))
        dy = p1.translate[1] - p2.translate[1]
        if abs(dy - want) > FLUSH_PITCH_TOL:
            problems.append(
                f"{r1}->{r2} march {dy:.2f} != flush pitch {want:g} "
                "(module_w + face_gap)")
    return _finding(
        check, not problems,
        f"{len(posed_rails)} modules in one plane (worst dZ {worst_dz:.2f}), "
        "marching at module_w + face_gap"
        if not problems else "; ".join(problems),
        measured=worst_dz, limit=FLUSH_DZ_TOL,
    )


# -- assembly.row_drains_under_mount ---------------------------------------------


def _row_drains_under_mount(asm, states, posed_rails, poses) -> Finding:
    """Virtual heights v = z + y*tan(slope): under the DECLARED mount the
    whole floor path must descend monotonically from the first inlet to
    the last outlet. The rails are level by design — without the mount
    there IS no drainage, so a missing/out-of-band mount_context FAILS."""
    check = "assembly.row_drains_under_mount"
    mount = getattr(asm, "mount_context", None)
    if not posed_rails:
        return _finding(check, False, "no posed water rails — nothing drains")
    if mount is None:
        return _finding(
            check, False,
            "no mount_context: a constant-depth row drains ONLY when the "
            "assembly declares its mounted slope (tilted_flush_row, "
            f"{MOUNT_SLOPE_BAND[0]:g}..{MOUNT_SLOPE_BAND[1]:g} deg)")
    slope = mount.slope_deg
    if not (MOUNT_SLOPE_BAND[0] - 1e-9 <= slope <= MOUNT_SLOPE_BAND[1] + 1e-9):
        return _finding(
            check, False,
            f"mount slope {slope:g} outside the operational band "
            f"{MOUNT_SLOPE_BAND[0]:g}..{MOUNT_SLOPE_BAND[1]:g} — too flat "
            "leaves films standing, too steep strands the substrate",
            measured=slope, limit=MOUNT_SLOPE_BAND[1])
    grade = math.tan(math.radians(slope))
    # walk the floor path: inlet and outlet corner of every rail, in order
    path: list[tuple[str, float, float]] = []
    for ref, pose in posed_rails:
        fr = states[ref].form.frame
        for label, y_key, z_key in (
                ("inlet", "rail_y1", "channel_floor_z_inlet"),
                ("outlet", "rail_y0", "channel_floor_z_outlet")):
            y = fr[y_key] + pose.translate[1]
            z = fr[z_key] + pose.translate[2]
            path.append((f"{ref}.{label}", y, z))
    problems: list[str] = []
    virtual = [(name, z + y * grade) for name, y, z in path]
    for (n1, v1), (n2, v2) in zip(virtual, virtual[1:]):
        if v2 > v1 + VIRTUAL_DESCENT_TOL:
            problems.append(
                f"{n1} -> {n2} climbs {v2 - v1:.2f} under the mount — the "
                "row is reversed or stepped against the slope")
    total = virtual[0][1] - virtual[-1][1] if virtual else 0.0
    if not problems and total <= 0.0:
        problems.append("zero virtual drop across the row — nothing drains")
    return _finding(
        check, not problems,
        f"mounted at {slope:g} deg the floor path falls {total:.2f} "
        f"monotonically ({mount.slope_source}) — no standing water under "
        "the mount"
        if not problems else "; ".join(problems),
        measured=total,
    )


# -- assembly.profile_support_full_length -----------------------------------------


def _profile_support_full_length(
    asm, states, poses, perch_joints, rails, profiles
) -> Finding:
    """Straight profile + level grooves = FULL seating: every rail perched
    on every profile, groove ceilings coplanar with the flat profile top,
    span gap ZERO — a checked contract now, not a VF-4 honesty note."""
    check = "assembly.profile_support_full_length"
    problems: list[str] = []
    worst = 0.0
    for prof in profiles:
        fr = states[prof].form.frame
        slope = fr.get("profile_slope_deg", 0.0)
        if abs(slope) > 1e-6:
            problems.append(
                f"{prof} models a {slope:g} deg top — the corrected carrier "
                "is a STANDARD STRAIGHT profile; the slope belongs to "
                "mount_context")
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
                "hangs on its water joints, not on the carrier")
            continue
        for joint in (j for j in perch_joints if j.a_ref == rail):
            prof = joint.b_ref
            prof_pose = poses.get(prof)
            if prof_pose is None:
                problems.append(f"{prof}: profile not posed")
                continue
            datum = _datum_of(rail_state, joint.a.split(".", 1)[1])
            if datum is None:
                problems.append(f"{joint.a}: no seat datum")
                continue
            seat = rail_pose.apply(tuple(datum["at"]))
            pf = states[prof].form.frame
            top = prof_pose.translate[2] + pf.get(
                "profile_top_z_low", pf.get("profile_size", 20.0))
            gap = seat[2] - top
            worst = max(worst, abs(gap))
            if abs(gap) > SEAT_CONTACT_TOL:
                problems.append(
                    f"{rail} groove vs {prof} top off by {gap:+.2f} "
                    f"(|gap| <= {SEAT_CONTACT_TOL:g}) — full seating broken")
    return _finding(
        check, not problems,
        f"{len(rails)} rail(s) seated FULL LENGTH on {len(profiles)} straight "
        f"profile(s) (worst contact {worst:.2f}); span gap 0 by construction",
        measured=worst, limit=SEAT_CONTACT_TOL,
    ) if not problems else _finding(check, False, "; ".join(problems),
                                    measured=worst, limit=SEAT_CONTACT_TOL)


# -- assembly.magnet_alignment_ok --------------------------------------------------


def _magnet_alignment(lap_joints, states, poses) -> Finding:
    check = "assembly.magnet_alignment_ok"
    pairs = 0
    problems: list[str] = []
    for joint in lap_joints:
        sa, sb = states.get(joint.a_ref), states.get(joint.b_ref)
        if sa is None or sb is None or sa.form is None or sb.form is None:
            continue
        fa, fb = sa.form.frame, sb.form.frame
        if not fa.get("magnet_count") or not fb.get("magnet_count"):
            continue
        pa, pb = poses.get(joint.a_ref), poses.get(joint.b_ref)
        if pa is None or pb is None:
            continue
        for sign in (1.0, -1.0):
            a_pt = pa.apply((sign * fa["magnet_x_offset"], fa["rail_y0"],
                             fa["magnet_z"]))
            b_pt = pb.apply((sign * fb["magnet_x_offset"], fb["rail_y1"],
                             fb["magnet_z"]))
            pairs += 1
            dx, dz = abs(a_pt[0] - b_pt[0]), abs(a_pt[2] - b_pt[2])
            if dx > MAGNET_COAX_TOL or dz > MAGNET_COAX_TOL:
                problems.append(
                    f"{joint.a_ref}->{joint.b_ref} magnet pair at x "
                    f"{sign * fa['magnet_x_offset']:+g} off by "
                    f"dx={dx:.2f}/dz={dz:.2f}")
    if pairs == 0:
        return _finding(check, True,
                        "no magnets on the mated faces — nothing to align")
    return _finding(
        check, not problems,
        f"{pairs} magnet pair(s) coaxial across the lap seams — alignment "
        "only, never a seal, never a support"
        if not problems else "; ".join(problems),
        limit=MAGNET_COAX_TOL,
    )


# -- assembly.cassettes_removable_under_mount --------------------------------------


def _cassettes_removable(asm, joint_findings: list[Finding]) -> Finding:
    """Rollup note: the insert joints already verified drop-in clearance
    and lift access; at <= 2 deg the vertical lift is unchanged (cos 2 deg
    = 0.9994), so mounted removal holds exactly when the inserts pass."""
    check = "assembly.cassettes_removable_under_mount"
    inserts = [f for f in joint_findings
               if f.check == "assembly.removable_insert_ir"]
    mount = getattr(asm, "mount_context", None)
    slope = mount.slope_deg if mount is not None else 0.0
    if not inserts:
        return _finding(check, True, "no cassettes seated — nothing to remove")
    bad = [f for f in inserts if f.status is not Status.PASS]
    return _finding(
        check, not bad,
        f"{len(inserts)} cassette(s) hand-removable at the {slope:g} deg "
        "mount — straight vertical lift, clearances unchanged"
        if not bad else
        f"{len(bad)} cassette insert(s) failed — not removable, mounted or not",
    )
