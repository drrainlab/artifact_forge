"""The assembly pipeline — validate and build multi-part products.

Mirrors the single-part discipline exactly: everything IR-checkable runs
WITHOUT CAD (``forge validate`` on an assembly never imports cadquery);
the build step compiles each part with the ordinary per-part pipeline
(each STL exported in ITS OWN print orientation), then verifies the fit
in the assembled pose with cross-part probes and writes assembled.step as
a COMPOUND (no boolean fuse — placement for the eyes, intersection only
inside probes).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..catalog.loader import Catalog, CatalogError, load_catalog
from ..core.findings import Finding, Level, Status
from ..pipeline import PipelineFailure, PipelineState, pre_cad_from_instance
from ..product.assembly import AssemblyInstance, JointUse
from .joints import (IDENTITY_POSE, JOINT_TYPES, JointError, Pose,
                     compose_pose, compute_pose, inverse_pose)
from .mates import interface_findings, resolve_port_anchor


def load_assembly(path: Path) -> AssemblyInstance:
    try:
        doc = yaml.safe_load(Path(path).read_text())
    except yaml.YAMLError as exc:
        raise CatalogError(f"{path}: not valid YAML: {exc}") from exc
    try:
        return AssemblyInstance.model_validate(doc)
    except Exception as exc:  # pydantic ValidationError
        raise CatalogError(f"{path}: {exc}") from exc


def validate_assembly(asm: AssemblyInstance, catalog: Catalog) -> None:
    """Fail-fast name binding: joint types against the registry, features
    against the vocabulary. Part instances are validated by the per-part
    pre-CAD run (same code path as single products)."""
    for joint in asm.joints:
        if joint.type not in JOINT_TYPES:
            raise CatalogError(
                f"assembly {asm.id!r}: unknown joint type {joint.type!r}; "
                f"known: {sorted(JOINT_TYPES)}"
            )
    for feature in asm.contract.must_have:
        if feature not in catalog.features:
            raise CatalogError(
                f"assembly {asm.id!r}: unknown feature {feature!r} in contract"
            )


def _inject_shared(asm: AssemblyInstance, catalog: Catalog) -> dict[str, Any]:
    """shared parameters land in every part whose archetype declares the
    parameter — mating dimensions are stated ONCE. Returns instances by ref."""
    instances = {}
    for part in asm.parts:
        instance = part.product
        applicable = {
            k: v
            for k, v in asm.shared.items()
            if k in catalog.archetype_for(instance).parameters
        }
        if applicable:
            data = instance.model_dump(by_alias=True)
            data["params"] = {**data.get("params", {}), **applicable}
            instance = type(instance).model_validate(data)
        instances[part.ref] = instance
    return instances


def _joint_findings(
    asm: AssemblyInstance,
    states: dict[str, PipelineState],
    ir_eval: Any = None,
) -> tuple[list[Finding], dict[str, Pose], list[dict[str, Any]]]:
    """IR-level joint verification + the assembly poses (root = identity;
    every joint poses its B part; recorded for the report). ``ir_eval``
    lets the evaluation session memoize the per-joint check — ONE loop
    serves both the plain and the cached paths."""
    if ir_eval is None:
        def ir_eval(decl, joint, form_a, form_b, pose):
            return decl.ir_check(form_a, form_b, pose, joint)
    findings: list[Finding] = []
    poses: dict[str, Pose] = {asm.root: IDENTITY_POSE}
    pose_report: list[dict[str, Any]] = [
        {"part": asm.root, "transform": "identity"}
    ]
    for i, joint in enumerate(asm.joints):
        decl = JOINT_TYPES[joint.type]
        joint = resolve_port_anchor(joint, states)
        form_a = states[joint.a_ref].form
        form_b = states[joint.b_ref].form
        if form_a is None or form_b is None:
            findings.append(Finding(
                check="assembly.joint_pose", status=Status.FAIL,
                level=Level.ASSEMBLY,
                message=f"joint {i} ({joint.type}): a part failed to build its form",
                critical=True,
            ))
            continue
        try:
            pose = compute_pose(joint, form_a, form_b)
        except JointError as exc:
            findings.append(Finding(
                check="assembly.joint_pose", status=Status.FAIL,
                level=Level.ASSEMBLY,
                message=str(exc), critical=True,
            ))
            continue
        # Ordering guard: a joint may only hang B off an ALREADY-POSED A.
        # Without this, a misordered joint list silently posed B against
        # the root origin — the worst kind of wrong (looks assembled,
        # water flows nowhere). List joints in chain order.
        if joint.a_ref != asm.root and joint.a_ref not in poses:
            findings.append(Finding(
                check="assembly.joint_pose", status=Status.FAIL,
                level=Level.ASSEMBLY,
                message=(
                    f"joint {i} ({joint.type}): part {joint.a_ref!r} is not "
                    "posed yet — list joints in chain order (each a: must "
                    "reference the root or an already-posed part)"
                ),
                critical=True,
            ))
            continue
        # Chained joints (B mates a part that is itself posed): the global
        # pose composes through the parent — quarter turns are closed
        # under composition, so a ROTATED parent composes exactly (a box
        # riding a flipped dovetail carriage is a legal chain). The
        # ir_check below still sees the RELATIVE pose; only the global
        # placement composes.
        parent = poses.get(joint.a_ref)
        pose_global = pose
        if parent is not None and parent is not IDENTITY_POSE:
            pose_global = compose_pose(parent, pose)
        if joint.b_ref != asm.root and joint.b_ref not in poses:
            poses[joint.b_ref] = pose_global
            pose_report.append({
                "part": joint.b_ref,
                "rotate": list(pose_global.rotate),
                "translate": [round(v, 4) for v in pose_global.translate],
                "derived_from": f"{joint.type}_{i}",
            })
        # IR checks always see the RELATIVE pose (B in A's frame) — that is
        # what the mating arithmetic is written against.
        findings.extend(ir_eval(decl, joint, form_a, form_b, pose))
    for part in asm.parts:
        if part.ref not in poses:
            findings.append(Finding(
                check="assembly.joint_pose", status=Status.FAIL,
                level=Level.ASSEMBLY,
                message=f"part {part.ref!r} is not posed by any joint",
                critical=True,
            ))
    findings.extend(interface_findings(asm, states))
    # Pack-contributed assembly findings (e.g. the VF pack's carrier/row
    # verification).
    from ..packs import ASSEMBLY_FINDING_HOOKS

    for hook in ASSEMBLY_FINDING_HOOKS:
        findings.extend(hook(asm, states, poses, findings))
    return findings, poses, pose_report


def run_assembly_validate(path: Path, strict_flag: bool | None) -> dict[str, Any]:
    return validate_assembly_doc(load_assembly(path), load_catalog(), strict_flag)


def validate_assembly_doc(
    asm: AssemblyInstance, catalog: Catalog, strict_flag: bool | None
) -> dict[str, Any]:
    """CAD-free assembly validation on an already-parsed document — a thin
    one-pass facade over a fresh evaluation session. Callers that
    re-validate repeatedly (the intent repair loop) hold their own session
    to reuse the cache across attempts."""
    from .evaluation import AssemblyEvaluationSession

    return AssemblyEvaluationSession(catalog).validate(
        asm, strict_flag=strict_flag)


class AssemblyFailure(PipelineFailure):
    def __init__(self, report: dict[str, Any], message: str, code: int = 4) -> None:
        super().__init__(message, code=code)
        self.report = report


def run_assembly_build(
    path: Path, out_dir: Path, strict_flag: bool | None
) -> dict[str, Any]:
    """Per-part builds + cross-part fit probes in the assembled pose."""
    from ..compiler.pipeline import run_build_from_state  # cadquery import point
    from ..cad.assembly import (
        export_assembled_step,
        place,
        interference_volume,
    )
    from ..cad.probes import channel_probe, solid_fraction
    catalog = load_catalog()
    asm = load_assembly(path)
    strict = asm.strict if strict_flag is None else strict_flag
    validate_assembly(asm, catalog)
    instances = _inject_shared(asm, catalog)
    states = {
        ref: pre_cad_from_instance(inst, catalog, strict)
        for ref, inst in instances.items()
    }
    joint_findings, poses, pose_report = _joint_findings(asm, states)
    # Joint IR gate BEFORE any CAD: a mismatched mount_bc must never reach
    # the compiler.
    hard = [f for f in joint_findings if f.critical and f.status is Status.FAIL]
    if strict and hard:
        raise PipelineFailure(
            "strict: joint failures: " + ", ".join(sorted({f.check for f in hard})),
            code=4,
        )

    target = out_dir / asm.id
    parts_out: dict[str, Any] = {}
    geometries = {}
    for ref, state in states.items():
        state.enforce_strict()
        built, geometry = run_build_from_state(state, target / ref)
        parts_out[ref] = {
            "status": built["status"],
            "grade": built.get("score", {}).get("grade"),
            "exports": built["exports"],
        }
        geometries[ref] = geometry

    def afind(check: str, ok: bool, message: str, *, measured: float | None = None,
              limit: float | None = None) -> Finding:
        return Finding(
            check=check, status=Status.PASS if ok else Status.FAIL,
            level=Level.ASSEMBLY, message=message, critical=not ok,
            measured=measured, limit=limit,
            unit="" if measured is None else "mm3" if "volume" in message else "",
        )

    placed = {ref: place(geometries[ref], poses[ref]) for ref in geometries if ref in poses}

    # -- assembly.no_interference: parts may TOUCH, never overlap — except
    # the overlap a press fit DECLARES (the pin is thicker than its bore
    # by the interference; that annulus is the joint working as designed).
    import math as _math

    allowed = 2.0
    for joint in asm.joints:
        if joint.type not in ("press_fit_pin_pair", "butt_pin_joint"):
            continue
        interference = float(joint.params.get("interference", 0.1))
        for pin in states[joint.b_ref].form.pins:
            allowed += _math.pi * pin.d * (interference / 2.0) * pin.length * 1.5
    refs = list(placed)
    worst_overlap = 0.0
    worst_pair = ""
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            vol = interference_volume(placed[refs[i]], placed[refs[j]])
            if vol > worst_overlap:
                worst_overlap = vol
                worst_pair = f"{refs[i]}<->{refs[j]}"
    joint_findings.append(afind(
        "assembly.no_interference",
        worst_overlap <= allowed,
        f"worst pairwise overlap volume {worst_overlap:.2f} mm3"
        + (f" ({worst_pair})" if worst_pair else "")
        + f" (allowed {allowed:.2f}: weld-level contact plus declared "
        "press-fit interference)",
        measured=worst_overlap, limit=allowed,
    ))

    # -- assembly.screw_axes_clear: every screw must physically pass ------
    for joint in asm.joints:
        if joint.type != "screw_joint":
            continue
        form_b = states[joint.b_ref].form
        pose_b = poses[joint.b_ref]
        blocked = []
        for h in form_b.holes:
            hx, hy, z_top = h.at
            # driver access needs 6mm on the HEAD side; the thread side
            # only pokes 1mm past the exit (into the receiving pilot).
            # countersink_face names the head side — a plate mounted
            # face-down (a wall bracket on a board) has it at "bottom".
            # A PLAIN hole (no countersink) accepts the screw from either
            # side: one clear insertion direction is enough.
            if getattr(h, "countersink", True):
                head_bottom = getattr(h, "countersink_face", "top") == "bottom"
                margins = [(1.0, 6.0)] if head_bottom else [(6.0, 1.0)]
            else:
                margins = [(6.0, 1.0), (1.0, 6.0)]
            frac = float("inf")
            for above, below in margins:
                p_top = pose_b.apply((hx, hy, z_top + above))
                p_bot = pose_b.apply((hx, hy, z_top - h.through - below))
                probe = channel_probe([p_top, p_bot], d=2.6)
                frac = min(frac, max(
                    solid_fraction(placed[r].workplane, probe)
                    for r in placed
                ))
            if frac > 0.05:
                blocked.append(f"({hx:.1f},{hy:.1f}) fill {frac:.2f}")
        joint_findings.append(afind(
            "assembly.screw_axes_clear",
            not blocked,
            "all screw axes pass through the assembled stack"
            if not blocked else "blocked screw axes: " + "; ".join(blocked),
        ))

    # -- assembly.lid_seats: the plug really sits inside the rim ----------
    for joint in asm.joints:
        if joint.type != "lid_seat":
            continue
        fa = states[joint.a_ref].form.frame
        fb = states[joint.b_ref].form.frame
        pose_b = poses[joint.b_ref]
        pose_a = poses[joint.a_ref]
        # sample the plug's mid-depth center: must be BELOW the rim plane
        # and inside the interior void of the box (not resting on top).
        # The interior bounds are BOX-LOCAL — compare in the box frame
        # (the esp32 example's box was the root, which hid this; a
        # station's box sits deep in a posed chain).
        probe_pt = pose_b.apply((0.0, 0.0, fb["plug_mid_z"]))
        inv_a = inverse_pose(pose_a)
        local_pt = inv_a.apply(probe_pt)
        inside = (
            fa["inner_u0"] < local_pt[0] < fa["inner_u1"]
            and fa["inner_v0"] < local_pt[1] < fa["inner_v1"]
            and local_pt[2] < fa["shell_h"]
        )
        # and the box material must NOT be there (it is the interior
        # void) — probe 1mm down IN THE BOX FRAME, posed back to global
        second_pt = pose_a.apply(
            (local_pt[0], local_pt[1], local_pt[2] - 1.0))
        box_probe_ = channel_probe([probe_pt, second_pt], d=3.0)
        frac = solid_fraction(placed[joint.a_ref].workplane, box_probe_)
        joint_findings.append(afind(
            "assembly.lid_seats",
            inside and frac < 0.05,
            f"plug center sits {'inside' if inside else 'OUTSIDE'} the rim "
            f"(box material fraction at plug {frac:.2f})",
        ))

    # -- assembly.pins_engage: pins physically occupy their receivers -----
    for joint in asm.joints:
        if joint.type != "press_fit_pin_pair":
            continue
        form_b = states[joint.b_ref].form
        pose_b = poses[joint.b_ref]
        missing = []
        for pin in form_b.pins:
            px, py = pin.at
            top = pose_b.apply((px, py, pin.z0 + pin.length - 0.5))
            bot = pose_b.apply((px, py, pin.z0 + 0.5))
            probe = channel_probe([top, bot], d=pin.d * 0.6)
            # the PIN part's own material must fill this line in the pose
            frac = solid_fraction(placed[joint.b_ref].workplane, probe)
            if frac < 0.9:
                missing.append(f"{pin.name} (fill {frac:.2f})")
                continue
            # and the receiving part must be void there (the bore) — the
            # interference itself is IR-verified; here we prove engagement
            recv = solid_fraction(placed[joint.a_ref].workplane, probe)
            if recv > 0.4:
                missing.append(f"{pin.name} collides with receiver body ({recv:.2f})")
        joint_findings.append(afind(
            "assembly.pins_engage",
            not missing,
            "all pins engage their receivers in the pose"
            if not missing else "pins not engaged: " + "; ".join(missing),
        ))

    # -- assembly.hooks_engage: snap lips physically sit in the windows ---
    for joint in asm.joints:
        if joint.type != "snap_joint":
            continue
        form_b = states[joint.b_ref].form
        pose_b = poses[joint.b_ref]
        prefix = str(joint.params.get("hooks", "snap"))
        missing = []
        for lip in [r for r in form_b.ribs if r.name.startswith(f"{prefix}_lip")]:
            b = lip.box
            center = pose_b.apply(
                ((b.x0 + b.x1) / 2.0, (b.y0 + b.y1) / 2.0, (b.z0 + b.z1) / 2.0)
            )
            probe = channel_probe(
                [(center[0], center[1] - 1.0, center[2]),
                 (center[0], center[1] + 1.0, center[2])], d=1.2
            )
            own = solid_fraction(placed[joint.b_ref].workplane, probe)
            host = solid_fraction(placed[joint.a_ref].workplane, probe)
            if own < 0.8:
                missing.append(f"{lip.name} lip missing in pose ({own:.2f})")
            elif host > 0.3:
                missing.append(f"{lip.name} collides with the wall ({host:.2f})")
        joint_findings.append(afind(
            "assembly.hooks_engage",
            not missing,
            "all snap lips sit in their windows"
            if not missing else "; ".join(missing),
        ))

    # -- assembly.channel_continuous_across: THE demo check ---------------
    if asm.wiring is not None:
        joint_findings.append(_wiring_check(asm, states, poses, placed, afind))

    # -- assembled.step: compound, poses baked, no fuse -------------------
    step_path = export_assembled_step(placed, target / "assembled.step")

    # -- contract: joint features built iff their checks passed -----------
    passed = {f.check for f in joint_findings if f.status is Status.PASS}
    failed = {f.check for f in joint_findings if f.status is Status.FAIL}
    # Part-level checks count toward assembly features too: a feature may
    # be verified by form/topology checks measured on each part (e.g. the
    # lap seam leak path). Built iff EVERY part measuring the check passes.
    for state in states.values():
        for f in state.report.findings:
            if f.status is Status.PASS:
                passed.add(f.check)
            elif f.status is Status.FAIL:
                failed.add(f.check)
    built_features = []
    for feature in asm.contract.must_have:
        verified_by = catalog.features[feature].verified_by
        if all(c in passed and c not in failed for c in verified_by):
            built_features.append(feature)
        else:
            joint_findings.append(Finding(
                check=f"contract.must_have:{feature}", status=Status.FAIL,
                level=Level.CONTRACT,
                message=f"{feature} NOT verified as built",
                critical=True,
            ))

    grades = [p["grade"] for p in parts_out.values() if p.get("grade")]
    hard_fails = [f for f in joint_findings if f.critical and f.status is Status.FAIL]
    grade = "F" if hard_fails else (max(grades) if grades else "?")  # A<B<...: max = worst
    status = "fail" if hard_fails or any(
        p["status"] != "pass" for p in parts_out.values()
    ) else "pass"

    report = {
        "assembly": asm.id,
        "root": asm.root,
        "parts": parts_out,
        "assembly_pose": pose_report,
        "joints": [f.to_dict() for f in joint_findings],
        "built_features": built_features,
        "exports": {"assembled_step": str(step_path)},
        "status": status,
        "grade": grade,
    }
    if asm.meta:
        report["meta"] = dict(asm.meta)
    from .bom import build_bom

    bom = build_bom(asm, states, catalog)
    bom_path = target / "bom.yaml"
    bom_path.write_text(yaml.safe_dump(bom, sort_keys=False, allow_unicode=True))
    report["bom"] = bom
    report["exports"]["bom"] = str(bom_path)

    # Pack-contributed report sections (e.g. the VF pack's frame report,
    # water contract report and view metadata). A section with a filename
    # is also written next to the assembly report and recorded in exports.
    from ..packs import ASSEMBLY_REPORT_HOOKS

    for hook in ASSEMBLY_REPORT_HOOKS:
        for key, filename, payload in hook(
                asm=asm, states=states, joint_findings=joint_findings,
                poses=poses):
            if payload is None:
                continue
            report[key] = payload
            if filename:
                section_path = target / filename
                section_path.write_text(yaml.safe_dump(
                    payload, sort_keys=False, allow_unicode=True))
                report["exports"][Path(filename).stem] = str(section_path)
    (target / "assembly_report.yaml").write_text(
        yaml.safe_dump(report, sort_keys=False, allow_unicode=True)
    )
    if strict and status != "pass":
        raise AssemblyFailure(
            report,
            "strict: assembly failures: "
            + ", ".join(sorted({f.check for f in hard_fails})),
            code=4,
        )
    return report


def _wiring_check(asm, states, poses, placed, afind) -> Finding:
    """The cable path through BOTH parts in the assembled pose: bracket
    entry -> run -> tip drop -> (posed) cup base exit into the cavity."""
    from ..cad.probes import channel_probe, solid_fraction
    from ..core.values import parse_quantity

    src = states[asm.wiring.from_part]
    dst = states[asm.wiring.to_part]
    f = src.form.frame
    needed = ("channel_x", "channel_entry_u", "channel_z", "channel_drop_y")
    if any(k not in f for k in needed):
        return afind(
            "assembly.channel_continuous_across", False,
            f"{asm.wiring.from_part} declares no droppable channel path "
            f"(needs frame keys {needed})",
        )
    d = parse_quantity(str(asm.wiring.d), "length", where="assembly.wiring.d")
    x, entry_u, z_c, drop_y = (f[k] for k in needed)
    top_z = f.get("flange_t", 5.0) + 2.0
    # The channel keys are SOURCE-LOCAL — pose them into the assembly
    # frame (the desk-lamp bracket happened to be the root, which hid
    # this; a station's bracket is posed).
    src_pose = poses[asm.wiring.from_part]
    dst_pose = poses[asm.wiring.to_part]
    exit_end = dst_pose.apply((0.0, 0.0, dst.form.params.get("base_t", 3.0) + 2.0))
    p0 = src_pose.apply((x, entry_u, top_z))
    p1 = src_pose.apply((x, entry_u, z_c))
    p2 = src_pose.apply((x, drop_y, z_c))
    # the drop continues from the posed drop point into the cup cavity
    path = [p0, p1, p2, (p2[0], p2[1], exit_end[2])]
    # Probe LEG BY LEG and keep the worst: one full-path fraction would
    # dilute a short plug (a too-small cup exit) below the threshold —
    # a 3mm blockage in a 200mm path is 1.5% "clear" and 100% stuck cable.
    worst = 0.0
    for a, b in zip(path, path[1:]):
        probe = channel_probe([a, b], d=0.8 * d)
        if probe is None:
            continue
        worst = max(
            worst,
            max(solid_fraction(placed[r].workplane, probe) for r in placed),
        )
    return afind(
        "assembly.channel_continuous_across",
        worst < 0.05,
        f"cable path through {asm.wiring.from_part}+{asm.wiring.to_part}: "
        f"worst leg solid fraction {worst:.3f} — functional continuity "
        "across parts",
        measured=worst, limit=0.05,
    )
