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
from .joints import IDENTITY_POSE, JOINT_TYPES, JointError, Pose, compute_pose
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
) -> tuple[list[Finding], dict[str, Pose], list[dict[str, Any]]]:
    """IR-level joint verification + the assembly poses (root = identity;
    every joint poses its B part; recorded for the report)."""
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
        # pose composes through the parent. v1 composes pure translations
        # only — a rotated parent would need Euler composition, and no
        # current pack chains through one; refuse honestly instead.
        parent = poses.get(joint.a_ref)
        pose_global = pose
        if parent is not None and parent is not IDENTITY_POSE:
            if any(abs(a) > 1e-9 for a in parent.rotate):
                findings.append(Finding(
                    check="assembly.joint_pose", status=Status.FAIL,
                    level=Level.ASSEMBLY,
                    message=(
                        f"joint {i} ({joint.type}): chaining through the "
                        f"ROTATED part {joint.a_ref!r} is not supported in v1"
                    ),
                    critical=True,
                ))
                continue
            pose_global = Pose(
                rotate=pose.rotate,
                translate=(
                    pose.translate[0] + parent.translate[0],
                    pose.translate[1] + parent.translate[1],
                    pose.translate[2] + parent.translate[2],
                ),
            )
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
        findings.extend(decl.ir_check(form_a, form_b, pose, joint))
    for part in asm.parts:
        if part.ref not in poses:
            findings.append(Finding(
                check="assembly.joint_pose", status=Status.FAIL,
                level=Level.ASSEMBLY,
                message=f"part {part.ref!r} is not posed by any joint",
                critical=True,
            ))
    findings.extend(interface_findings(asm, states))
    return findings, poses, pose_report


def run_assembly_validate(path: Path, strict_flag: bool | None) -> dict[str, Any]:
    catalog = load_catalog()
    asm = load_assembly(path)
    strict = asm.strict if strict_flag is None else strict_flag
    validate_assembly(asm, catalog)
    instances = _inject_shared(asm, catalog)
    states = {
        ref: pre_cad_from_instance(inst, catalog, strict)
        for ref, inst in instances.items()
    }
    joint_findings, _, pose_report = _joint_findings(asm, states)

    parts_summary = {ref: st.summary() for ref, st in states.items()}
    critical_joint = [f for f in joint_findings if f.critical and f.status is Status.FAIL]
    status = "fail" if critical_joint or any(
        s["status"] == "fail" for s in parts_summary.values()
    ) else "pass"
    out = {
        "assembly": asm.id,
        "root": asm.root,
        "parts": parts_summary,
        "assembly_pose": pose_report,
        "joints": [f.to_dict() for f in joint_findings],
        "status": status,
    }
    if asm.meta:
        out["meta"] = dict(asm.meta)
    if strict:
        for ref, st in states.items():
            st.enforce_strict()
        if critical_joint:
            raise AssemblyFailure(
                out,
                "strict: joint failures: "
                + ", ".join(f.check for f in critical_joint),
                code=4,
            )
    return out


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
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            worst_overlap = max(
                worst_overlap,
                interference_volume(placed[refs[i]], placed[refs[j]]),
            )
    joint_findings.append(afind(
        "assembly.no_interference",
        worst_overlap <= allowed,
        f"worst pairwise overlap volume {worst_overlap:.2f} mm3 (allowed "
        f"{allowed:.2f}: weld-level contact plus declared press-fit "
        "interference)",
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
            p_top = pose_b.apply((hx, hy, z_top + 6.0))
            p_bot = pose_b.apply((hx, hy, z_top - h.through - 1.0))
            probe = channel_probe([p_top, p_bot], d=2.6)
            frac = max(
                solid_fraction(placed[r].workplane, probe) for r in placed
            )
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
        # sample the plug's mid-depth center: must be BELOW the rim plane
        # and inside the interior void of the box (not resting on top)
        probe_pt = pose_b.apply((0.0, 0.0, fb["plug_mid_z"]))
        inside = (
            fa["inner_u0"] < probe_pt[0] < fa["inner_u1"]
            and fa["inner_v0"] < probe_pt[1] < fa["inner_v1"]
            and probe_pt[2] < fa["shell_h"]
        )
        # and the box material must NOT be there (it is the interior void)
        box_probe_ = channel_probe(
            [probe_pt, (probe_pt[0], probe_pt[1], probe_pt[2] - 1.0)], d=3.0
        )
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
    # Vertical farm pack: the water contract report + view metadata, when
    # any part carries a water channel (dry assemblies stay untouched).
    from .bom import build_bom
    from .water_report import build_views, build_water_report

    bom = build_bom(asm, states, catalog)
    bom_path = target / "bom.yaml"
    bom_path.write_text(yaml.safe_dump(bom, sort_keys=False, allow_unicode=True))
    report["bom"] = bom
    report["exports"]["bom"] = str(bom_path)

    water = build_water_report(states, joint_findings, asm=asm, poses=poses)
    if water is not None:
        water_path = target / "water_report.yaml"
        water_path.write_text(
            yaml.safe_dump(water, sort_keys=False, allow_unicode=True)
        )
        report["water"] = water
        report["exports"]["water_report"] = str(water_path)
    views = build_views(asm, states, poses)
    if views is not None:
        report["views"] = views
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
    # continue past the mount plane through the posed cup base to its cavity
    dst_pose = poses[asm.wiring.to_part]
    exit_end = dst_pose.apply((0.0, 0.0, dst.form.params.get("base_t", 3.0) + 2.0))
    path = [
        (x, entry_u, top_z),
        (x, entry_u, z_c),
        (x, drop_y, z_c),
        (x, drop_y, exit_end[2]),
    ]
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
