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
from ..product.interfaces import INTERFACE_TYPES, InterfaceSpec, mate_problems


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
            if spec is not None:
                mated.add((ref, spec.id))
        _, a_arch, a_spec = sides["a"]
        _, b_arch, b_spec = sides["b"]
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
        problems = mate_problems(
            a_spec, b_spec,
            (a_arch.id, a_arch.object_class),
            (b_arch.id, b_arch.object_class),
            joint_type=joint.type,
        )
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
