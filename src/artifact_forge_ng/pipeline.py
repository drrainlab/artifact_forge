"""The pre-CAD pipeline — everything from product YAML to a validated Form
IR, shared by ``forge validate`` and ``forge build``. Importing this module
never loads cadquery.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .archetypes import builder_for
from .catalog.loader import Catalog, load_catalog, load_instance, validate_instance
from .core.findings import Status, ValidationReport
from .form.part import PartForm
from .form.silhouette import measure
from .form.validators import validate_form
from .product.archetype import ArchetypeSpec
from .product.capability import CapabilityReport, resolve_capability
from .product.instance import ProductInstance
from .product.resolve import ResolvedParams, resolve_params


class PipelineFailure(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class PipelineState:
    catalog: Catalog
    instance: ProductInstance
    archetype: ArchetypeSpec
    strict: bool
    resolved: ResolvedParams
    capability: CapabilityReport
    form: PartForm | None
    report: ValidationReport

    def form_checks(self) -> dict[str, Any]:
        """Family-aware summary: the side-hook block only makes sense for
        the side-hook family; other sections get a generic frame digest."""
        if self.form is None:
            return {}
        if self.form.section.name == "molded_side_hook":
            sil = measure(self.form.section, self.form.frame)
            return {
                "mouth_gap": _mm(sil.mouth_gap),
                "mouth_direction": _direction_label(sil.mouth_direction),
                "lower_lip_len": _mm(sil.lower_lip_len),
                "upper_lip_len": _mm(sil.upper_lip_len),
                "lower_lip_ratio_ok": bool(
                    sil.lip_ratio is not None and sil.lip_ratio > 1.5
                ),
                "symmetric_c_ring": not sil.family_ok,
                "flange_above_cradle": self.report.passed("form.flange_above_cradle"),
                "regions_present": [r.name for r in self.form.regions],
            }
        lo, hi = self.form.section.outer.bbox()
        checks: dict[str, Any] = {
            "section": self.form.section.name,
            "profile_ok": self.report.passed("form.profile_closed"),
            "profile_bbox": f"{hi.u - lo.u:.1f} x {hi.v - lo.v:.1f} mm",
            "width": _mm(self.form.width),
            "regions_present": [r.name for r in self.form.regions],
        }
        # Surface the builder's own key numbers (frame entries are the
        # per-family measurement vocabulary).
        for key in sorted(self.form.frame):
            if key.startswith("report_"):
                checks[key.removeprefix("report_")] = _mm(self.form.frame[key])
        return checks

    def summary(self) -> dict[str, Any]:
        return {
            "product": self.instance.id,
            "archetype": self.archetype.ref,
            "strict": self.strict,
            "form_checks": self.form_checks(),
            "capability": {
                "requested_features": self.capability.requested_features,
                "supported_features": self.capability.supported_features,
                "unsupported_features": self.capability.unsupported_features,
                "buildable": self.capability.buildable,
            },
            "findings": [
                f.to_dict() for f in self.report.findings if f.status is not Status.PASS
            ],
            "status": self.report.status.value,
        }

    def enforce_strict(self) -> None:
        if not self.strict:
            return
        if self.capability.unsupported_features:
            raise PipelineFailure(
                "strict: unsupported requested features: "
                + ", ".join(self.capability.unsupported_features),
                code=3,
            )
        critical = self.report.critical_failures()
        if critical or not self.resolved.ok:
            names = [f.check for f in critical] or [
                f.check for f in self.report.failures()
            ]
            raise PipelineFailure(
                "strict: critical failures: " + ", ".join(names), code=4
            )


def _mm(value: float | None) -> str:
    return "unmeasured" if value is None else f"{value:g}mm"


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


def run_pre_cad(product_path: Path, strict_flag: bool | None) -> PipelineState:
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

    form: PartForm | None = None
    if resolved.ok:
        form = builder(resolved, archetype, instance)
        # The modifier kernel: typed, region-bound transformations applied
        # AFTER the archetype owns the product's function; their validators
        # run with the form checks right below.
        from .modifiers import apply_modifiers

        modifier_defs = catalog.modifiers_for(instance)
        report.extend(
            apply_modifiers(form, instance.modifiers, modifier_defs, archetype)
        )
        modifier_checks = tuple(
            name for mod in modifier_defs.values() for name in mod.validators
        )
        report.extend(validate_form(form, archetype, modifier_checks))

    return PipelineState(
        catalog=catalog,
        instance=instance,
        archetype=archetype,
        strict=strict,
        resolved=resolved,
        capability=capability,
        form=form,
        report=report,
    )
