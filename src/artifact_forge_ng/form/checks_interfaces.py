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
    """A REQUIRED port must be real on every build. An OPTIONAL port may
    be parameter-disabled (the lamp bracket with mount_bc=0 builds no
    bolt circle) — datum entirely absent is then a PASS with the
    supported-not-built note, never a silent one. A datum WITHOUT its
    type's frame keys is always a FAIL: half-built ports do not exist."""
    check = "interface.frame_exists"
    specs = getattr(ctx, "interfaces", ()) if ctx is not None else ()
    if not specs:
        return _finding(check, True, "no interfaces declared")
    problems: list[str] = []
    disabled: list[str] = []
    for spec in specs:
        if spec.datum not in form.datums:
            if spec.assembly_role == "required":
                problems.append(
                    f"{spec.id}: datum {spec.datum!r} not published by "
                    "the builder (required port)")
            else:
                disabled.append(spec.id)
            continue
        for key in spec.decl().keys_for(spec.gender):
            if key not in form.frame:
                problems.append(
                    f"{spec.id}: frame key {key!r} missing for a "
                    f"{spec.gender} {spec.type}")
    if problems:
        return _finding(check, False, "; ".join(problems))
    if disabled:
        # the supported-not-built honesty pattern: the port is declared,
        # this instance simply does not build it (parameter-disabled)
        return _finding(
            check, True,
            "optional port(s) not built on this instance (datum absent): "
            + ", ".join(disabled),
        )
    return _finding(
        check, True,
        f"{len(specs)} interface(s) anchored to real datums and frame keys",
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


# -- A1.5: port frame checks -------------------------------------------------

from ..product.interfaces import AXIS_VECTORS  # noqa: E402


def _point_in_loop(loop, u: float, v: float) -> bool:
    """Ray-cast containment on chord approximations of the outer loop."""
    crossings = 0
    for seg in loop.segments:
        pts = [seg.point_at(t / 8.0) for t in range(9)]
        for a, b in zip(pts, pts[1:]):
            if (a.v > v) != (b.v > v):
                x = a.u + (v - a.v) * (b.u - a.u) / (b.v - a.v)
                if x > u:
                    crossings += 1
    return crossings % 2 == 1


def _inside_material(form: PartForm, x: float, y: float, z: float) -> bool | None:
    """Part-frame material test for constant sections: inside the outer
    loop MINUS the material-removing features (cutboxes, bores, U-channel
    cuts). IR-grade fidelity — mesh fields and molded voids under a port
    are the CAD probes' business. None = unsupported form kind."""
    if getattr(form, "kind", None) != "section_extrude":
        return None
    plane = form.section.plane
    if plane == "YZ":
        along, u, v = x, y, z
    elif plane == "XY":
        along, u, v = z, x, y
    else:
        return None
    if not -1e-6 <= along <= form.width + 1e-6:
        return False
    if not _point_in_loop(form.section.outer, u, v):
        return False
    for cut in form.cutboxes:
        if cut.box.contains(x, y, z):
            return False
    for bore in form.bores:
        lo, hi = sorted(bore.span)
        bx, by, bz = bore.center
        if bore.axis == "Z" and lo <= z <= hi and \
                (x - bx) ** 2 + (y - by) ** 2 <= (bore.d / 2.0) ** 2:
            return False
        if bore.axis == "X" and lo <= x <= hi and \
                (y - by) ** 2 + (z - bz) ** 2 <= (bore.d / 2.0) ** 2:
            return False
        if bore.axis == "Y" and lo <= y <= hi and \
                (x - bx) ** 2 + (z - bz) ** 2 <= (bore.d / 2.0) ** 2:
            return False
    for ch in getattr(form, "channels", ()):
        half_w = ch.width / 2.0
        if abs(x - ch.center_x) <= half_w and \
                min(ch.y0, ch.y1) - 1.0 <= y <= max(ch.y0, ch.y1) + 1.0 and \
                ch.z_top - ch.depth_at(y) <= z <= ch.z_top + 1e-6:
            return False
    return True


@register_probe("interface.frame_orthonormal")
def check_interface_frame_orthonormal(form: PartForm, ctx=None) -> Finding:
    check = "interface.frame_orthonormal"
    specs = getattr(ctx, "interfaces", ()) if ctx is not None else ()
    if not specs:
        return _finding(check, True, "no interfaces declared")
    frameless = [s.id for s in specs if s.frame is None]
    triads = []
    for s in specs:
        if s.frame is None:
            continue
        n, u = s.frame.vectors()
        if sum(a * b for a, b in zip(n, u)) != 0:
            return _finding(check, False,
                            f"{s.id}: normal/up not orthogonal")
        triads.append(f"{s.id}({s.frame.normal},{s.frame.up})")
    if frameless:
        return Finding(
            check=check, status=Status.WARN, level=Level.FORM,
            message=("frameless ports (declare frame: normal/up): "
                     + ", ".join(frameless)),
        )
    return _finding(check, True,
                    "orthonormal frames: " + "; ".join(triads))


#: A male protrusion along its own normal must END within this depth —
#: beyond it the connection direction has to be clear air.
MALE_PROTRUSION_BUDGET = 20.0


def _material_at(form: PartForm, origin, n, d: float) -> bool | None:
    """Cross-sampled material test at origin + n*d: five parallel rays
    (center + 2 mm offsets in the port plane) so a mesh hole or a groove
    void under the exact datum never fakes 'floating in air'."""
    ox, oy, oz = origin
    px, py, pz = ox + n[0] * d, oy + n[1] * d, oz + n[2] * d
    axes = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    offsets = [a for a in axes
               if abs(sum(x * y for x, y in zip(a, n))) == 0]
    probes = [(px, py, pz)]
    for a in offsets:
        probes.append((px + 2 * a[0], py + 2 * a[1], pz + 2 * a[2]))
        probes.append((px - 2 * a[0], py - 2 * a[1], pz - 2 * a[2]))
    hit = False
    for p in probes:
        r = _inside_material(form, *p)
        if r is None:
            return None
        hit = hit or r
    return hit


@register_probe("interface.normal_points_outward")
def check_interface_normal_points_outward(form: PartForm, ctx=None) -> Finding:
    """female/neutral: the approach along +normal is clear air the whole
    way. male: the port's own protrusion MAY ride the normal but must end
    inside the protrusion budget. Both: material exists behind the port."""
    check = "interface.normal_points_outward"
    specs = [s for s in (getattr(ctx, "interfaces", ()) if ctx else ())
             if s.frame is not None]
    if not specs:
        return _finding(check, True, "no framed ports to measure")
    problems: list[str] = []
    warnings: list[str] = []
    for s in specs:
        datum = form.datums.get(s.datum)
        if datum is None:
            continue  # frame_exists reports the missing datum
        origin = tuple(datum["at"])
        n = AXIS_VECTORS[s.frame.normal]
        neg = tuple(-a for a in n)
        unsupported = False
        far_hit = near_hit = hit_in = False
        for step in range(1, 61):  # 0.5..30 mm
            d = 0.5 * step
            r = _material_at(form, origin, n, d)
            if r is None:
                unsupported = True
                break
            if r and d > MALE_PROTRUSION_BUDGET:
                far_hit = True
            if r and d <= MALE_PROTRUSION_BUDGET:
                near_hit = True
            if _material_at(form, origin, neg, d):
                hit_in = True
        if unsupported:
            # out of the measurable family (revolve/sweep) — the vacuous
            # gate discipline, stated in the message
            return _finding(
                check, True,
                "form kind not ray-markable (non-extrude) — outward "
                "normals apply to constant sections only",
            )
        if s.gender == "male":
            if far_hit:
                problems.append(
                    f"{s.id}: material along +{s.frame.normal} beyond the "
                    f"{MALE_PROTRUSION_BUDGET:g} mm protrusion budget")
        elif near_hit or far_hit:
            problems.append(
                f"{s.id}: material found along +{s.frame.normal} — the "
                "normal points INTO the part")
        # flow-through ports (fluid, cable) legitimately face void BOTH
        # ways — the connection continues into a channel by design.
        flow_through = s.type in ("fluid_inlet", "fluid_outlet", "cable_pass")
        if not hit_in and not flow_through:
            warnings.append(
                f"{s.id}: no material within the 2 mm cross behind the "
                f"port along -{s.frame.normal} — floating port, or a "
                "ring/void-centered datum (verify)")
    if problems:
        return _finding(check, False, "; ".join(problems))
    if warnings:
        return Finding(check=check, status=Status.WARN, level=Level.FORM,
                       message="; ".join(warnings))
    return _finding(
        check, True,
        f"{len(specs)} port normal(s) leave the part with material behind",
    )


#: Per-type axis semantics — the consumer that makes ``up_consistent``
#: measured, not decorative.
_AXIS_RULES = {
    "dovetail_rail": "in_plane",       # slide axis rides the port plane
    "cylindrical_payload_socket": "in_plane",
    "fluid_inlet": "on_normal",        # flow rides the normal
    "fluid_outlet": "on_normal",
    "tongue_groove": "in_plane",
}


@register_probe("interface.up_consistent")
def check_interface_up_consistent(form: PartForm, ctx=None) -> Finding:
    check = "interface.up_consistent"
    specs = [s for s in (getattr(ctx, "interfaces", ()) if ctx else ())
             if s.frame is not None]
    if not specs:
        return _finding(check, True, "no framed ports to judge")
    problems: list[str] = []
    for s in specs:
        n, u = s.frame.vectors()
        if sum(a * b for a, b in zip(n, u)) != 0:
            problems.append(f"{s.id}: up not orthogonal to normal")
        rule = _AXIS_RULES.get(s.type)
        ax = s.frame.axis
        if rule and ax is None:
            problems.append(
                f"{s.id}: type {s.type} needs an axis in its frame")
        elif rule and ax is not None:
            av = AXIS_VECTORS[ax]
            dot_n = sum(a * b for a, b in zip(av, n))
            if rule == "in_plane" and dot_n != 0:
                problems.append(
                    f"{s.id}: slide axis {ax} must lie in the port plane, "
                    f"not on the normal {s.frame.normal}")
            if rule == "on_normal" and abs(dot_n) != 1:
                problems.append(
                    f"{s.id}: flow axis {ax} must ride the normal "
                    f"{s.frame.normal}")
    return _finding(
        check, not problems,
        f"{len(specs)} port frame(s) consistent with their type semantics"
        if not problems else "; ".join(problems),
    )
