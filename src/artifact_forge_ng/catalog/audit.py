"""Datum-declaration honesty audit (wave G3).

An archetype DECLARES the datums its form publishes (``ArchetypeSpec.datums``)
so the assembly digest can teach the LLM the anchor vocabulary. Declarations
are metadata; the truth is the built Form IR. This audit builds every
declared archetype pre-CAD (fast, no cadquery) on its defaults — plus each
``audit_params`` variant for conditional datums — and reports every
disagreement:

* an unconditional declared datum that was not built            -> problem
* a glob declaration that matched nothing                       -> problem
* a built datum not covered by any declaration                  -> problem
  (undeclared publication is dishonesty too)
* ``conditional: true`` without audit_params                    -> warning
  (the flag must not become a way to switch the audit off)
* required parameters without defaults                          -> reported
  honestly as "unauditable at defaults", never silently skipped

CLI: ``forge catalog audit`` (exit code 4 on problems).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any

from ..pipeline import pre_cad_from_instance
from ..product.archetype import ArchetypeSpec
from ..product.instance import ProductInstance
from .loader import Catalog


@dataclass
class DatumAudit:
    archetype: str
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _built_datums(
    spec: ArchetypeSpec, catalog: Catalog, params: dict[str, Any]
) -> set[str] | str:
    """Datum names the form publishes for the given params, or an error
    string when the form cannot be built at all."""
    inst = ProductInstance.model_validate({
        "schema": "product/v1",
        "id": f"audit_{spec.id}",
        "archetype": spec.ref,
        "params": {k: str(v) for k, v in params.items()},
        "strict": False,
    })
    try:
        state = pre_cad_from_instance(inst, catalog, strict=False)
    except Exception as exc:  # noqa: BLE001 — reported, never swallowed
        return f"form failed to build: {exc}"
    if state.form is None:
        return "pre-CAD produced no form"
    return set(state.form.datums)


def _covered(name: str, spec: ArchetypeSpec) -> bool:
    return any(fnmatch(name, d.id) for d in spec.datums)


def audit_archetype_datums(spec: ArchetypeSpec, catalog: Catalog) -> DatumAudit:
    audit = DatumAudit(archetype=spec.id)
    required = [n for n, p in spec.parameters.items() if p.default is None]
    if required:
        audit.warnings.append(
            f"unauditable at defaults: required params without defaults "
            f"{sorted(required)}"
        )
        return audit

    built = _built_datums(spec, catalog, {})
    if isinstance(built, str):
        audit.problems.append(f"defaults: {built}")
        return audit

    for datum in spec.datums:
        matched = {n for n in built if fnmatch(n, datum.id)}
        if matched:
            continue
        if not datum.conditional:
            audit.problems.append(
                f"declared datum {datum.id!r} not built on defaults "
                f"(built: {sorted(built)})"
            )
        elif not datum.audit_params:
            audit.warnings.append(
                f"conditional datum {datum.id!r} has no audit_params — "
                "declared but never verified"
            )
    for name in sorted(built):
        if not _covered(name, spec):
            audit.problems.append(
                f"built datum {name!r} is not covered by any declaration "
                "— undeclared publication"
            )

    # Representative variants: each audit_params entry must produce the datum.
    for datum in spec.datums:
        for i, variant in enumerate(datum.audit_params):
            v_built = _built_datums(spec, catalog, variant)
            if isinstance(v_built, str):
                audit.problems.append(
                    f"datum {datum.id!r} audit_params[{i}]: {v_built}")
                continue
            if not any(fnmatch(n, datum.id) for n in v_built):
                audit.problems.append(
                    f"datum {datum.id!r} not built under audit_params[{i}] "
                    f"{variant} (built: {sorted(v_built)})"
                )
    return audit


def audit_catalog_datums(
    catalog: Catalog, *, only_declared: bool = True
) -> list[DatumAudit]:
    """Audit every archetype that declares datums. ``only_declared=False``
    additionally reports archetypes that PUBLISH datums while declaring
    none (the G3-full worklist)."""
    audits: list[DatumAudit] = []
    for spec in catalog.archetypes.values():
        if spec.datums:
            audits.append(audit_archetype_datums(spec, catalog))
        elif not only_declared:
            built = _built_datums(spec, catalog, {})
            if isinstance(built, set) and built:
                a = DatumAudit(archetype=spec.id)
                a.warnings.append(
                    f"publishes datums {sorted(built)} but declares none")
                audits.append(a)
    return audits
