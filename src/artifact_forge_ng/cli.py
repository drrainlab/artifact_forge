"""The forge CLI.

``forge validate product.yaml``
    Everything up to (and excluding) CAD: catalog load, instance
    cross-validation, parameter resolution, capability report, Form IR
    build, form validators. Prints the form_checks block and exits non-zero
    on any critical failure (strict mode) — the golden gate before any CAD.

``forge build product.yaml [-o out/]``
    All of the above, then CAD compilation, geometry validators, honesty
    report and STL/STEP export (Milestones C/D).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from .archetypes import builder_for
from .catalog.loader import CatalogError, load_catalog, load_instance, validate_instance
from .core.findings import Status, ValidationReport
from .form.silhouette import measure
from .form.validators import validate_form
from .product.capability import resolve_capability
from .product.resolve import resolve_params


class PipelineFailure(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def _mm(value: float | None) -> str:
    if value is None:
        return "unmeasured"
    return f"{value:g}mm"


def _direction_label(direction: tuple[float, float] | None) -> str:
    if direction is None:
        return "unmeasured"
    du, dv = direction
    if du > 0.9:
        return "+Y"
    if du < -0.9:
        return "-Y"
    if dv > 0.9:
        return "+Z"
    if dv < -0.9:
        return "-Z"
    return f"({du:.2f}, {dv:.2f})"


def run_validate(product_path: Path, strict_flag: bool | None) -> dict[str, Any]:
    """The pre-CAD pipeline; returns the printed report dict."""
    catalog = load_catalog()
    instance = load_instance(product_path)
    strict = instance.strict if strict_flag is None else strict_flag
    archetype = validate_instance(instance, catalog)

    resolved = resolve_params(archetype, instance)
    report = ValidationReport(findings=list(resolved.findings))

    capability = resolve_capability(
        instance, archetype, catalog.modifiers_for(instance), catalog.features
    )

    builder = builder_for(archetype)
    if builder is None:
        raise PipelineFailure(
            f"engine gap: no form builder for section {archetype.form.section!r}",
            code=2,
        )

    form_checks: dict[str, Any] = {}
    if resolved.ok:
        form = builder(resolved, archetype, instance)
        findings = validate_form(form, [r.id for r in archetype.regions])
        report.extend(findings)
        sil = measure(form.section, form.frame)
        form_checks = {
            "mouth_gap": _mm(sil.mouth_gap),
            "mouth_direction": _direction_label(sil.mouth_direction),
            "lower_lip_len": _mm(sil.lower_lip_len),
            "upper_lip_len": _mm(sil.upper_lip_len),
            "lower_lip_ratio_ok": bool(sil.lip_ratio is not None and sil.lip_ratio > 1.5),
            "symmetric_c_ring": not sil.family_ok,
            "flange_above_cradle": report.passed("form.flange_above_cradle"),
            "regions_present": [r.name for r in form.regions],
        }

    out: dict[str, Any] = {
        "product": instance.id,
        "archetype": archetype.ref,
        "strict": strict,
        "form_checks": form_checks,
        "capability": {
            "requested_features": capability.requested_features,
            "supported_features": capability.supported_features,
            "unsupported_features": capability.unsupported_features,
            "buildable": capability.buildable,
        },
        "findings": [f.to_dict() for f in report.findings if f.status is not Status.PASS],
        "status": report.status.value,
    }

    critical = report.critical_failures()
    if strict:
        if capability.unsupported_features:
            raise PipelineFailure(
                "strict: unsupported requested features: "
                + ", ".join(capability.unsupported_features),
                code=3,
            )
        if critical or not resolved.ok:
            _print(out)
            names = [f.check for f in critical] or [
                f.check for f in report.failures()
            ]
            raise PipelineFailure(
                "strict: critical failures: " + ", ".join(names), code=4
            )
    return out


def _print(doc: dict[str, Any]) -> None:
    yaml.safe_dump(doc, sys.stdout, sort_keys=False, allow_unicode=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="forge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="validate a product YAML without CAD")
    p_validate.add_argument("product", type=Path)
    p_validate.add_argument("--strict", action="store_true", default=None)

    p_build = sub.add_parser("build", help="build a product to STL/STEP")
    p_build.add_argument("product", type=Path)
    p_build.add_argument("-o", "--out", type=Path, default=Path("out"))
    p_build.add_argument("--strict", action="store_true", default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            _print(run_validate(args.product, args.strict))
            return 0
        if args.command == "build":
            from .compiler.pipeline import run_build

            _print(run_build(args.product, args.out, args.strict))
            return 0
    except PipelineFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return exc.code
    except CatalogError as exc:
        print(f"CATALOG ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
