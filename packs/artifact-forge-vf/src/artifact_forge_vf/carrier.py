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

from artifact_forge_ng.core.findings import Finding, Level, Status

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
    if not rails:
        # a lone profile_perch on a non-VF assembly (e.g. a workshop
        # station) is judged by its own ir_check; without water rails
        # there is no row-drainage story to tell — failing "nothing
        # drains" on a dry assembly would be a false witness
        return []
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
    collector = next(
        (p.ref for p in asm.parts
         if states.get(p.ref) is not None and states[p.ref].form is not None
         and getattr(states[p.ref].archetype, "object_class", "") == "water_collector"),
        None)
    if collector is not None and posed_rails:
        findings.extend(_collector_capture(
            collector, posed_rails[-1][0], states, poses))
        findings.extend(_endcap_dock(
            collector, posed_rails[-1][0], "front", states, poses))
    # inlet cap docks onto the FIRST rail's back wall top (VF-6)
    cap = next(
        (p.ref for p in asm.parts
         if states.get(p.ref) is not None and states[p.ref].form is not None
         and getattr(states[p.ref].archetype, "object_class", "")
         == "water_inlet_cap"),
        None)
    if cap is not None and posed_rails:
        findings.extend(_endcap_dock(
            cap, posed_rails[0][0], "back", states, poses))
        findings.extend(_cap_chute_drains_under_mount(asm, cap, states, poses))
    return findings


# -- assembly.cap_chute_drains_under_mount ----------------------------------------


def _cap_chute_drains_under_mount(
    asm: Any, cap_ref: str, states: dict[str, Any], poses: dict[str, Any],
) -> list[Finding]:
    """VF-9.2: the cap's open chute has a LEVEL floor — it drains toward the
    drip tip only because the mounted row is tilted. Verify it IN THE ASSEMBLED
    POSE, not in cap-local coordinates: virtual heights v = z + y*tan(slope) of
    the chute's uphill end and its tip — the uphill end must sit higher, so the
    film runs to the nose and drips off. Emitted only for a posed chute cap in
    a row with a declared mount."""
    check = "assembly.cap_chute_drains_under_mount"
    st, pose = states.get(cap_ref), poses.get(cap_ref)
    if st is None or st.form is None or pose is None:
        return []
    f = st.form.frame
    if "chute_tip_y" not in f:
        return []  # not a chute cap — nothing to verify
    mount = getattr(asm, "mount_context", None)
    if mount is None:
        return [_finding(
            check, False,
            "the cap's level chute drains only under the row mount — declare "
            "mount_context for the row")]
    grade = math.tan(math.radians(mount.slope_deg))
    z_floor = f["channel_floor_z_outlet"]
    up = pose.apply((0.0, f.get("chute_uphill_y", 0.0), z_floor))
    tip = pose.apply((0.0, f["chute_tip_y"], z_floor))
    v_up = up[2] + up[1] * grade
    v_tip = tip[2] + tip[1] * grade
    drop = v_up - v_tip
    ok = drop > 1e-3
    return [_finding(
        check, ok,
        f"the chute floor descends {drop:.2f} virtual mm toward the drip tip "
        f"under the {mount.slope_deg:g} deg mount — the level trough drains"
        if ok else
        f"the chute floor does NOT descend toward the tip under the mount "
        f"(virtual drop {drop:.2f}) — water would sit in the trough",
        measured=drop, limit=0.0,
    )]


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


# -- VF-4.1: the collector is an END RECEIVER for the final lap lip --------------

CAPTURE_TIP_MARGIN = 2.0   # lip tip to the apron wall, in the pose
CAPTURE_MIN_DEPTH = 1.0    # the tip must really be inside the mouth
MOUTH_SIDE_MARGIN = 1.4    # mouth over the posed lip, per side
LIFT_WINDOW = 15.0         # clear vertical exit over the captured lip


def _collector_capture(
    coll_ref: str, final_rail: str, states: dict[str, Any],
    poses: dict[str, Any],
) -> list[Finding]:
    """Three pose truths: the final lip tip sits INSIDE the receiver
    volume, the mouth envelopes the lip across X, and nothing of the
    collector roofs the captured lip — it lifts straight off."""
    out: list[Finding] = []
    coll_pose, rail_pose = poses.get(coll_ref), poses.get(final_rail)
    coll, rail = states[coll_ref], states[final_rail]
    if coll_pose is None or rail_pose is None:
        return [_finding("assembly.collector_captures_drain_edge", False,
                         "collector or final rail not posed")]
    cf, rf = coll.form.frame, rail.form.frame
    needed_c = ("receiver_capture_depth", "receiver_cheek_x0",
                "receiver_apron_z", "handover_dz")
    needed_r = ("lap_lip_tip_y", "lap_lip_w", "lap_lip_t",
                "channel_floor_z_outlet")
    missing = [k for k in needed_c if k not in cf]
    missing += [f"rail:{k}" for k in needed_r if k not in rf]
    if missing:
        return [_finding("assembly.collector_captures_drain_edge", False,
                         f"receiver/lap frame keys missing: {', '.join(missing)}")]

    tip = rail_pose.apply((0.0, rf["lap_lip_tip_y"],
                           rf["channel_floor_z_outlet"] - rf["lap_lip_t"]))
    face_y = coll_pose.translate[1]              # collector local y=0 plane
    handover_z = coll_pose.translate[2] + cf["handover_dz"]
    floor_z = handover_z - coll.form.frame.get("hang_drop", 0.0) * 0.0 - (
        cf.get("receiver_apron_z", 3.0) + 0.0)   # placeholder, refined below
    # tray floor at the catch: design -catch_fall below the handover plane
    catch_fall = coll.form.params.get("catch_fall", 8.5)
    floor_z = handover_z - catch_fall
    rim_z = handover_z + cf["receiver_apron_z"]

    depth = face_y - tip[1]
    problems: list[str] = []
    if not (CAPTURE_MIN_DEPTH <= depth <= cf["receiver_capture_depth"]
            - CAPTURE_TIP_MARGIN + 1e-6):
        problems.append(
            f"lip tip lands {depth:.2f} into the {cf['receiver_capture_depth']:g} "
            f"mouth (needs {CAPTURE_MIN_DEPTH:g}..capture-{CAPTURE_TIP_MARGIN:g})")
    if not (floor_z + 2.0 <= tip[2] <= rim_z + 0.1):
        problems.append(
            f"lip tip z {tip[2]:.2f} outside the receiver throat "
            f"({floor_z + 2.0:.2f}..{rim_z:.2f})")
    if abs(tip[0] - coll_pose.translate[0]) > 1.0:
        problems.append(
            f"lip tip {abs(tip[0] - coll_pose.translate[0]):.2f} off the "
            "mouth centerline")
    out.append(_finding(
        "assembly.collector_captures_drain_edge", not problems,
        f"the final lip tip sits {depth:.1f} inside the mouth, "
        f"{tip[2] - floor_z:.1f} above the tray floor — an end receiver, "
        "not a part standing nearby"
        if not problems else "; ".join(problems),
        measured=depth, limit=cf["receiver_capture_depth"],
    ))

    # mouth envelopes the lip across X
    dx = abs(rail_pose.translate[0] - coll_pose.translate[0])
    side = cf["receiver_cheek_x0"] - (dx + rf["lap_lip_w"] / 2.0)
    out.append(_finding(
        "assembly.collector_mouth_envelopes_outlet_lip",
        side >= MOUTH_SIDE_MARGIN - 1e-6,
        f"mouth envelopes the posed lip with {side:.2f} per side"
        if side >= MOUTH_SIDE_MARGIN - 1e-6 else
        f"mouth margin {side:.2f} < {MOUTH_SIDE_MARGIN:g} per side — the lip "
        "can foul the cheeks",
        measured=side, limit=MOUTH_SIDE_MARGIN,
    ))

    # removable by hand: nothing of the collector roofs the captured lip
    # inside the lift window (the receiver has no ceiling)
    lip_prism = (
        rail_pose.translate[0] - rf["lap_lip_w"] / 2.0,   # x0
        tip[1],                                           # y0 (tip)
        rail_pose.translate[0] + rf["lap_lip_w"] / 2.0,   # x1
        face_y,                                           # y1 (face plane)
        handover_z + rf["lap_lip_t"],                     # z0 (lip top)
        handover_z + LIFT_WINDOW,                         # z1
    )
    blockers: list[str] = []
    for feat in coll.form.ribs:
        b = feat.box
        gx0, gy0, gz0 = (b.x0 + coll_pose.translate[0],
                         b.y0 + coll_pose.translate[1],
                         b.z0 + coll_pose.translate[2])
        gx1, gy1, gz1 = (b.x1 + coll_pose.translate[0],
                         b.y1 + coll_pose.translate[1],
                         b.z1 + coll_pose.translate[2])
        if (gx0 < lip_prism[2] and gx1 > lip_prism[0]
                and gy0 < lip_prism[3] and gy1 > lip_prism[1]
                and gz0 < lip_prism[5] and gz1 > lip_prism[4]):
            blockers.append(feat.name)
    out.append(_finding(
        "assembly.collector_removable_by_hand", not blockers,
        f"nothing roofs the captured lip within {LIFT_WINDOW:g} of lift — "
        "the collector lifts straight off"
        if not blockers else
        "collector material over the captured lip: " + ", ".join(blockers),
    ))

    # root drainage (VF-5): if the final rail has a root chamber, its root
    # troughs exit the front face across the module width — the collector's
    # tray mouth must span them so the passive root-drainage return lands
    # in the tray (a narrow receiver would spill the outer troughs).
    if rf.get("root_trough_count"):
        trough_x = rf["root_trough_x_max"]  # outermost trough outer edge in x
        dxc = abs(rail_pose.translate[0] - coll_pose.translate[0])
        mouth_reach = cf["receiver_cheek_x0"] - dxc
        out.append(_finding(
            "assembly.collector_catches_root_drainage",
            mouth_reach >= trough_x - 1e-6,
            f"the tray mouth spans the root troughs (reach {mouth_reach:.0f} >= "
            f"outer trough {trough_x:.0f}) — passive root drainage lands in the tray"
            if mouth_reach >= trough_x - 1e-6 else
            f"tray mouth reaches {mouth_reach:.0f} but the outer root trough is at "
            f"{trough_x:.0f} — widen the collector or the drainage spills",
            measured=mouth_reach, limit=trough_x,
        ))
    return out


DOCK_ALIGN_TOL = 1.0  # magnet-to-magnet lateral/plane slack across the dock


def _endcap_dock(
    endcap_ref: str, rail_ref: str, side: str,
    states: dict[str, Any], poses: dict[str, Any],
) -> list[Finding]:
    """VF-6: when an endcap carries dock magnets, each must land on a
    matching rail dock pocket across the arm/wall-top contact. We transform
    both pocket mouths to world and require they coincide within
    DOCK_ALIGN_TOL — a magnet with nothing to grab is a hallucinated dock.
    Emitted only when the endcap declares dock pockets."""
    check = "assembly.endcap_docks_to_rail"
    ec, rl = states.get(endcap_ref), states.get(rail_ref)
    ec_pose, rl_pose = poses.get(endcap_ref), poses.get(rail_ref)
    if ec is None or ec.form is None or ec_pose is None:
        return []
    ef = ec.form.frame
    if not ef.get("dock_pocket_count"):
        return []  # endcap has no dock magnets — nothing to seat
    if rl is None or rl.form is None or rl_pose is None:
        return [_finding(check, False, f"endcap {endcap_ref} docks but its "
                         f"rail {rail_ref} is not posed")]
    rf = rl.form.frame
    has_rail = rf.get("dock_front" if side == "front" else "dock_back", 0.0)
    if not has_rail:
        return [_finding(
            check, False,
            f"{endcap_ref} carries dock magnets but the {side} end of "
            f"{rail_ref} has no dock pocket to grab — add dock_end: {side}")]
    # VF-9 Part B: top (Z pockets on the wall top) vs face (Y pockets in the
    # end face). Both endcap and rail must use the same style, and we compare
    # their pocket-mouth positions in the pose.
    ec_face = ef.get("dock_style_face", 0.0) >= 0.5
    rl_face = rf.get("dock_style_face", 0.0) >= 0.5
    if ec_face != rl_face:
        return [_finding(
            check, False,
            f"{endcap_ref} docks {'face' if ec_face else 'top'} but {rail_ref}'s "
            f"{side} dock is {'face' if rl_face else 'top'} — styles must match")]
    if ec_face:
        rail_y = rf["rail_y0"] if side == "front" else rf["rail_y1"]
        z_ec, z_rl = ef["dock_z_plane"], rf.get("dock_face_z", ef["dock_z_plane"])
        where = f"{side} end face"
    else:
        rail_y = (rf["rail_y0"] + rf["dock_inset"] if side == "front"
                  else rf["rail_y1"] - rf["dock_inset"])
        z_ec, z_rl = ef["dock_z_plane"], rf["dock_z_plane"]
        where = f"{side} wall top"
    worst = 0.0
    for xs in (1.0, -1.0):
        pe = ec_pose.apply((xs * ef["dock_x"], ef["dock_y"], z_ec))
        pr = rl_pose.apply((xs * rf["dock_x"], rail_y, z_rl))
        d = math.dist(pe, pr)
        worst = max(worst, d)
    ok = worst <= DOCK_ALIGN_TOL + 1e-6
    return [_finding(
        check, ok,
        f"{int(ef['dock_pocket_count'])} dock magnet(s) seat on {rail_ref}'s "
        f"{where} (worst offset {worst:.2f})"
        if ok else
        f"{endcap_ref} dock magnets miss {rail_ref}'s pockets by {worst:.2f} "
        f"> {DOCK_ALIGN_TOL:g} — the magnetic dock does not mate in the pose",
        measured=worst, limit=DOCK_ALIGN_TOL,
    )]
