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
