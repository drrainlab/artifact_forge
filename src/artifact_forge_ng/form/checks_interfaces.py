"""Form-time interface checks (wave A1) — a declared port must be REAL on
the built form: its datum published, its type's frame keys measured, its
keepout regions untouched by any cut. Self-registers on import.

Vacuous PASS when the archetype declares no interfaces — every other
archetype never subscribes these, but a probe must not crash on foreign
geometry.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm
from .regions import Box3


def _finding(check: str, ok: bool, message: str) -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=not ok,
    )


@register_probe("interface.frame_exists")
def check_interface_frame_exists(form: PartForm, ctx=None) -> Finding:
    check = "interface.frame_exists"
    specs = getattr(ctx, "interfaces", ()) if ctx is not None else ()
    if not specs:
        return _finding(check, True, "no interfaces declared")
    problems: list[str] = []
    for spec in specs:
        if spec.datum not in form.datums:
            problems.append(
                f"{spec.id}: datum {spec.datum!r} not published by the builder")
        for key in spec.decl().keys_for(spec.gender):
            if key not in form.frame:
                problems.append(
                    f"{spec.id}: frame key {key!r} missing for a "
                    f"{spec.gender} {spec.type}")
    return _finding(
        check, not problems,
        f"{len(specs)} interface(s) anchored to real datums and frame keys"
        if not problems else "; ".join(problems),
    )


def _boxes_intersect(a: Box3, b: Box3) -> bool:
    return not (
        a.x1 <= b.x0 or b.x1 <= a.x0
        or a.y1 <= b.y0 or b.y1 <= a.y0
        or a.z1 <= b.z0 or b.z1 <= a.z0
    )


@register_probe("interface.keepouts_preserved")
def check_interface_keepouts_preserved(form: PartForm, ctx=None) -> Finding:
    check = "interface.keepouts_preserved"
    specs = getattr(ctx, "interfaces", ()) if ctx is not None else ()
    guarded = [(s, k) for s in specs for k in s.keepouts]
    if not guarded:
        return _finding(check, True, "no interface keepouts declared")
    regions = {r.name: r for r in form.regions}
    problems: list[str] = []
    for spec, keep in guarded:
        region = regions.get(keep)
        if region is None:
            problems.append(
                f"{spec.id}: keepout region {keep!r} not on the form")
            continue
        for cut in form.cutboxes:
            if _boxes_intersect(cut.box, region.box):
                problems.append(
                    f"{spec.id}: cut {cut.name!r} enters keepout {keep!r}")
        for bore in form.bores:
            x, y, z = bore.center
            r = bore.d / 2.0
            lo, hi = bore.span
            bb = (
                Box3(lo, y - r, z - r, hi, y + r, z + r)
                if bore.axis == "X" else
                Box3(x - r, lo, z - r, x + r, hi, z + r)
                if bore.axis == "Y" else
                Box3(x - r, y - r, lo, x + r, y + r, hi)
            )
            if _boxes_intersect(bb, region.box):
                problems.append(
                    f"{spec.id}: bore {bore.name!r} enters keepout {keep!r}")
    return _finding(
        check, not problems,
        f"{len(guarded)} interface keepout(s) intact" if not problems
        else "; ".join(problems[:5]),
    )
