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
from typing import Callable

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

    pilots = [b for b in form_a.bores if b.name.startswith(PILOT_PREFIX)]
    holes = list(form_b.holes)
    if len(pilots) != count or len(holes) != count:
        findings.append(_finding(
            "assembly.screw_joint_ir", False,
            f"screw count mismatch: joint wants {count}, "
            f"{joint.a_ref} has {len(pilots)} pilot(s), "
            f"{joint.b_ref} has {len(holes)} hole(s)",
        ))
        return findings

    # B hole centers in the assembled (root) frame. Holes sit on B's mount
    # plane — project each to its plate-bottom point before posing.
    posed = []
    for h in holes:
        hx, hy, z_top = h.at
        posed.append(pose.apply((hx, hy, z_top - h.through)))
    worst = 0.0
    for b in pilots:
        px, py, _ = b.center
        best = min(math.hypot(px - q[0], py - q[1]) for q in posed)
        worst = max(worst, best)
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
