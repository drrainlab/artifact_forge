"""Mechanical joint IR builders — screw, lid seat, press fit, butt pin,
snap, compression gap."""
from __future__ import annotations

import math

from ..core.fasteners import screw_spec
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from ..product.assembly import JointUse
from .joints_core import (PILOT_PREFIX, POSITION_TOL, JointDecl, Pose, _finding,
                          _register, compute_pose, rotate_point)

# -- screw_joint ---------------------------------------------------------------


def _screw_joint_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """Bolt-circle screw joint: B's clearance holes must land on A's pilot
    bores after posing, with compatible diameters and enough thread
    engagement. Measured on the two Form IRs — a mismatched mount_bc dies
    HERE, before any CAD ever runs."""
    findings: list[Finding] = []
    screw = str(joint.params.get("screw", "M4"))
    count = int(joint.params.get("count", 3))
    spec = screw_spec(screw)

    prefix = str(joint.params.get("pilots", PILOT_PREFIX))
    pilots = [b for b in form_a.bores if b.name.startswith(prefix)]
    holes = list(form_b.holes)
    if len(pilots) < count or len(holes) < count:
        findings.append(_finding(
            "assembly.screw_joint_ir", False,
            f"screw count mismatch: joint wants {count}, "
            f"{joint.a_ref} has {len(pilots)} pilot(s) ({prefix}*), "
            f"{joint.b_ref} has {len(holes)} hole(s)",
        ))
        return findings

    # B hole centers in the assembled (root) frame. Holes sit on B's mount
    # plane — project each to its plate-bottom point before posing. Every
    # HOLE must land on a DISTINCT pilot (a part may carry more pilots than
    # this joint uses — the box's four bosses serve screws AND pins).
    posed = []
    for h in holes:
        hx, hy, z_top = h.at
        posed.append(pose.apply((hx, hy, z_top - h.through)))
    taken: set[int] = set()
    matched: list[tuple[Any, ...]] = []
    worst = 0.0
    for q in posed:
        best_i, best_d = None, float("inf")
        for i, b in enumerate(pilots):
            if i in taken:
                continue
            d_i = math.hypot(b.center[0] - q[0], b.center[1] - q[1])
            if d_i < best_d:
                best_i, best_d = i, d_i
        if best_i is None:
            best_d = float("inf")
        else:
            taken.add(best_i)
            matched.append((pilots[best_i],))
        worst = max(worst, best_d)
    pilots = [m[0] for m in matched] if len(matched) == len(posed) else pilots
    if worst > POSITION_TOL:
        findings.append(_finding(
            "assembly.screw_joint_ir", False,
            f"bolt patterns do not coincide in the assembled pose: worst "
            f"pair offset {worst:.2f} (tolerance {POSITION_TOL}) — check "
            "mount_bc on both parts (use assembly.shared to declare it once)",
            measured=worst, limit=POSITION_TOL,
        ))
        return findings

    problems: list[str] = []
    for h in holes:
        clear = screw_spec(h.screw)["clear"]
        if h.screw.lower() != screw.lower():
            problems.append(
                f"{joint.b_ref} hole is {h.screw}, joint says {screw}"
            )
        elif clear < spec["clear"] - 1e-6:
            problems.append(f"{joint.b_ref} hole too tight for {screw}")
    tap_lo, tap_hi = spec["tap"] - 0.4, spec["heatset"] + 0.3
    for b in pilots:
        if not tap_lo <= b.d <= tap_hi:
            problems.append(
                f"pilot {b.name} d={b.d:g} outside {screw} thread range "
                f"[{tap_lo:.1f}, {tap_hi:.1f}]"
            )
        depth = abs(b.span[1] - b.span[0])
        if depth < 5.0:
            problems.append(f"pilot {b.name} only {depth:g} deep — no thread grip")
    if problems:
        findings.append(_finding(
            "assembly.screw_joint_ir", False, "; ".join(problems)
        ))
        return findings

    findings.append(_finding(
        "assembly.screw_joint_ir", True,
        f"{count}x {screw}: bolt patterns coincide (worst offset "
        f"{worst:.3f}), clearance holes over thread pilots",
        measured=worst, limit=POSITION_TOL,
    ))
    return findings


_register(JointDecl(
    name="screw_joint",
    description="bolt-circle/line screw joint: clearance holes on B over "
                "thread pilots on A, verified coincident in the pose",
    ir_check=_screw_joint_ir,
    cad_checks=("assembly.no_interference", "assembly.screw_axes_clear"),
))


# -- lid_seat -------------------------------------------------------------------


def _lid_seat_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """Dimension-chain fit: the lid's plug must drop into the shell's
    interior with the declared clearance on every side, and not bottom out
    on anything before the rim seats. A is the box (shell frame keys), B is
    the lid (plug frame keys)."""
    clearance = float(joint.params.get("clearance", 0.3))
    fa, fb = form_a.frame, form_b.frame
    need_a = ("inner_u0", "inner_v0", "inner_u1", "inner_v1", "shell_h")
    need_b = ("plug_u0", "plug_v0", "plug_u1", "plug_v1", "plug_depth")
    missing = [k for k in need_a if k not in fa] + [k for k in need_b if k not in fb]
    if missing:
        return [_finding(
            "assembly.lid_seat_ir", False,
            f"missing fit frame keys: {missing} — the parts do not expose "
            "a shell interior / lid plug",
        )]
    # Pose the plug rectangle into the root frame (quarter turns keep it
    # axis-aligned) and compare against the interior rectangle.
    corners = [
        pose.apply((fb["plug_u0"], fb["plug_v0"], 0.0)),
        pose.apply((fb["plug_u1"], fb["plug_v1"], 0.0)),
    ]
    pu0, pu1 = sorted((corners[0][0], corners[1][0]))
    pv0, pv1 = sorted((corners[0][1], corners[1][1]))
    gaps = (
        pu0 - fa["inner_u0"], fa["inner_u1"] - pu1,
        pv0 - fa["inner_v0"], fa["inner_v1"] - pv1,
    )
    lo, hi = clearance - 0.15, clearance + 0.6
    problems: list[str] = []
    if min(gaps) < lo:
        problems.append(
            f"plug too tight: side gap {min(gaps):.2f} < {lo:.2f} "
            "(it will not drop in)"
        )
    if max(gaps) > hi:
        problems.append(
            f"plug too loose: side gap {max(gaps):.2f} > {hi:.2f} "
            "(the lid will rattle)"
        )
    # The plug must not reach the bosses/floor: depth < shell_h - floor gap.
    boss_top = max(
        (fa[k] for k in fa if k.endswith("_top")), default=fa.get("floor_t", 0.0)
    )
    room = fa["shell_h"] - boss_top
    if fb["plug_depth"] > room - 0.2:
        problems.append(
            f"plug depth {fb['plug_depth']:g} bottoms out on the bosses "
            f"(only {room:.1f} below the rim)"
        )
    if problems:
        return [_finding("assembly.lid_seat_ir", False, "; ".join(problems),
                         measured=min(gaps), limit=clearance)]
    return [_finding(
        "assembly.lid_seat_ir", True,
        f"plug seats with side gaps {min(gaps):.2f}..{max(gaps):.2f} "
        f"(clearance {clearance:g})",
        measured=min(gaps), limit=clearance,
    )]


_register(JointDecl(
    name="lid_seat",
    description="lid plug drops into the shell interior with declared "
                "clearance and seats on the rim without bottoming out",
    ir_check=_lid_seat_ir,
    cad_checks=("assembly.no_interference", "assembly.lid_seats"),
))


# -- press_fit_pin_pair ---------------------------------------------------------


def _press_fit_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """Pins on B land on receiving bores on A with the declared
    INTERFERENCE: the pin is thicker than the bore (negative clearance) —
    that is what makes it press-fit rather than loose."""
    interference = float(joint.params.get("interference", 0.1))
    prefix = str(joint.params.get("receivers", PILOT_PREFIX))
    if interference <= 0:
        return [_finding(
            "assembly.press_fit_ir", False,
            f"interference {interference:g} must be positive — a pin no "
            "thicker than its bore falls out",
        )]
    pins = list(form_b.pins)
    if not pins:
        return [_finding(
            "assembly.press_fit_ir", False,
            f"{joint.b_ref} declares no pins",
        )]
    receivers = [b for b in form_a.bores if b.name.startswith(prefix)]
    problems: list[str] = []
    worst = 0.0
    taken: set[int] = set()
    for pin in pins:
        px, py = pin.at
        q = pose.apply((px, py, 0.0))
        best_i, best_d = None, float("inf")
        for i, b in enumerate(receivers):
            if i in taken:
                continue
            d_i = math.hypot(b.center[0] - q[0], b.center[1] - q[1])
            if d_i < best_d:
                best_i, best_d = i, d_i
        if best_i is None or best_d > POSITION_TOL:
            problems.append(f"pin {pin.name} has no receiver within tolerance")
            continue
        taken.add(best_i)
        worst = max(worst, best_d)
        bore = receivers[best_i]
        want = bore.d + interference
        # Declared design numbers must agree nearly exactly — a tolerance
        # wider than the interference itself would wave loose pins through.
        if abs(pin.d - want) > 0.06:
            problems.append(
                f"pin {pin.name} d={pin.d:g} vs receiver {bore.d:g}: "
                f"needs {want:g} for {interference:g} interference"
            )
        depth = abs(bore.span[1] - bore.span[0])
        if pin.length > depth - 0.3:
            problems.append(
                f"pin {pin.name} ({pin.length:g}) longer than its receiver "
                f"({depth:g}) — the lid will never seat"
            )
    if problems:
        return [_finding("assembly.press_fit_ir", False, "; ".join(problems))]
    return [_finding(
        "assembly.press_fit_ir", True,
        f"{len(pins)} pin(s) land on receivers (worst offset {worst:.3f}) "
        f"with {interference:g} interference",
        measured=worst, limit=POSITION_TOL,
    )]


_register(JointDecl(
    name="press_fit_pin_pair",
    description="pins on B press into receiving bores on A: coincident in "
                "the pose, thicker than the bore by the interference",
    ir_check=_press_fit_ir,
    cad_checks=("assembly.pins_engage",),
))


# -- butt_pin_joint -------------------------------------------------------------


def _butt_pin_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """Butt-split alignment: a run longer than the bed prints as two
    mating halves — pins on B's end face press into sockets on A's start
    face. The joint proves the halves are the SAME section (outline match)
    and the pins land on their sockets with the declared interference."""
    interference = float(joint.params.get("interference", 0.1))
    pins = [p for p in form_b.pins if p.name.startswith("butt_pin")]
    sockets = [b for b in form_a.bores if b.name.startswith("butt_socket")]
    if not pins or len(pins) != len(sockets):
        return [_finding(
            "assembly.butt_pin_ir", False,
            f"butt joint needs matching pin/socket counts: {joint.b_ref} has "
            f"{len(pins)} pin(s), {joint.a_ref} has {len(sockets)} socket(s) "
            "(set end_joint: pins / sockets on the two halves)",
        )]
    # Same section: both halves must share the profile outline bbox.
    la, ha = form_a.section.outer.bbox()
    lb, hb = form_b.section.outer.bbox()
    mismatch = max(
        abs(la.u - lb.u), abs(la.v - lb.v), abs(ha.u - hb.u), abs(ha.v - hb.v)
    )
    if mismatch > 0.05:
        return [_finding(
            "assembly.butt_pin_ir", False,
            f"halves have different sections (outline mismatch {mismatch:.2f}) "
            "— a butt joint only aligns identical profiles",
            measured=mismatch, limit=0.05,
        )]
    problems: list[str] = []
    worst = 0.0
    for pin in pins:
        tip = pose.apply(pin.end_point())
        best = min(
            math.hypot(
                # off-axis distance in the socket's cross plane (axis X):
                tip[1] - s.center[1], tip[2] - s.center[2]
            )
            for s in sockets
        )
        worst = max(worst, best)
        near = min(sockets, key=lambda s: math.hypot(
            tip[1] - s.center[1], tip[2] - s.center[2]))
        want = near.d + interference
        if abs(pin.d - want) > 0.06:
            problems.append(
                f"{pin.name} d={pin.d:g} vs socket {near.d:g}: needs "
                f"{want:g} for {interference:g} interference"
            )
        depth = abs(near.span[1] - near.span[0])
        if pin.length > depth + 0.5:
            problems.append(
                f"{pin.name} ({pin.length:g}) longer than its socket ({depth:g})"
            )
    if worst > POSITION_TOL:
        problems.append(
            f"pins do not land on sockets (worst offset {worst:.2f})"
        )
    if problems:
        return [_finding("assembly.butt_pin_ir", False, "; ".join(problems))]
    return [_finding(
        "assembly.butt_pin_ir", True,
        f"{len(pins)} butt pin(s) align identical sections "
        f"(worst offset {worst:.3f}, interference {interference:g})",
        measured=worst, limit=POSITION_TOL,
    )]


_register(JointDecl(
    name="butt_pin_joint",
    description="butt-split halves of one long section aligned by end-face "
                "press pins — identical outlines verified, pins on sockets",
    ir_check=_butt_pin_ir,
    cad_checks=("assembly.no_interference",),
))


# -- snap_joint -----------------------------------------------------------------

#: Max flexure strain during snap insertion for common FDM plastics
#: (PETG/ABS ~5%; PLA is stiffer — the check WARNs above 3.5%).
SNAP_STRAIN_LIMIT = 0.05
SNAP_STRAIN_WARN = 0.035


def _snap_joint_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """Cantilever snap: B's hook lips must land INSIDE A's receiver
    windows in the pose with a real undercut, and the beam must survive
    the insertion flex — strain = 1.5 * deflection * t / L^2, the classic
    cantilever snap formula, checked against printable-plastic limits."""
    prefix = str(joint.params.get("hooks", "snap"))
    lips = [r for r in form_b.ribs if r.name.startswith(f"{prefix}_lip")]
    windows = [c for c in form_a.cutboxes if "snap_window" in c.name]
    if not lips or len(lips) > len(windows):
        return [_finding(
            "assembly.snap_joint_ir", False,
            f"{joint.b_ref} has {len(lips)} lip(s), {joint.a_ref} has "
            f"{len(windows)} window(s)",
        )]
    f = form_b.frame
    beam_t = f.get(f"{prefix}_beam_t")
    hook_len = f.get(f"{prefix}_hook_len")
    lip_d = f.get(f"{prefix}_lip_d")
    if beam_t is None or hook_len is None or lip_d is None:
        return [_finding(
            "assembly.snap_joint_ir", False,
            f"{joint.b_ref} frame lacks {prefix}_beam_t/hook_len/lip_d",
        )]
    # Insertion flex: the beam deflects by the full lip depth.
    strain = 1.5 * lip_d * beam_t / (hook_len * hook_len)
    if strain > SNAP_STRAIN_LIMIT:
        return [_finding(
            "assembly.snap_joint_ir", False,
            f"snap insertion strain {strain:.3f} > {SNAP_STRAIN_LIMIT} — "
            "the hook snaps off instead of snapping in (lengthen the beam, "
            "thin it, or shorten the lip)",
            measured=strain, limit=SNAP_STRAIN_LIMIT,
        )]
    problems: list[str] = []
    engaged = 0
    for lip in lips:
        b = lip.box
        c1 = pose.apply((b.x0, b.y0, b.z0))
        c2 = pose.apply((b.x1, b.y1, b.z1))
        lx0, lx1 = sorted((c1[0], c2[0]))
        ly0, ly1 = sorted((c1[1], c2[1]))
        lz0, lz1 = sorted((c1[2], c2[2]))
        hit = None
        for win in windows:
            w = win.box
            if (w.x0 - 0.01 <= lx0 and lx1 <= w.x1 + 0.01
                    and w.y0 + 0.05 <= ly0 and ly1 <= w.y1 - 0.05
                    and w.z0 + 0.05 <= lz0 and lz1 <= w.z1 - 0.05):
                hit = win
                break
        if hit is None:
            problems.append(f"{lip.name} does not land inside any window")
            continue
        # Real undercut: the lip must reach PAST the wall's inner face.
        wall = form_a.frame.get("shell_wall", 2.4)
        inner = (form_a.frame.get("inner_u1", 0.0)
                 if (lx0 + lx1) / 2.0 > 0 else form_a.frame.get("inner_u0", 0.0))
        undercut = (lx1 - inner) if (lx0 + lx1) / 2.0 > 0 else (inner - lx0)
        if undercut < 0.8:
            problems.append(
                f"{lip.name} undercut {undercut:.2f} < 0.8 — the lid pops off"
            )
            continue
        engaged += 1
    if problems:
        return [_finding("assembly.snap_joint_ir", False, "; ".join(problems))]
    note = ""
    if strain > SNAP_STRAIN_WARN:
        note = f" (strain {strain:.3f} is PETG/ABS territory — brittle PLA may crack)"
    return [_finding(
        "assembly.snap_joint_ir", True,
        f"{engaged} hook(s) engage their windows, insertion strain "
        f"{strain:.3f} <= {SNAP_STRAIN_LIMIT}{note}",
        measured=strain, limit=SNAP_STRAIN_LIMIT,
    )]


_register(JointDecl(
    name="snap_joint",
    description="cantilever snap hooks into receiver windows: undercut and "
                "insertion strain verified, engagement probed in the pose",
    ir_check=_snap_joint_ir,
    cad_checks=("assembly.no_interference", "assembly.hooks_engage"),
))


# -- compression_gap_joint --------------------------------------------------------

#: A compression gap thinner than this cannot guarantee squeeze across FDM
#: tolerances — the halves would bottom out face-to-face.
MIN_COMPRESSION_GAP = 1.5


def _compression_gap_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """Split-clamp compression joint (Bio-1): in the assembled pose the two
    mating planes stay exactly ``gap`` apart, the saddle centers coincide
    (the halves form ONE branch circle), and both saddles carry the same
    radius — the branch_d desync detector. Measured on the two Form IR
    frames + the pose, before any CAD."""
    from ..core.values import parse_quantity

    check = "assembly.clamp_gap_ir"
    raw_gap = joint.params.get("gap")
    if raw_gap is None:
        return [_finding(check, False,
                         "compression_gap_joint needs params.gap (length)")]
    try:
        gap = parse_quantity(str(raw_gap), "length", where="compression_gap_joint.gap")
    except ValueError as exc:
        return [_finding(check, False, str(exc))]
    fa, fb = form_a.frame, form_b.frame
    needed = ("mate_z", "saddle_cz", "saddle_r", "cavity_center_u")
    missing = [k for k in needed if k not in fa or k not in fb]
    if missing:
        return [_finding(
            check, False,
            f"clamp frame keys missing on a half: {missing} — the parts are "
            "not split-clamp halves",
        )]
    if gap < MIN_COMPRESSION_GAP:
        return [_finding(
            check, False,
            f"compression gap {gap:g} < {MIN_COMPRESSION_GAP} — the halves "
            "bottom out face-to-face and never squeeze the branch",
            measured=gap, limit=MIN_COMPRESSION_GAP,
        )]
    problems: list[str] = []
    # posed mating-plane separation == gap
    posed_mate_b = pose.apply((0.0, 0.0, fb["mate_z"]))[2]
    separation = posed_mate_b - fa["mate_z"]
    if abs(separation - gap) > 0.15:
        problems.append(
            f"posed mate planes are {separation:.2f} apart, declared gap "
            f"{gap:g} (check compression_gap on both halves — use "
            "assembly.shared)")
    # posed saddle centers coincide: one nominal branch circle
    a_c = (form_a.width / 2.0, fa["cavity_center_u"], fa["saddle_cz"])
    b_c = pose.apply((form_b.width / 2.0, fb["cavity_center_u"], fb["saddle_cz"]))
    center_off = math.dist(a_c, b_c)
    if center_off > 0.15:
        problems.append(
            f"posed saddle centers {center_off:.2f} apart — the halves do "
            "not form one branch circle")
    # branch_d desync detector
    if abs(fa["saddle_r"] - fb["saddle_r"]) > 0.05:
        problems.append(
            f"saddle radii differ: {fa['saddle_r']:g} vs {fb['saddle_r']:g} "
            "— nominal_branch_d desync between the halves")
    if problems:
        return [_finding(check, False, "; ".join(problems),
                         measured=separation, limit=gap)]
    return [_finding(
        check, True,
        f"mating planes {separation:.2f} apart (gap {gap:g}), saddle centers "
        f"coincide within {center_off:.3f}, radii match",
        measured=separation, limit=gap,
    )]


_register(JointDecl(
    name="compression_gap_joint",
    description="split-clamp compression interface: posed mating planes keep "
                "the declared gap, saddles form one circle with equal radii",
    ir_check=_compression_gap_ir,
    cad_checks=("assembly.no_interference",),
))

