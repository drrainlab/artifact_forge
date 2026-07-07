"""Interface mate resolution (wave A1) — joints land on DECLARED ports.

A joint anchor "ref.name" resolves to a port when the part's archetype
declares an interface whose datum (or id) is that name. Mated ports are
checked for type/gender/accepts/joint legality and declared-fit agreement;
required ports must all be mated (no orphan ports). Dimensional DEPTH
stays in the joint IR checks — this layer never re-measures, it makes the
connection semantics explicit and falsifiable.

Legacy assemblies (bare datums, no interfaces declared) stay legal: a
joint touching no declared port emits nothing; a joint touching exactly
one side's port emits an honest WARN (half-declared connection).
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..product.assembly import AssemblyInstance, JointUse
from ..product.interfaces import (
    AXIS_VECTORS, INTERFACE_TYPES, InterfaceSpec, mate_problems,
)
from .joints import rotate_point


def _world_dir(token: str, rotate: tuple[float, float, float]) -> tuple[int, int, int]:
    v = rotate_point(AXIS_VECTORS[token], rotate)
    return (round(v[0]), round(v[1]), round(v[2]))


def _frames_opposed(a: InterfaceSpec, b: InterfaceSpec, joint: JointUse
                    ) -> list[str]:
    """A1.5: in the pose, mating normals OPPOSE; orientation-sensitive
    types additionally demand up-agreement and exact axis continuity
    (flow direction survives the joint)."""
    rot = (joint.rotate[0], joint.rotate[1], joint.rotate[2])
    an, au = AXIS_VECTORS[a.frame.normal], AXIS_VECTORS[a.frame.up]
    bn, bu = _world_dir(b.frame.normal, rot), _world_dir(b.frame.up, rot)
    problems: list[str] = []
    if tuple(-x for x in bn) != an:
        problems.append(
            f"normals not opposed in the pose: A {a.frame.normal} vs "
            f"B {b.frame.normal} rotated {list(rot)}")
    sensitive = a.decl().orientation_sensitive or b.decl().orientation_sensitive
    if sensitive and bu != au:
        problems.append(
            f"orientation-sensitive mate with disagreeing up: A "
            f"{a.frame.up} vs B {b.frame.up} rotated {list(rot)}")
    if a.frame.axis and b.frame.axis:
        aa = AXIS_VECTORS[a.frame.axis]
        ba = _world_dir(b.frame.axis, rot)
        if sensitive and ba != aa:
            problems.append(
                f"flow/line axis breaks across the joint: A {a.frame.axis} "
                f"vs B {b.frame.axis} rotated {list(rot)}")
        if not sensitive and ba != aa and tuple(-x for x in ba) != aa:
            problems.append(
                f"slide axes not collinear: A {a.frame.axis} vs B "
                f"{b.frame.axis} rotated {list(rot)}")
    return problems


def _finding(check: str, status: Status, message: str,
             critical: bool = False) -> Finding:
    return Finding(check=check, status=status, level=Level.ASSEMBLY,
                   message=message, critical=critical)


def _port_index(archetype) -> dict[str, InterfaceSpec]:
    """Datum name AND interface id both address the port."""
    idx: dict[str, InterfaceSpec] = {}
    for spec in getattr(archetype, "interfaces", ()) or ():
        idx.setdefault(spec.datum, spec)
        idx.setdefault(spec.id, spec)
    return idx


def resolve_port_anchor(joint: JointUse, states) -> JointUse:
    """Port-id anchoring: 'ref.port_id' becomes 'ref.datum' when the name
    is not a published datum but IS a declared interface id."""
    updates: dict[str, str] = {}
    for side, ref, name in (
        ("a", joint.a_ref, joint.a_datum), ("b", joint.b_ref, joint.b_datum),
    ):
        state = states.get(ref)
        if state is None or state.form is None:
            continue
        if name in state.form.datums:
            continue
        spec = next(
            (i for i in getattr(state.archetype, "interfaces", ()) or ()
             if i.id == name), None,
        )
        if spec is not None:
            updates[side] = f"{ref}.{spec.datum}"
    return joint.model_copy(update=updates) if updates else joint


def interface_findings(
    asm: AssemblyInstance, states
) -> list[Finding]:
    findings: list[Finding] = []
    mated: set[tuple[str, str]] = set()  # (part_ref, interface_id)

    for i, joint in enumerate(asm.joints):
        sides = {}
        for side, ref, name in (
            ("a", joint.a_ref, joint.a_datum),
            ("b", joint.b_ref, joint.b_datum),
        ):
            arch = states[ref].archetype
            spec = _port_index(arch).get(name)
            sides[side] = (ref, arch, spec)
        a_ref0, a_arch, a_spec = sides["a"]
        b_ref0, b_arch, b_spec = sides["b"]
        where = f"joint {i} ({joint.type}) {joint.a} <-> {joint.b}"
        if a_spec is None and b_spec is None:
            continue  # fully legacy connection — nothing declared to judge
        if a_spec is None or b_spec is None:
            bare = joint.a if a_spec is None else joint.b
            findings.append(_finding(
                "interface.mate_compatible", Status.WARN,
                f"{where}: {bare} is a bare datum — connection only half "
                "declared (declare the counterpart interface)",
            ))
            continue
        # A joint whose type does not realize the port pair is AUXILIARY
        # (the clamp's compression_gap over the heatset datums): it rides
        # declared ports without claiming them — legality is judged
        # without the joint rule, and it does not count as mating for the
        # orphan check (a realizing joint must still exist).
        decl_a = a_spec.decl()
        realizes = joint.type in decl_a.joints
        problems = mate_problems(
            a_spec, b_spec,
            (a_arch.id, a_arch.object_class),
            (b_arch.id, b_arch.object_class),
            joint_type=joint.type if realizes else None,
        )
        if not realizes:
            findings.append(_finding(
                "interface.mate_compatible",
                Status.PASS if not problems else Status.FAIL,
                f"{where}: auxiliary {joint.type} over {a_spec.type} ports "
                "(a realizing joint must mate them separately)"
                if not problems else f"{where}: " + "; ".join(problems),
                critical=bool(problems),
            ))
            continue
        mated.add((a_ref0, a_spec.id))
        mated.add((b_ref0, b_spec.id))
        # declared-fit agreement is its own check, not a mate blocker
        fit = [p for p in problems if "clearances disagree" in p]
        legal = [p for p in problems if p not in fit]
        findings.append(_finding(
            "interface.mate_compatible",
            Status.PASS if not legal else Status.FAIL,
            f"{where}: {a_spec.type} {a_spec.gender}/{b_spec.gender}"
            if not legal else f"{where}: " + "; ".join(legal),
            critical=bool(legal),
        ))
        if a_spec.frame is not None and b_spec.frame is not None:
            frame_problems = _frames_opposed(a_spec, b_spec, joint)
            findings.append(_finding(
                "interface.mate_frames_opposed",
                Status.PASS if not frame_problems else Status.FAIL,
                f"{where}: normals opposed"
                + (", orientation locked"
                   if (a_spec.decl().orientation_sensitive
                       or b_spec.decl().orientation_sensitive) else "")
                if not frame_problems else f"{where}: "
                + "; ".join(frame_problems),
                critical=bool(frame_problems),
            ))
        elif a_spec.frame is not None or b_spec.frame is not None:
            findings.append(_finding(
                "interface.mate_frames_opposed", Status.WARN,
                f"{where}: only one side declares a frame — orientation "
                "unverifiable",
            ))
        if a_spec.clearance is not None or b_spec.clearance is not None:
            findings.append(_finding(
                "interface.clearance_ok",
                Status.PASS if not fit else Status.FAIL,
                f"{where}: declared fit "
                f"{a_spec.clearance if a_spec.clearance is not None else b_spec.clearance:g} mm"
                if not fit else f"{where}: " + "; ".join(fit),
                critical=bool(fit),
            ))
        decl = INTERFACE_TYPES[a_spec.type]
        if decl.fastened and not legal:
            fastening = joint.type == "screw_joint"
            findings.append(_finding(
                "interface.fastener_access_ok",
                Status.PASS if fastening else Status.FAIL,
                f"{where}: screw axes verified at build by "
                "assembly.screw_axes_clear"
                if fastening else
                f"{where}: fastened interface mated by non-fastening "
                f"joint {joint.type!r}",
                critical=not fastening,
            ))

    for part in asm.parts:
        arch = states[part.ref].archetype
        for spec in getattr(arch, "interfaces", ()) or ():
            if spec.assembly_role != "required":
                continue
            if (part.ref, spec.id) not in mated:
                findings.append(_finding(
                    "assembly.no_orphan_ports", Status.FAIL,
                    f"part {part.ref!r}: required interface {spec.id!r} "
                    f"({spec.type}) is not mated by any joint",
                    critical=True,
                ))
    if not any(f.check == "assembly.no_orphan_ports" for f in findings):
        declared = sum(
            1 for p in asm.parts
            for _ in getattr(states[p.ref].archetype, "interfaces", ()) or ()
        )
        if declared:
            findings.append(_finding(
                "assembly.no_orphan_ports", Status.PASS,
                f"all required ports mated ({declared} declared across parts)",
            ))
    return findings
