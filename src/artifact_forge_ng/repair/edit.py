"""Semantic editing — edit = REBUILD FROM SEMANTIC SOURCE, never mesh
surgery. The pipeline: build the current product (real before-metrics),
apply a typed patch (from an intent or a patch file), write the edited
YAML as a self-contained artifact, rebuild, then VERIFY the patch's
``preserve`` list against both builds — preserved parameters must come out
numerically identical and preserved features must still be validator-built.
A violated preserve fails the edit; "functionally the same" is a checked
contract, not a promise.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..catalog.loader import Catalog, load_catalog, load_instance, validate_instance
from ..pipeline import PipelineFailure
from ..product.instance import ProductInstance
from .intents import INTENTS, IntentNotApplicable
from .patch import Patch, apply_patch


@dataclass
class BuildSnapshot:
    params: dict[str, float]
    choices: dict[str, str]
    built_features: list[str]
    manufacturing: dict[str, Any]
    style: dict[str, Any]
    findings: list[dict[str, Any]]
    status: str
    grade: str

    @classmethod
    def from_build(cls, out: dict[str, Any], resolved_ctx: dict[str, float],
                   choices: dict[str, str], instance: ProductInstance) -> "BuildSnapshot":
        return cls(
            params=dict(resolved_ctx),
            choices=dict(choices),
            built_features=list(out["honesty_report"]["built_features"]),
            manufacturing=instance.manufacturing.model_dump(),
            style=dict(instance.style),
            findings=list(out.get("findings", [])),
            status=out["score"]["status"],
            grade=out["score"]["grade"],
        )


def _build(product_path: Path, out_dir: Path) -> tuple[dict[str, Any], BuildSnapshot]:
    from ..compiler.pipeline import run_build
    from ..product.resolve import resolve_params

    catalog = load_catalog()
    instance = load_instance(product_path)
    archetype = validate_instance(instance, catalog)
    resolved = resolve_params(archetype, instance)
    out = run_build(product_path, out_dir, None)
    snapshot = BuildSnapshot.from_build(out, resolved.context, resolved.choices, instance)
    # run_build's summary filters PASS findings; the full list (incl. the
    # passing overhang verdict the report wants to show) is on disk.
    findings_file = out_dir / instance.id / "findings.yaml"
    if findings_file.exists():
        snapshot.findings = yaml.safe_load(findings_file.read_text())["findings"]
    return out, snapshot


def _finding_for(findings: list[dict[str, Any]], check: str) -> dict[str, Any] | None:
    for f in findings:
        if f.get("check") == check:
            return f
    return None


def verify_preserve(
    patch: Patch, before: BuildSnapshot, after: BuildSnapshot
) -> tuple[list[dict[str, Any]], list[str]]:
    """Returns (verified entries, violation messages)."""
    verified: list[dict[str, Any]] = []
    violations: list[str] = []
    for name in patch.preserve:
        if name in before.params or name in after.params:
            b, a = before.params.get(name), after.params.get(name)
            if b is None or a is None or abs(b - a) > 1e-6:
                violations.append(f"parameter {name!r} changed: {b} -> {a}")
            else:
                verified.append({"name": name, "kind": "param", "value": round(a, 6)})
        elif name in before.choices or name in after.choices:
            b_c, a_c = before.choices.get(name), after.choices.get(name)
            if b_c != a_c:
                violations.append(f"choice {name!r} changed: {b_c} -> {a_c}")
            else:
                verified.append({"name": name, "kind": "choice", "value": a_c})
        else:
            if name not in after.built_features:
                violations.append(
                    f"feature {name!r} is no longer validator-built after the edit"
                )
            else:
                verified.append({"name": name, "kind": "feature", "built": True})
    return verified, violations


def _changed(before: BuildSnapshot, after: BuildSnapshot) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    params = {
        k: f"{before.params[k]:g} -> {after.params[k]:g}"
        for k in sorted(set(before.params) & set(after.params))
        if abs(before.params[k] - after.params[k]) > 1e-6
        and not k.startswith(("printer_", "nozzle", "layer_"))
    }
    choices = {
        k: f"{before.choices.get(k, '(absent)')} -> {after.choices.get(k, '(absent)')}"
        for k in sorted(set(before.choices) | set(after.choices))
        if before.choices.get(k) != after.choices.get(k)
    }
    manufacturing = {
        k: f"{before.manufacturing.get(k)} -> {after.manufacturing.get(k)}"
        for k in sorted(set(before.manufacturing) | set(after.manufacturing))
        if before.manufacturing.get(k) != after.manufacturing.get(k)
    }
    style = {
        k: f"{before.style.get(k)} -> {after.style.get(k)}"
        for k in sorted(set(before.style) | set(after.style))
        if before.style.get(k) != after.style.get(k)
    }
    if params:
        changed["params"] = params
    if choices:
        changed["choices"] = choices
    if manufacturing:
        changed["manufacturing"] = manufacturing
    if style:
        changed["style"] = style
    gained = sorted(set(after.built_features) - set(before.built_features))
    lost = sorted(set(before.built_features) - set(after.built_features))
    if gained:
        changed["features_gained"] = gained
    if lost:
        changed["features_lost"] = lost
    return changed


def run_edit(
    product_path: Path,
    out_dir: Path,
    intent_name: str | None = None,
    patch_path: Path | None = None,
) -> dict[str, Any]:
    catalog: Catalog = load_catalog()
    instance = load_instance(product_path)
    archetype = validate_instance(instance, catalog)

    if intent_name is not None:
        spec = INTENTS.get(intent_name)
        if spec is None:
            raise PipelineFailure(
                f"unknown intent {intent_name!r}; known: {sorted(INTENTS)}", code=2
            )
        try:
            patch = spec.build_patch(instance, archetype)
        except IntentNotApplicable as exc:
            raise PipelineFailure(f"intent not applicable: {exc}", code=2) from exc
        label = intent_name
    elif patch_path is not None:
        patch = Patch.model_validate(yaml.safe_load(patch_path.read_text()))
        label = patch_path.stem
    else:
        raise PipelineFailure("forge edit needs --intent or --patch", code=2)

    # 1. the BEFORE build — real metrics, not guesses
    before_out, before = _build(product_path, out_dir)

    # 2. apply the patch, write the edited YAML as a standalone artifact
    edited = apply_patch(instance, patch, archetype, catalog)
    edited_id = f"{instance.id}__{label}"
    edited_data = edited.model_dump(by_alias=True, mode="json", exclude_defaults=False)
    edited_data["id"] = edited_id
    edited_yaml_path = out_dir / f"{edited_id}.yaml"
    out_dir.mkdir(parents=True, exist_ok=True)
    edited_yaml_path.write_text(
        yaml.safe_dump(edited_data, sort_keys=False, allow_unicode=True)
    )

    # 3. rebuild from the edited semantic source
    after_out, after = _build(edited_yaml_path, out_dir)

    # 4. the preserve contract — verified, not promised
    verified, violations = verify_preserve(patch, before, after)

    overhang_b = _finding_for(before.findings, "manufacturing.overhang")
    overhang_a = _finding_for(after.findings, "manufacturing.overhang")

    def _overhang_view(f: dict[str, Any] | None) -> dict[str, Any]:
        if f is None:
            return {"status": "pass", "message": "no overhang finding"}
        return {"status": f["status"], "message": f["message"]}

    report: dict[str, Any] = {
        "edit_report": {
            "intent": label,
            "patch_type": patch.type,
            "reason": patch.reason,
            "preserved": verified,
            "preserve_violations": violations,
            "changed": {
                **(
                    {"archetype": f"{archetype.id} -> {patch.archetype}"}
                    if patch.archetype
                    else {}
                ),
                **_changed(before, after),
            },
            "printability": {
                "overhang_before": _overhang_view(overhang_b),
                "overhang_after": _overhang_view(overhang_a),
                "supports_recommended_before": (
                    overhang_b is not None and overhang_b["status"] != "pass"
                ),
                "supports_recommended_after": (
                    overhang_a is not None and overhang_a["status"] != "pass"
                ),
            },
            "grades": {"before": before.grade, "after": after.grade},
            "status": "fail" if violations or after.status != "pass" else "pass",
            "edited_yaml": str(edited_yaml_path),
            "stl": after_out["exports"]["stl"],
        }
    }

    (out_dir / edited_id / "edit_report.yaml").write_text(
        yaml.safe_dump(report, sort_keys=False, allow_unicode=True)
    )

    if violations:
        raise PipelineFailure(
            "edit violated its preserve contract: " + "; ".join(violations), code=5
        )
    if after.status != "pass":
        raise PipelineFailure("edited product failed validation", code=4)
    return report
