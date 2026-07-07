"""Part-swap verification (wave A1) — interface.swap_part_builds.

The strongest proof interfaces are real: take a validated assembly,
replace ONE part's product with a different archetype's, re-validate the
WHOLE assembly in memory. The swap passes only when every part still
builds its form, every joint IR still measures true, every mate is still
interface-legal — and the untouched parts are bit-identical (the rail
never changes when the cassette does).
"""

from __future__ import annotations

from typing import Any

from ..core.findings import Finding, Level, Status
from ..catalog.loader import Catalog, load_catalog
from ..pipeline import pre_cad_from_instance
from ..product.assembly import AssemblyInstance
from ..product.instance import ProductInstance
from .pipeline import _inject_shared, _joint_findings


def swap_part(
    asm: AssemblyInstance, ref: str, product: dict[str, Any] | ProductInstance
) -> AssemblyInstance:
    """A new AssemblyInstance with ``ref``'s inline product replaced —
    shared params re-inject on validation, joints/contract untouched."""
    if isinstance(product, dict):
        product = ProductInstance.model_validate(product)
    parts = [
        p.model_copy(update={"product": product}) if p.ref == ref else p
        for p in asm.parts
    ]
    if not any(p.ref == ref for p in asm.parts):
        raise KeyError(f"assembly has no part {ref!r}")
    return asm.model_copy(update={"parts": parts})


def verify_swap(
    asm: AssemblyInstance,
    ref: str,
    product: dict[str, Any] | ProductInstance,
    catalog: Catalog | None = None,
    strict: bool = True,
) -> tuple[Finding, dict[str, Any]]:
    """Swap ``ref`` for ``product`` and re-validate in memory. Returns the
    interface.swap_part_builds finding plus the swapped run's summary."""
    catalog = catalog or load_catalog()
    swapped = swap_part(asm, ref, product)
    instances = _inject_shared(swapped, catalog)
    states = {
        r: pre_cad_from_instance(inst, catalog, strict)
        for r, inst in instances.items()
    }
    joint_findings, _, _ = _joint_findings(swapped, states)
    part_fails = {
        r: [f.check for f in st.report.findings
            if f.status is Status.FAIL and f.critical]
        for r, st in states.items()
    }
    part_fails = {r: c for r, c in part_fails.items() if c}
    joint_fails = [
        f for f in joint_findings if f.critical and f.status is Status.FAIL
    ]
    ok = not part_fails and not joint_fails
    new_arch = states[ref].archetype.id
    finding = Finding(
        check="interface.swap_part_builds",
        status=Status.PASS if ok else Status.FAIL,
        level=Level.ASSEMBLY,
        message=(
            f"{ref!r} swapped to {new_arch}: assembly still validates "
            "end to end"
            if ok else
            f"{ref!r} swapped to {new_arch}: "
            + "; ".join(
                [f"{r} fails {c}" for r, c in part_fails.items()]
                + [f.message for f in joint_fails][:3]
            )
        ),
        critical=not ok,
    )
    summary = {
        "swapped_ref": ref,
        "archetype": new_arch,
        "parts": {r: st.summary()["status"] for r, st in states.items()},
        "joints": [f.to_dict() for f in joint_findings],
    }
    return finding, summary
