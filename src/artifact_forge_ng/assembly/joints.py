"""The joint registry — typed, verifiable connections between parts.

Same discipline as recipe ops and validators: a joint type named in YAML
binds fail-fast at load; every joint declares the IR check it runs BEFORE
any CAD and the assembly-level CAD probes that verify the fit in the
assembled pose. A joint whose checks cannot run leaves its interface
feature honestly un-built.

Everything here is CAD-free — pose math and frame arithmetic only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

from ..core.fasteners import screw_spec
from ..core.findings import Finding, Level, Status
from ..form.part import PartForm
from ..product.assembly import JointUse

#: Paired bolt patterns must coincide within this after posing.
POSITION_TOL = 0.3

#: Bore-name prefix a part uses to expose screw-joint pilots.
PILOT_PREFIX = "mount_pilot"


class JointError(ValueError):
    pass


@dataclass(frozen=True)
class Pose:
    """Rigid placement of a part: rotate (90-degree Euler XYZ steps, in
    degrees) then translate. Deterministic integers — no solver."""

    rotate: tuple[float, float, float]
    translate: tuple[float, float, float]

    def apply(self, p: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = rotate_point(p, self.rotate)
        tx, ty, tz = self.translate
        return (x + tx, y + ty, z + tz)


IDENTITY_POSE = Pose(rotate=(0.0, 0.0, 0.0), translate=(0.0, 0.0, 0.0))


def rotate_point(
    p: tuple[float, float, float], rotate: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Euler XYZ rotation restricted to quarter turns — exact arithmetic,
    no float drift in poses."""
    x, y, z = p
    for axis, deg in enumerate(rotate):
        c = int(round(math.cos(math.radians(deg))))
        s = int(round(math.sin(math.radians(deg))))
        if axis == 0:
            y, z = c * y - s * z, s * y + c * z
        elif axis == 1:
            x, z = c * x + s * z, -s * x + c * z
        else:
            x, y = c * x - s * y, s * x + c * y
    return (x, y, z)


def compute_pose(joint: JointUse, form_a: PartForm, form_b: PartForm) -> Pose:
    """Pose of part B in part A's (root's) frame: rotate B by the joint's
    explicit angles, then translate so B's datum lands on A's datum."""
    da = form_a.datums.get(joint.a_datum)
    db = form_b.datums.get(joint.b_datum)
    if da is None:
        raise JointError(
            f"part {joint.a_ref!r} has no datum {joint.a_datum!r} "
            f"(has: {sorted(form_a.datums)})"
        )
    if db is None:
        raise JointError(
            f"part {joint.b_ref!r} has no datum {joint.b_datum!r} "
            f"(has: {sorted(form_b.datums)})"
        )
    rot = (joint.rotate[0], joint.rotate[1], joint.rotate[2])
    bx, by, bz = rotate_point(tuple(db["at"]), rot)
    ax, ay, az = da["at"]
    return Pose(rotate=rot, translate=(ax - bx, ay - by, az - bz))


def _finding(check: str, ok: bool, message: str, *, measured: float | None = None,
             limit: float | None = None, warn: bool = False) -> Finding:
    status = Status.PASS if ok else (Status.WARN if warn else Status.FAIL)
    return Finding(
        check=check, status=status, level=Level.ASSEMBLY, message=message,
        critical=not ok and not warn, measured=measured, limit=limit,
        unit="mm" if measured is not None else "",
    )


@dataclass(frozen=True)
class JointDecl:
    name: str
    description: str
    #: (PartForm A, PartForm B, pose of B, joint) -> findings. CAD-free.
    ir_check: Callable[[PartForm, PartForm, Pose, JointUse], list[Finding]]
    #: Assembly-level CAD probe names this joint subscribes to.
    cad_checks: tuple[str, ...]


JOINT_TYPES: dict[str, JointDecl] = {}


def _register(decl: JointDecl) -> None:
    JOINT_TYPES[decl.name] = decl


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


# -- removable_insert (vertical farm: cassette into rail seat) ------------------

#: Per-side drop-in clearance band: tighter binds when the print swells,
#: looser lets the cassette rattle over the water.
INSERT_CLEARANCE_BAND = (0.5, 1.0)
#: Water must always pass UNDER the seated contact window.
MIN_DRAIN_GAP = 1.0
#: The window's reach into the channel's upper zone — pulse contact only.
WINDOW_REACH_BAND = (1.0, 2.0)

_INSERT_A_KEYS = (
    "seat_u0", "seat_v0", "seat_u1", "seat_v1", "seat_floor_z",
    "seat_clearance", "channel_center_x", "channel_w", "channel_top_z",
    "channel_floor_z_inlet", "channel_floor_z_outlet",
    "channel_y_inlet", "channel_y_outlet", "body_h",
)
_INSERT_B_KEYS = (
    "cassette_u0", "cassette_v0", "cassette_u1", "cassette_v1",
    "cassette_h", "window_cx", "window_w", "window_floor_z",
)


def _removable_insert_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """The Cassette Interface Standard, verified in the pose: the cassette
    drops into the rail seat within the clearance band, its rim stays
    graspable above the rail top (tool-free), and its contact window rides
    INSIDE the channel with pulse-only reach — water always drains under
    it, so permanent flooding is unrepresentable."""
    check = "assembly.removable_insert_ir"
    fa, fb = form_a.frame, form_b.frame
    missing = [k for k in _INSERT_A_KEYS if k not in fa]
    missing += [f"B:{k}" for k in _INSERT_B_KEYS if k not in fb]
    if missing:
        return [_finding(
            check, False,
            f"interface frame keys missing: {', '.join(missing)} — the part "
            "does not implement the Cassette Interface Standard",
        )]
    from ..core.values import parse_quantity

    raw_lift = joint.params.get("lift_margin", 3.0)
    lift_margin = (parse_quantity(raw_lift, "length", where="removable_insert")
                   if isinstance(raw_lift, str) else float(raw_lift))

    lo = pose.apply((fb["cassette_u0"], fb["cassette_v0"], 0.0))
    hi = pose.apply((fb["cassette_u1"], fb["cassette_v1"], fb["cassette_h"]))
    pu0, pu1 = sorted((lo[0], hi[0]))
    pv0, pv1 = sorted((lo[1], hi[1]))
    pz0, pz1 = sorted((lo[2], hi[2]))

    problems: list[str] = []
    clearance = fa["seat_clearance"]
    gaps = {
        "west": pu0 - fa["seat_u0"], "east": fa["seat_u1"] - pu1,
        "front": pv0 - fa["seat_v0"], "back": fa["seat_v1"] - pv1,
    }
    for side, gap in gaps.items():
        if not (INSERT_CLEARANCE_BAND[0] - 1e-6 <= gap <= INSERT_CLEARANCE_BAND[1] + 1e-6):
            problems.append(
                f"{side} gap {gap:.2f} outside "
                f"{INSERT_CLEARANCE_BAND[0]}..{INSERT_CLEARANCE_BAND[1]}")
        elif abs(gap - clearance) > 0.3:
            problems.append(
                f"{side} gap {gap:.2f} != declared clearance {clearance:g}")
    if abs(pz0 - fa["seat_floor_z"]) > 0.05:
        problems.append(
            f"cassette floor lands at z={pz0:.2f}, the seat floor is "
            f"{fa['seat_floor_z']:g} — it floats or clips")
    rim_above = pz1 - fa["body_h"]
    if rim_above < lift_margin:
        problems.append(
            f"rim only {rim_above:.1f} above the rail top (needs >= "
            f"{lift_margin:g}) — no tool-free grip")

    # The window must ride INSIDE the channel and reach pulse water only.
    wx = pose.apply((fb["window_cx"], 0.0, 0.0))[0]
    half_w = fb["window_w"] / 2.0
    ch_half = fa["channel_w"] / 2.0
    if abs(wx - fa["channel_center_x"]) > 2.0:
        problems.append(
            f"window center {wx:.1f} vs channel {fa['channel_center_x']:g} — "
            "not aligned")
    if (wx - half_w < fa["channel_center_x"] - ch_half + 0.5
            or wx + half_w > fa["channel_center_x"] + ch_half - 0.5):
        problems.append(
            f"window {fb['window_w']:g} wide does not fit inside the "
            f"{fa['channel_w']:g} channel — its edges would sit in water "
            "on the seat floor")
    wz = pose.apply((0.0, 0.0, fb["window_floor_z"]))[2]
    y_in, y_out = fa["channel_y_inlet"], fa["channel_y_outlet"]
    t = (0.0 - y_in) / (y_out - y_in)
    floor_here = (fa["channel_floor_z_inlet"]
                  + t * (fa["channel_floor_z_outlet"] - fa["channel_floor_z_inlet"]))
    drain_gap = wz - floor_here
    reach = fa["channel_top_z"] - wz
    if drain_gap < MIN_DRAIN_GAP:
        problems.append(
            f"window floor {drain_gap:.2f} above the channel floor — it dams "
            f"the flow (needs >= {MIN_DRAIN_GAP:g}); the substrate would sit in water")
    if not (WINDOW_REACH_BAND[0] - 1e-6 <= reach <= WINDOW_REACH_BAND[1] + 1e-6):
        problems.append(
            f"window reaches {reach:.2f} into the channel (band "
            f"{WINDOW_REACH_BAND[0]}..{WINDOW_REACH_BAND[1]}) — shallower "
            "never touches pulse water, deeper floods the substrate")
    if problems:
        return [_finding(check, False, "; ".join(problems))]
    return [_finding(
        check, True,
        f"cassette seats with {clearance:g} clearance, rim {rim_above:.1f} "
        f"proud for fingers, window reaches {reach:.2f} into the channel "
        f"with {drain_gap:.1f} drain gap under it",
        measured=reach, limit=WINDOW_REACH_BAND[1],
    )]


_register(JointDecl(
    name="removable_insert",
    description="drop-in cassette in the rail seat: clearance band, "
                "tool-free rim, contact window inside the channel with "
                "pulse-only reach and a guaranteed drain gap",
    ir_check=_removable_insert_ir,
    cad_checks=("assembly.no_interference",),
))


# -- drop_in_screen (vertical farm VF-8: strainer basket in the collector) ------

_SCREEN_A_KEYS = (
    "screen_seat_u0", "screen_seat_v0", "screen_seat_u1", "screen_seat_v1",
    "screen_seat_floor_z", "screen_seat_clearance", "screen_seat_drain_y",
    "screen_seat_drain_d", "tray_overflow_z",
)
_SCREEN_B_KEYS = (
    "screen_u0", "screen_v0", "screen_u1", "screen_v1",
    "screen_rim_z", "screen_floor_z",
)
#: The basket footprint must overhang the drain on every side by at least the
#: seat clearance PLUS this margin, so even shifted to its clearance limit it
#: still fully covers the drain (no bypass, no slide-off). The collector sump
#: is shallow in Y (the drain sits near the back wall), so the margin is modest.
SCREEN_DRAIN_OVERHANG = 0.5


def _drop_in_screen_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """VF-8: a drop-in strainer basket seats over the collector drain. In the
    pose: the basket footprint ENCLOSES the drain (water reaches it only
    through the mesh — no side bypass), it can't slide far enough to expose the
    drain (anti-shift), it lifts straight out (tool-free), and by default its
    rim sits ABOVE the tray overflow so a clog spills the OPEN tray visibly
    rather than overtopping the basket to the drain. `allow_emergency_bypass`
    opts out of the rim rule and is reported."""
    check = "assembly.screen_normal_no_bypass"
    fa, fb = form_a.frame, form_b.frame
    missing = [k for k in _SCREEN_A_KEYS if k not in fa]
    if missing:
        return [_finding(
            check, False,
            f"collector has no strainer seat ({', '.join(missing)}) — set "
            "screen_seat: true on the collector")]
    missing += [f"B:{k}" for k in _SCREEN_B_KEYS if k not in fb]
    if missing:
        return [_finding(check, False, f"screen frame keys missing: {', '.join(missing)}")]

    allow_bypass = bool(joint.params.get("allow_emergency_bypass", False))

    lo = pose.apply((fb["screen_u0"], fb["screen_v0"], fb["screen_floor_z"]))
    hi = pose.apply((fb["screen_u1"], fb["screen_v1"], fb["screen_rim_z"]))
    pu0, pu1 = sorted((lo[0], hi[0]))
    pv0, pv1 = sorted((lo[1], hi[1]))
    pz_floor = min(lo[2], hi[2])
    pz_rim = max(lo[2], hi[2])

    problems: list[str] = []
    clr = fa["screen_seat_clearance"]
    for side, gap in (("west", pu0 - fa["screen_seat_u0"]),
                      ("east", fa["screen_seat_u1"] - pu1),
                      ("front", pv0 - fa["screen_seat_v0"]),
                      ("back", fa["screen_seat_v1"] - pv1)):
        if not (INSERT_CLEARANCE_BAND[0] - 1e-6 <= gap <= INSERT_CLEARANCE_BAND[1] + 1e-6):
            problems.append(f"{side} seat gap {gap:.2f} outside "
                            f"{INSERT_CLEARANCE_BAND[0]}..{INSERT_CLEARANCE_BAND[1]}")

    # no bypass + anti-shift: the basket overhangs the drain on every side by
    # >= the seat clearance + margin, so no side path reaches the drain and a
    # clearance-limit slide can't expose it. Drain center = (x0, dy), radius dr.
    dy, dr = fa["screen_seat_drain_y"], fa["screen_seat_drain_d"] / 2.0
    need = clr + SCREEN_DRAIN_OVERHANG
    for side, overhang in (("west", -dr - pu0), ("east", pu1 - dr),
                           ("front", (dy - dr) - pv0), ("back", pv1 - (dy + dr))):
        if overhang < need - 1e-6:
            problems.append(
                f"{side} basket edge only {overhang:.1f} past the drain (needs >= "
                f"{need:.1f}) — water could bypass the mesh or the basket slide off")

    # mesh floor sits at/above the seat floor (over the drain mouth)
    if pz_floor < fa["screen_seat_floor_z"] - 0.6:
        problems.append(
            f"basket floor lands at z={pz_floor:.2f} below the seat floor "
            f"{fa['screen_seat_floor_z']:g} — it clips the sump")

    # fail-safe: rim above the tray overflow unless emergency bypass is opted in
    overflow = fa["tray_overflow_z"]
    bypass_note = ""
    if pz_rim < overflow - 1e-6:
        if allow_bypass:
            bypass_note = (" [emergency_unfiltered_bypass ON: a clog overtops the "
                           "basket to the drain — rinse the basket]")
        else:
            problems.append(
                f"basket rim z={pz_rim:.1f} below the tray overflow {overflow:.1f} "
                "— a clog would overtop the basket to the drain UNFILTERED; raise "
                "the basket or set allow_emergency_bypass: true")

    findings: list[Finding] = []
    if problems:
        findings.append(_finding(check, False, "; ".join(problems)))
    else:
        findings.append(_finding(
            check, True,
            f"basket seats over the drain (mesh-only path, rim {pz_rim - overflow:+.1f} "
            f"vs tray overflow), lifts out tool-free" + bypass_note,
        ))

    # the drain footprint is fully inside the basket footprint in the pose
    enclosed = (pu0 <= -dr + 1e-6 and pu1 >= dr - 1e-6
                and pv0 <= (dy - dr) + 1e-6 and pv1 >= (dy + dr) - 1e-6)
    findings.append(_finding(
        "assembly.drain_inside_screen_footprint", enclosed,
        "the drain bore is fully within the basket footprint — water enters "
        "only through the mesh" if enclosed else
        "the drain pokes past the basket footprint — a rim of unfiltered bypass"))

    # tool-free vertical removal: the rim stands proud of the sump-well floor by
    # a finger's grip and the mate is a straight lift (drop-in, no snap/screw)
    proud = pz_rim - fa["screen_seat_floor_z"]
    lift_ok = proud >= 8.0
    findings.append(_finding(
        "assembly.screen_removable_from_sump", lift_ok,
        f"the basket stands {proud:.0f} mm proud of the sump floor and lifts "
        "straight out of the well — tool-free" if lift_ok else
        f"the basket is only {proud:.0f} mm proud — no finger grip to lift it out"))
    return findings


_register(JointDecl(
    name="drop_in_screen",
    description="drop-in strainer basket over the collector drain: seats in "
                "the sump ledge, encloses the drain (no bypass), anti-shift, "
                "tool-free, zero-bypass fail-safe unless allow_emergency_bypass",
    ir_check=_drop_in_screen_ir,
    cad_checks=("assembly.no_interference",),
))


# -- tongue_groove (vertical farm: module-to-module line alignment) --------------

TG_SIDE_BAND = (0.3, 0.5)
TG_BOTTOM_MARGIN = 0.3

_TG_KEYS = ("channel_center_x", "channel_top_z", "channel_y_inlet",
            "module_pitch", "rail_x0", "rail_x1")


def _tongue_groove_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """Line alignment, verified in the pose: B's groove swallows A's tongue
    with the per-side clearance band and never bottoms (aligns, never
    carries, never seals), the faces mate flush at the module length, both
    channels stay parallel at the same height with inlets on the same
    edge — a flipped module fails loudly."""
    check = "assembly.tongue_groove_ir"
    fa, fb = form_a.frame, form_b.frame
    missing = [k for k in _TG_KEYS if k not in fa]
    missing += [f"B:{k}" for k in _TG_KEYS if k not in fb]
    if missing:
        return [_finding(check, False,
                         f"line-interface frame keys missing: {', '.join(missing)}")]
    tongue = next((r for r in form_a.ribs if "tongue" in r.name), None)
    groove = next((c for c in form_b.cutboxes if "groove" in c.name), None)
    if tongue is None or groove is None:
        return [_finding(
            check, False,
            f"{joint.a_ref} tongue: {tongue is not None}, "
            f"{joint.b_ref} groove: {groove is not None}",
        )]
    g1 = pose.apply((groove.box.x0, groove.box.y0, groove.box.z0))
    g2 = pose.apply((groove.box.x1, groove.box.y1, groove.box.z1))
    gx0, gx1 = sorted((g1[0], g2[0]))
    gy0, gy1 = sorted((g1[1], g2[1]))
    gz0, gz1 = sorted((g1[2], g2[2]))
    t = tongue.box

    problems: list[str] = []
    for label, gap in (
        ("y-", t.y0 - gy0), ("y+", gy1 - t.y1),
        ("z-", t.z0 - gz0), ("z+", gz1 - t.z1),
    ):
        if not (TG_SIDE_BAND[0] - 1e-6 <= gap <= TG_SIDE_BAND[1] + 1e-6):
            problems.append(
                f"{label} clearance {gap:.2f} outside {TG_SIDE_BAND[0]}..{TG_SIDE_BAND[1]}")
    if t.x0 < gx0 - 1e-6:
        problems.append("tongue starts before the groove mouth — faces do not mate")
    bottom_margin = gx1 - t.x1
    if bottom_margin < TG_BOTTOM_MARGIN:
        problems.append(
            f"tongue bottoms in the groove (margin {bottom_margin:.2f} < "
            f"{TG_BOTTOM_MARGIN:g}) — the joint must align, never carry")

    module_l = fa["rail_x1"] - fa["rail_x0"]
    measured_pitch = pose.translate[0]
    if abs(measured_pitch - module_l) > 0.2:
        problems.append(
            f"posed pitch {measured_pitch:.2f} != mating module length "
            f"{module_l:g} — the faces do not sit flush")
    p_center = pose.apply((fb["channel_center_x"], 0.0, fb["channel_top_z"]))
    ch_off = abs(p_center[0] - fa["channel_center_x"] - measured_pitch)
    if ch_off > 0.5:
        problems.append(f"channel centerlines offset {ch_off:.2f} across the joint")
    dz = abs(p_center[2] - fa["channel_top_z"])
    if dz > 0.3:
        problems.append(f"channel entry planes differ by {dz:.2f} across the joint")
    p_inlet_y = pose.apply((0.0, fb["channel_y_inlet"], 0.0))[1]
    inlet_off = abs(p_inlet_y - fa["channel_y_inlet"])
    if inlet_off > 1.0:
        problems.append(
            f"inlet edges offset {inlet_off:.1f} — one module is flipped in the line")
    if problems:
        return [_finding(check, False, "; ".join(problems))]
    return [_finding(
        check, True,
        f"modules mate flush at {measured_pitch:.1f} (nominal grid "
        f"{fa['module_pitch']:g}), tongue floats {bottom_margin:.1f} short of "
        f"the groove bottom, channels parallel within {ch_off:.2f}",
        measured=measured_pitch, limit=fa["module_pitch"],
    )]


_register(JointDecl(
    name="tongue_groove",
    description="module line alignment: groove swallows tongue in the "
                "clearance band without bottoming; channels stay parallel, "
                "level, and same-facing across the joint",
    ir_check=_tongue_groove_ir,
    cad_checks=("assembly.no_interference",),
))


_DOVETAIL_A_KEYS = ("groove_top_w", "groove_bottom_w", "groove_depth",
                    "socket_top_v")
_DOVETAIL_B_KEYS = ("dovetail_root_w", "dovetail_top_w", "dovetail_h",
                    "foot_plane_v")
#: Per-side sliding clearance band (mm): tighter than the drop-in insert,
#: looser than a press fit — the adapter must SLIDE by hand yet not rattle.
DOVETAIL_CLEARANCE_BAND = (0.1, 0.8)
#: The wide end of the male must exceed the groove OPENING by at least
#: this much — the retention that makes a dovetail a dovetail.
MIN_DOVETAIL_RETENTION = 0.5


def _dovetail_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """The wearable adapter standard, verified in the pose: the male foot
    rides the female groove flanks inside the sliding band, cannot lift
    straight out (wide end > opening), never bottoms (seats on flanks),
    matches the flank angle, and engages the socket over its full length.
    Axial retention is friction-only in v1 — stated in the report, not
    hidden."""
    check = "assembly.dovetail_ir"
    fa, fb = form_a.frame, form_b.frame
    missing = [k for k in _DOVETAIL_A_KEYS if k not in fa]
    missing += [f"B:{k}" for k in _DOVETAIL_B_KEYS if k not in fb]
    if missing:
        return [_finding(
            check, False,
            f"dovetail frame keys missing: {', '.join(missing)} — a part "
            "does not implement the adapter socket standard",
        )]
    problems: list[str] = []
    gt, gb = fa["groove_top_w"], fa["groove_bottom_w"]
    gd = fa["groove_depth"]
    mt, mb, mh = fb["dovetail_root_w"], fb["dovetail_top_w"], fb["dovetail_h"]
    lo, hi = DOVETAIL_CLEARANCE_BAND
    for name, female, male in (("flank", gb, mb), ("opening", gt, mt)):
        side = (female - male) / 2.0
        if not lo <= side <= hi:
            problems.append(
                f"{name} clearance {side:.2f}/side outside [{lo:g}, {hi:g}]")
    if mb < gt + MIN_DOVETAIL_RETENTION:
        problems.append(
            f"male wide end {mb:.1f} does not exceed the opening {gt:.1f} "
            f"by {MIN_DOVETAIL_RETENTION:g} — lifts straight out, no dovetail")
    if mh > gd - 0.2:
        problems.append(
            f"male height {mh:.1f} bottoms in the {gd:.1f} groove — the "
            "foot must seat on the flanks")
    import math as _math
    ang_f = _math.degrees(_math.atan2((gb - gt) / 2.0, gd))
    ang_m = _math.degrees(_math.atan2((mb - mt) / 2.0, mh))
    if abs(ang_f - ang_m) > 3.0:
        problems.append(
            f"flank angles differ: female {ang_f:.1f} vs male {ang_m:.1f} deg")
    if form_b.width > form_a.width + 0.1:
        problems.append(
            f"adapter length {form_b.width:g} overhangs the {form_a.width:g} "
            "socket")
    # posed foot plane must land on the socket top plane
    foot_global_z = pose.apply((0.0, 0.0, fb["foot_plane_v"]))[2]
    if abs(foot_global_z - fa["socket_top_v"]) > 0.05:
        problems.append(
            f"posed foot plane at {foot_global_z:.2f}, socket top at "
            f"{fa['socket_top_v']:.2f} — datum chain broken")
    return [_finding(
        check, not problems,
        "male dovetail rides the socket in the sliding band, retained "
        "against lift-out; axial retention friction-only (v1)"
        if not problems else "; ".join(problems),
        measured=(gb - mb) / 2.0, limit=hi,
    )]


_register(JointDecl(
    name="dovetail_joint",
    description="slide-on payload adapter: male dovetail foot in the "
                "female socket groove, clearance band per side, lift-out "
                "retention by undercut, friction-only axial hold (v1)",
    ir_check=_dovetail_ir,
    cad_checks=("assembly.no_interference",),
))


_FLUID_A_KEYS = ("channel_center_x", "channel_w", "channel_top_z",
                 "channel_floor_z_outlet", "channel_y_outlet")
_FLUID_B_KEYS = ("channel_center_x", "channel_w", "channel_top_z",
                 "channel_floor_z_inlet", "channel_y_inlet")


def _fluid_joint_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """Water handover, verified in the pose: A's outlet hands to B's inlet
    DOWNHILL (gravity is the pump — an uphill handover is a pond), with
    compatible channel widths on a shared axis. First real client lands
    with the VF-3 inlet/outlet adapters; the physics is ready now."""
    check = "assembly.fluid_joint_ir"
    fa, fb = form_a.frame, form_b.frame
    missing_a = [k for k in _FLUID_A_KEYS if k not in fa]
    missing_b = [k for k in _FLUID_B_KEYS if k not in fb]
    if missing_a or missing_b:
        sides = []
        if missing_a:
            sides.append(f"{joint.a_ref} lacks {', '.join(missing_a)}")
        if missing_b:
            sides.append(f"{joint.b_ref} lacks {', '.join(missing_b)}")
        return [_finding(
            check, False,
            "fluid_joint expects a: the OUTLET-carrying part and b: the "
            "INLET-carrying part — " + "; ".join(sides),
        )]
    problems: list[str] = []
    # The receiver must be at least as wide as the giver — a rail happily
    # catches a narrow spout, but a wide stream into a narrow inlet spills.
    if fb["channel_w"] < fa["channel_w"] - 0.5:
        problems.append(
            f"receiving channel {fb['channel_w']:g} narrower than the "
            f"giving {fa['channel_w']:g} — the handover spills")
    out_floor = fa["channel_floor_z_outlet"]
    in_floor_posed = pose.apply(
        (fb["channel_center_x"], fb["channel_y_inlet"],
         fb["channel_floor_z_inlet"])
    )[2]
    if in_floor_posed > out_floor + 0.05:
        problems.append(
            f"handover flows UPHILL: outlet floor {out_floor:.2f} into "
            f"inlet floor {in_floor_posed:.2f} — gravity will not pump")
    return [_finding(
        check, not problems,
        f"downhill handover ({out_floor:.2f} -> {in_floor_posed:.2f}) with "
        "matched channels" if not problems else "; ".join(problems),
        measured=out_floor - in_floor_posed, limit=0.0,
    )]


_register(JointDecl(
    name="fluid_joint",
    description="water/nutrient line handover: outlet hands to inlet "
                "downhill with matched channel widths (VF-3 adapters are "
                "the first client; the physics is ready)",
    ir_check=_fluid_joint_ir,
    cad_checks=("assembly.no_interference",),
))


# -- lap_flow_joint (VF correction: flush module-to-module handover) -------------

#: The lap handover bands, measured IN THE POSE (the form check proved the
#: same numbers on each part alone; here the two parts prove them against
#: each other).
LAP_DZ_TOL = 0.05          # floors coplanar — flush means flush
LAP_FACE_GAP_BAND = (0.3, 0.6)
LAP_OVERLAP_BAND = (3.0, 6.0)   # lip length reaching INTO the receiver
LAP_JOINT_SIDE_CLEAR = (0.3, 0.5)
LAP_JOINT_SLOT_BAND = (0.5, 2.5)

_LAP_A_KEYS = ("lap_lip_len", "lap_lip_w", "lap_lip_t", "lap_lip_top_z",
               "channel_floor_z_outlet", "channel_w", "rail_y0", "face_gap")
_LAP_B_KEYS = ("lap_pocket_len", "lap_pocket_w", "channel_floor_z_inlet",
               "channel_w", "rail_y1")


def _lap_flow_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """The flush handover: a's lap lip nests in b's FLOORED lip-seat receiver
    with the floors COPLANAR (dZ = 0 — nothing falls between modules), the
    faces at the controlled gap, the lip overlapping 3-6 into the opening
    and the deliberate 0.5-2.5 slot left at the tip. The receiver is closed
    below (VF-9) — no external downward leak at the seam. a: is the UPSTREAM
    rail (outlet), b: the downstream (inlet)."""
    check = "assembly.lap_flow_ir"
    fa, fb = form_a.frame, form_b.frame
    if "outlet" not in joint.a_datum or "inlet" not in joint.b_datum:
        return [_finding(
            check, False,
            "lap_flow_joint mates a: the upstream OUTLET datum onto b: the "
            f"downstream INLET datum — got a.{joint.a_datum} / b.{joint.b_datum}",
        )]
    missing = [k for k in _LAP_A_KEYS if k not in fa]
    missing += [f"B:{k}" for k in _LAP_B_KEYS if k not in fb]
    if missing:
        return [_finding(
            check, False,
            f"lap frame keys missing: {', '.join(missing)} — both sides "
            "must be corrected flush rails",
        )]
    problems: list[str] = []
    # floors coplanar in the pose — THE flush contract
    out_floor = fa["channel_floor_z_outlet"]
    in_floor = pose.apply(
        (0.0, fb["rail_y1"], fb["channel_floor_z_inlet"]))[2]
    dz = in_floor - out_floor
    if abs(dz) > LAP_DZ_TOL:
        problems.append(
            f"floors not coplanar: dZ = {dz:+.2f} (|dZ| <= {LAP_DZ_TOL:g}) — "
            "a stair step is the old cascade, not a flush row")
    # controlled face gap
    b_face = pose.apply((0.0, fb["rail_y1"], 0.0))[1]
    gap = fa["rail_y0"] - b_face
    if not (LAP_FACE_GAP_BAND[0] - 1e-6 <= gap <= LAP_FACE_GAP_BAND[1] + 1e-6):
        problems.append(
            f"face gap {gap:.2f} outside {LAP_FACE_GAP_BAND[0]}..{LAP_FACE_GAP_BAND[1]} — "
            "flush means one plane with a controlled gap, not contact")
    elif abs(gap - fa["face_gap"]) > 0.05:
        problems.append(
            f"posed face gap {gap:.2f} != declared face_gap {fa['face_gap']:g}")
    # lip really lands in the opening
    overlap = fa["lap_lip_len"] - gap
    if not (LAP_OVERLAP_BAND[0] - 1e-6 <= overlap <= LAP_OVERLAP_BAND[1] + 1e-6):
        problems.append(
            f"lip overlap {overlap:.2f} outside "
            f"{LAP_OVERLAP_BAND[0]}..{LAP_OVERLAP_BAND[1]}")
    side = (fb["lap_pocket_w"] - fa["lap_lip_w"]) / 2.0
    if not (LAP_JOINT_SIDE_CLEAR[0] - 1e-6 <= side <= LAP_JOINT_SIDE_CLEAR[1] + 1e-6):
        problems.append(
            f"per-side lip clearance {side:.2f} outside "
            f"{LAP_JOINT_SIDE_CLEAR[0]}..{LAP_JOINT_SIDE_CLEAR[1]}")
    slot = fb["lap_pocket_len"] - overlap
    if not (LAP_JOINT_SLOT_BAND[0] - 1e-6 <= slot <= LAP_JOINT_SLOT_BAND[1] + 1e-6):
        problems.append(
            f"tip slot {slot:.2f} outside "
            f"{LAP_JOINT_SLOT_BAND[0]}..{LAP_JOINT_SLOT_BAND[1]} — the seam "
            "must stay deliberately open, and only just")
    if fb["channel_w"] < fa["channel_w"] - 0.5:
        problems.append(
            f"receiving channel {fb['channel_w']:g} narrower than the "
            f"giving {fa['channel_w']:g}")
    if problems:
        findings = [_finding(check, False, "; ".join(problems))]
    else:
        findings = [_finding(
            check, True,
            f"flush handover: floors coplanar (dZ {dz:+.2f}), face gap {gap:.2f}, "
            f"lip {overlap:.1f} into the opening, {slot:.1f} slot at the tip",
            measured=dz, limit=LAP_DZ_TOL,
        )]
    # VF-9: the receiver is a FLOORED lip-seat — no open bottom under the seam,
    # so water crosses over the nested lip with no external downward leak (only
    # the controlled top tip-slot stays open).
    pf = fb.get("lap_pocket_floor_z")
    floored = pf is not None and pf > 0.05
    findings.append(_finding(
        "assembly.lap_joint_no_external_downward_leak", floored,
        f"the lap receiver is floored (pocket floor z={pf:.1f}) — no open path "
        "straight down at the seam"
        if floored else
        "the lap receiver is open-bottom — water would leak straight down at the seam"))
    return findings


_register(JointDecl(
    name="lap_flow_joint",
    description="flush module-to-module water handover: the upstream lap "
                "lip continues the floor plane into the downstream FLOORED "
                "lip-seat receiver — dZ = 0, controlled face gap, deliberate "
                "tip slot, no downward leak (closed below)",
    ir_check=_lap_flow_ir,
    cad_checks=("assembly.no_interference",),
))


# -- saddle_hang (vertical farm: adapter hangs on a rail wall) -------------------
#
# An AUXILIARY VERIFICATION JOINT: it never realizes a fluid port (it is
# not in fluid_inlet/fluid_outlet's joints tuple, so no_orphan_ports does
# not count it). fluid_joint sets the pose; saddle_hang proves the
# adapter's physical hang is CONSISTENT with that pose — the saddle really
# straddles the wall, rests on its top, and the spout/tongue fits the
# corridor it dips through.

SADDLE_PLAY_BAND = (0.2, 2.0)
HOOK_LEDGE_BAND = (2.5, 6.0)   # VF-9 Part B: short rest ledge onto the wall top
SADDLE_REST_TOL = 0.3

_SADDLE_A_KEYS = ("rail_y0", "rail_y1", "seat_v0", "seat_v1", "body_h", "channel_w")
_SADDLE_B_KEYS = ("saddle_slot_y0", "saddle_slot_y1", "saddle_floor_z", "spout_w")


def _cap_drip_lands_in_channel_safe_floor(form_a: PartForm) -> Finding:
    """VF-9: the inlet cap drips at the rail's `feed`. The rail's inlet must be
    a CHANNEL-SAFE floor there — the FLOORED lip-seat pocket or the solid channel
    floor right after it — never a through hole that drops the water to the level
    below. Deliberately NOT fragile on the exact landing point: it passes as long
    as no open-bottom `*_lap_receiver` cutbox sits under the feed column."""
    check = "assembly.cap_drip_lands_in_channel_safe_floor"
    fa = form_a.frame
    yin = fa.get("channel_y_inlet")
    through = None
    for c in form_a.cutboxes:
        if "lap_receiver" not in c.name:
            continue
        b = c.box
        if (yin is None or (b.y0 - 0.5 <= yin <= b.y1 + 0.5)) and b.z0 <= 0.05:
            through = c
            break
    ok = through is None
    return _finding(
        check, ok,
        "the cap drips onto a channel-safe floor (floored lip-seat / solid "
        "channel floor) — no fall-through"
        if ok else
        f"the cap drips over a through hole {through.name!r} — water would fall "
        "to the level below; the inlet receiver must be FLOORED")


def _saddle_hang_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    check = "assembly.saddle_hang_ir"
    fa, fb = form_a.frame, form_b.frame
    missing = [k for k in _SADDLE_A_KEYS if k not in fa]
    missing += [f"B:{k}" for k in _SADDLE_B_KEYS if k not in fb]
    if missing:
        return [_finding(
            check, False,
            f"saddle frame keys missing: {', '.join(missing)} — a: must be "
            "the rail, b: the hanging adapter",
        )]
    lo = pose.apply((0.0, fb["saddle_slot_y0"], 0.0))[1]
    hi = pose.apply((0.0, fb["saddle_slot_y1"], 0.0))[1]
    slot_y0, slot_y1 = sorted((lo, hi))
    back = (slot_y0 + slot_y1) / 2.0 > 0.0
    # which wall the adapter hangs on: the one whose span the slot covers
    if back:
        wall_lo, wall_hi = fa["seat_v1"], fa["rail_y1"]
    else:
        wall_lo, wall_hi = fa["rail_y0"], fa["seat_v0"]
    problems: list[str] = []
    hook = fb.get("hang_mode", 0.0) >= 0.5
    if hook:
        # VF-9 Part B one-sided Г-hook: the leg grips the wall's OUTBOARD face
        # and a SHORT ledge rests on the outboard part of the wall top — it does
        # NOT straddle to the inboard face (that would need an un-printable leg
        # in the seat). Capture: leg gap at the face + ledge reach onto the top.
        face = wall_hi if back else wall_lo
        reach = (face - slot_y0) if back else (slot_y1 - face)  # inboard onto top
        leg_gap = (slot_y1 - face) if back else (face - slot_y0)  # off the face
        wall_t = fa["rail_y1"] - fa["seat_v1"]
        if not (HOOK_LEDGE_BAND[0] - 1e-6 <= reach <= HOOK_LEDGE_BAND[1] + 1e-6):
            problems.append(
                f"hook ledge reach {reach:.2f} onto the wall top outside "
                f"{HOOK_LEDGE_BAND[0]}..{HOOK_LEDGE_BAND[1]} — a short rest, not a "
                "deep cantilever")
        elif reach > wall_t - 1.0:
            problems.append(
                f"hook ledge reach {reach:.2f} exceeds the wall top {wall_t:.1f} "
                "— it would overhang past the inboard edge")
        if not (SADDLE_PLAY_BAND[0] - 1e-6 <= leg_gap <= SADDLE_PLAY_BAND[1] + 1e-6):
            problems.append(
                f"leg gap {leg_gap:.2f} off the wall face outside "
                f"{SADDLE_PLAY_BAND[0]}..{SADDLE_PLAY_BAND[1]} — the hook does not "
                "grip the outboard face")
    else:
        play_lo = wall_lo - slot_y0
        play_hi = slot_y1 - wall_hi
        for label, play in (("inner", play_lo), ("outer", play_hi)):
            if not (SADDLE_PLAY_BAND[0] - 1e-6 <= play <= SADDLE_PLAY_BAND[1] + 1e-6):
                problems.append(
                    f"{label} saddle play {play:.2f} outside "
                    f"{SADDLE_PLAY_BAND[0]}..{SADDLE_PLAY_BAND[1]} — the saddle "
                    "does not straddle the wall in this pose")
    rest_z = pose.apply((0.0, 0.0, fb["saddle_floor_z"]))[2]
    if abs(rest_z - fa["body_h"]) > SADDLE_REST_TOL:
        problems.append(
            f"saddle floor lands at z={rest_z:.2f}, the wall top is "
            f"{fa['body_h']:g} — the adapter floats or clips")
    if fb["spout_w"] > fa["channel_w"] - 2.0:
        problems.append(
            f"spout/tongue {fb['spout_w']:g} does not fit the "
            f"{fa['channel_w']:g} channel it dips into")
    kind = "Г-hook grips the wall" if hook else "saddle straddles the wall"
    if problems:
        findings = [_finding(check, False, "; ".join(problems))]
    else:
        findings = [_finding(
            check, True,
            f"{kind}, rests on its top at z={rest_z:.1f}, spout fits the channel",
            measured=rest_z, limit=fa["body_h"],
        )]
    # VF-9: emit cap_drip_lands_in_channel_safe_floor ONLY for the inlet-cap ->
    # rail.feed mate (a: rail.feed, carries channel_y_inlet; b: the cap, carries a
    # hose bore) — NEVER the collector saddle (a: rail.drain_edge, no hose bore).
    if ("feed" in (joint.a_datum or "") and "channel_y_inlet" in fa
            and "hose_bore_d" in fb):
        findings.append(_cap_drip_lands_in_channel_safe_floor(form_a))
    return findings


_register(JointDecl(
    name="saddle_hang",
    description="auxiliary verification joint: the adapter's saddle "
                "straddles and rests on the rail wall in the pose the "
                "fluid joint set — never realizes a fluid port",
    ir_check=_saddle_hang_ir,
    cad_checks=("assembly.no_interference",),
))


# -- profile_perch (VF-4: rail groove on the aluminum carrier) --------------------

PERCH_FIT_BAND = (0.1, 0.5)  # per-side groove clearance over the profile

_PERCH_A_KEYS = ("profile_slot_w", "profile_slot_x", "profile_slot_depth",
                 "profile_slot_clearance")
_PERCH_B_KEYS = ("profile_size", "profile_len", "profile_slope_deg")


def _profile_perch_ir(
    form_a: PartForm, form_b: PartForm, pose: Pose, joint: JointUse
) -> list[Finding]:
    """The rail's bottom groove seats on the aluminum profile carrier:
    width fit in the push-on band, groove deep enough to swallow the
    contact, flow axes aligned. A = the rail (groove), B = the straight
    profile reference. Row-level support truth (full seating, span gap
    zero) lives in assembly.profile_support_full_length — this joint
    verifies the LOCAL seat fit."""
    check = "assembly.profile_perch_ir"
    fa, fb = form_a.frame, form_b.frame
    missing = [k for k in _PERCH_A_KEYS if k not in fa]
    missing += [f"B:{k}" for k in _PERCH_B_KEYS if k not in fb]
    if missing:
        return [_finding(
            check, False,
            "profile_perch expects a: the rail (groove keys) and b: the "
            f"profile reference — missing {', '.join(missing)}",
        )]
    problems: list[str] = []
    per_side = (fa["profile_slot_w"] - fb["profile_size"]) / 2.0
    if not (PERCH_FIT_BAND[0] - 1e-6 <= per_side <= PERCH_FIT_BAND[1] + 1e-6):
        problems.append(
            f"groove {fa['profile_slot_w']:g} over profile "
            f"{fb['profile_size']:g}: per-side fit {per_side:.2f} outside "
            f"{PERCH_FIT_BAND[0]}..{PERCH_FIT_BAND[1]} — wrong profile size "
            "or slot width")
    if fa["profile_slot_depth"] < 3.0:
        problems.append(
            f"groove only {fa['profile_slot_depth']:g} deep — no lateral "
            "capture on the profile")
    if problems:
        return [_finding(check, False, "; ".join(problems))]
    return [_finding(
        check, True,
        f"groove seats the {fb['profile_size']:g} profile with "
        f"{per_side:.2f} per-side fit",
        measured=per_side, limit=PERCH_FIT_BAND[1],
    )]


_register(JointDecl(
    name="profile_perch",
    description="rail bottom groove seated on the aluminum profile carrier "
                "(straight reference): width fit and capture verified locally; "
                "row-level truth in assembly.profile_support_full_length",
    ir_check=_profile_perch_ir,
    cad_checks=("assembly.no_interference",),
))
