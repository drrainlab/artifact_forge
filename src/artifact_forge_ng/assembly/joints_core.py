"""Joint registry core — pose math, JointDecl, JOINT_TYPES, _register.

The joint IR builders live in joints_mechanical / joints_fluid; they import
this module and self-register on import. joints.py is the shim that pulls
everything together and preserves the original import paths.
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
    no float drift in poses. Extrinsic (fixed world axes), X then Y then Z
    — the same convention cad.assembly.place and the viewer apply."""
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


def _rotation_matrix(
    rotate: tuple[float, float, float],
) -> tuple[tuple[int, ...], ...]:
    """Integer 3x3 matrix (rows) of a quarter-turn Euler triple — exact."""
    cols = [rotate_point(e, rotate) for e in
            ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    return tuple(
        tuple(int(round(cols[j][i])) for j in range(3)) for i in range(3)
    )


def _mat_mul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def _canonical_euler_table() -> dict[Any, tuple[float, float, float]]:
    """matrix -> the canonical quarter-turn Euler triple producing it.
    The 24 proper quarter-turn rotations are all reachable from angles
    {0, 90, 180, 270}; canonical = fewest non-zero components, then the
    smallest angles — deterministic, always inside the legal set."""
    table: dict[Any, tuple[float, float, float]] = {}
    angles = (0.0, 90.0, 180.0, 270.0)
    candidates = sorted(
        ((rx, ry, rz) for rx in angles for ry in angles for rz in angles),
        key=lambda t: (sum(1 for a in t if a), sum(t), t),
    )
    for triple in candidates:
        table.setdefault(_rotation_matrix(triple), triple)
    return table


_EULER_BY_MATRIX = _canonical_euler_table()


def inverse_pose(pose: Pose) -> Pose:
    """The exact inverse: ``inverse_pose(P).apply(P.apply(x)) == x``.
    Quarter-turn rotations invert by transposition — still integers."""
    m = _rotation_matrix(pose.rotate)
    m_inv = tuple(tuple(m[j][i] for j in range(3)) for i in range(3))
    rotate = _EULER_BY_MATRIX[m_inv]
    tx, ty, tz = pose.translate
    t_inv = tuple(
        -(m_inv[i][0] * tx + m_inv[i][1] * ty + m_inv[i][2] * tz)
        for i in range(3)
    )
    return Pose(rotate=rotate, translate=t_inv)  # type: ignore[arg-type]


def compose_pose(parent: Pose, local: Pose) -> Pose:
    """Global pose of a chained part: ``global.apply(x) ==
    parent.apply(local.apply(x))``. Quarter turns are closed under
    composition — the result is exact integers and its rotate triple
    stays inside the legal set (canonical form from the 24-element
    rotation group)."""
    m = _mat_mul(_rotation_matrix(parent.rotate),
                 _rotation_matrix(local.rotate))
    rotate = _EULER_BY_MATRIX[m]
    return Pose(rotate=rotate, translate=parent.apply(local.translate))


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
class JointParamDecl:
    """Grounding metadata for one ``joint.params`` key.

    NEVER executed: the ir_check remains the single measuring truth. A
    declaration that drifts from the ir_check body is caught by the
    coherence test (tests/assembly/test_joint_grounding.py), not at
    runtime."""

    name: str
    type: str                     # "length" | "count" | "screw" | "prefix" | "number"
    default: Any = None           # None = the param is required
    description: str = ""


@dataclass(frozen=True)
class JointSideDecl:
    """What the ir_check expects one side (A or B) of the joint to expose.

    Grounding metadata for the assembly digest and intent graph-grounding
    — not enforced here; the ir_check measures, this only describes."""

    role: str = ""                          # human-readable: "box shell"
    #: Frame keys the side must carry. "{param}" substitutes the joint
    #: param of that name ("{hooks}_beam_t" -> "<hooks>_beam_t").
    frame_keys: tuple[str, ...] = ()
    #: Name of the joint PARAM holding the bores prefix ("pilots"), or a
    #: literal prefix when the ir_check hardcodes it ("butt_socket").
    bores_prefix: str | None = None
    pins_prefix: str | None = None
    needs_pins: bool = False
    needs_holes: bool = False
    ribs_prefix: str | None = None          # "{hooks}_lip"
    cutboxes_contains: str | None = None    # "snap_window"
    datum_hint: str = ""                    # anchor convention: "rim (rounded_box_shell)"


@dataclass(frozen=True)
class JointDecl:
    name: str
    description: str
    #: (PartForm A, PartForm B, pose of B, joint) -> findings. CAD-free.
    ir_check: Callable[[PartForm, PartForm, Pose, JointUse], list[Finding]]
    #: Assembly-level CAD probe names this joint subscribes to.
    cad_checks: tuple[str, ...]
    # -- grounding metadata (wave G) — empty means "not declared yet"; the
    # -- shrink-only allowlist in test_joint_grounding.py tracks the gap.
    params: tuple[JointParamDecl, ...] = ()
    side_a: JointSideDecl | None = None
    side_b: JointSideDecl | None = None
    #: Pose-chain role. The KERNEL semantics is positional (the first joint
    #: naming an unposed part establishes its pose; later joints of the
    #: same pair only run their ir_check — see pipeline._joint_findings).
    #: This field makes that intent legible to the LLM and the intent
    #: graph-grounding; the kernel never reads it.
    pose_mode: str = "either"               # "establish" | "verify" | "either"
    #: Short YAML fragment for few-shot use in the assembly digest.
    example: str = ""


JOINT_TYPES: dict[str, JointDecl] = {}


def _register(decl: JointDecl) -> None:
    JOINT_TYPES[decl.name] = decl


