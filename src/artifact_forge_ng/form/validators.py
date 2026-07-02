"""Form-level validators — every ``form.*`` check, measured analytically on
the PartForm with zero CAD. These run in ``forge validate`` and gate the
golden test; the CAD compiler is not touched until they are green.

Checks self-register in KNOWN_CHECKS (validators/probes.py — stdlib-only,
safe to import here). :func:`validate_form` is archetype-driven: three
universal checks always run; the rest come from the archetype's own
``validators:`` list, so a phone stand is never judged by the cable clip's
mouth checks. A declared form check with no implementation is an honest
ENGINE-GAP warning, mirroring the geometry-level runner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.findings import Finding, Level, Status
from ..validators.probes import KNOWN_CHECKS, register_probe
from .molded import INTENTIONAL_TAGS, joint_is_tangent
from .part import PartForm
from .section import ProfileLoop, Pt, Seg
from . import silhouette


@dataclass(frozen=True)
class FormCheckContext:
    """Extra inputs a form check may need beyond the PartForm itself."""

    declared_region_ids: tuple[str, ...] = ()


def _finding(
    check: str,
    ok: bool,
    message: str,
    *,
    critical: bool = False,
    warn_only: bool = False,
    measured: float | None = None,
    limit: float | None = None,
    suggestion: str = "",
) -> Finding:
    status = Status.PASS if ok else (Status.WARN if warn_only else Status.FAIL)
    return Finding(
        check=check,
        status=status,
        level=Level.FORM,
        message=message,
        critical=critical and not warn_only,
        measured=measured,
        limit=limit,
        suggestion=suggestion,
        unit="mm" if measured is not None else "",
    )


def _chords(seg: Seg, n: int = 8) -> list[tuple[float, float, float, float]]:
    pts = [seg.point_at(i / n) for i in range(n + 1)]
    return [(a.u, a.v, b.u, b.v) for a, b in zip(pts, pts[1:])]


def _segments_intersect(c1: tuple[float, float, float, float],
                        c2: tuple[float, float, float, float]) -> bool:
    ax, ay, bx, by = c1
    cx, cy, dx, dy = c2

    def orient(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> float:
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    d1 = orient(cx, cy, dx, dy, ax, ay)
    d2 = orient(cx, cy, dx, dy, bx, by)
    d3 = orient(ax, ay, bx, by, cx, cy)
    d4 = orient(ax, ay, bx, by, dx, dy)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def check_profile_closed(loop: ProfileLoop) -> Finding:
    """Closure is guaranteed by construction; simplicity (no self-crossing)
    is checked here on chord approximations of non-adjacent segments."""
    n = len(loop.segments)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # adjacent through the wrap-around
            for c1 in _chords(loop.segments[i]):
                for c2 in _chords(loop.segments[j]):
                    if _segments_intersect(c1, c2):
                        return _finding(
                            "form.profile_closed",
                            False,
                            f"profile self-intersects (segments {i} and {j})",
                            critical=True,
                        )
    return _finding(
        "form.profile_closed", True, "one closed simple loop", critical=True
    )


def check_profile_smooth(loop: ProfileLoop) -> Finding:
    sharp = 0
    considered = 0
    for prev, nxt in loop.joints():
        if (prev.tags | nxt.tags) & INTENTIONAL_TAGS:
            continue
        considered += 1
        if not joint_is_tangent(prev, nxt):
            sharp += 1
    if considered == 0:
        return _finding("form.profile_smooth", True, "no joints to check")
    fraction = sharp / considered
    if fraction > 0.3:
        return _finding(
            "form.profile_smooth",
            False,
            f"{sharp}/{considered} joints are sharp — boxy primitive geometry",
            suggestion="use a molded section builder, not box unions",
        )
    if sharp:
        return _finding(
            "form.profile_smooth",
            False,
            f"{sharp}/{considered} joints could not be rounded",
            warn_only=True,
        )
    return _finding("form.profile_smooth", True, "all joints tangent or intentional")


def check_mouth_opens_sideways(form: PartForm) -> Finding:
    direction = silhouette.measure_mouth_direction(form.section)
    if direction is None:
        return _finding(
            "form.mouth_opens_sideways", False, "no measurable mouth", critical=True
        )
    ok = direction[0] > 0.9
    return _finding(
        "form.mouth_opens_sideways",
        ok,
        f"mouth direction ({direction[0]:.2f}, {direction[1]:.2f})"
        + ("" if ok else " — must open toward +Y"),
        critical=True,
    )


def check_mouth_gap_matches(form: PartForm) -> Finding:
    declared = form.params.get("mouth_gap")
    measured = silhouette.measure_mouth_gap(form.section.outer)
    if declared is None or measured is None:
        return _finding(
            "form.mouth_gap_matches", False, "mouth gap unmeasurable", critical=True
        )
    ok = abs(measured - declared) <= 0.05
    return _finding(
        "form.mouth_gap_matches",
        ok,
        f"measured {measured:.3f} vs declared {declared:.3f}",
        critical=True,
        measured=measured,
        limit=declared,
    )


def check_lower_lip_longer(form: PartForm) -> Finding:
    wall_u = form.frame.get("wall_outer_u", 0.0)
    upper = silhouette.measure_lip_length(form.section.outer, "upper_lip", wall_u)
    lower = silhouette.measure_lip_length(form.section.outer, "lower_lip", wall_u)
    if upper is None or lower is None or upper <= 1e-9:
        return _finding(
            "form.lower_lip_longer_than_upper", False, "lips unmeasurable", critical=True
        )
    ratio = lower / upper
    return _finding(
        "form.lower_lip_longer_than_upper",
        ratio > 1.5,
        f"lower/upper = {lower:.2f}/{upper:.2f} = {ratio:.2f} (must exceed 1.5)",
        critical=True,
        measured=ratio,
        limit=1.5,
    )


def check_not_symmetric_c_ring(form: PartForm) -> Finding:
    report = silhouette.measure(form.section, form.frame)
    return _finding(
        "form.not_symmetric_c_ring",
        report.family_ok,
        "asymmetric side-hook family"
        if report.family_ok
        else "; ".join(report.family_problems),
        critical=True,
        suggestion="" if report.family_ok else "use the molded_side_hook section builder",
    )


def check_flange_above_cradle(form: PartForm) -> Finding:
    ok = silhouette.flange_above_cradle(form)
    return _finding(
        "form.flange_above_cradle",
        ok,
        "flange plate above hook body" if ok else "flange is not above the hook",
        critical=True,
    )


def check_wall_thickness(form: PartForm) -> Finding:
    wall = form.params.get("wall")
    loop = form.section.outer
    cavity = loop.tagged("cavity_inner")
    outer = loop.tagged("hook_outer")
    if wall is None or not cavity or not outer:
        return _finding("form.wall_thickness", False, "wall unmeasurable")
    outer_pts = [p for s in outer for p in (s.point_at(t / 12) for t in range(13))]
    min_dist = float("inf")
    for s in cavity:
        for t in range(13):
            p = s.point_at(t / 12)
            min_dist = min(min_dist, min(p.dist(q) for q in outer_pts))
    ok = min_dist >= wall - 0.15
    return _finding(
        "form.wall_thickness",
        ok,
        f"min cavity-to-outer distance {min_dist:.2f} vs wall {wall:.2f}",
        measured=min_dist,
        limit=wall,
    )


def check_regions_present(form: PartForm, declared_region_ids: list[str]) -> Finding:
    have = {r.name for r in form.regions}
    missing = [rid for rid in declared_region_ids if rid not in have]
    return _finding(
        "form.regions_present",
        not missing,
        "all declared regions present" if not missing else f"missing regions: {missing}",
        critical=True,
    )


def check_contact_edges_rounded(form: PartForm) -> Finding:
    """Every joint touching a cable-contact segment must be tangent after
    the molded pass — a sharp corner on the cable path scrapes insulation."""
    loop = form.section.outer
    sharp = 0
    for prev, nxt in loop.joints():
        touches = (prev.tags | nxt.tags) & {"cable_contact", "lip_tip"}
        if touches and not joint_is_tangent(prev, nxt):
            sharp += 1
    return _finding(
        "form.contact_edges_rounded",
        sharp == 0,
        "cable-contact and lip-tip joints all rounded"
        if sharp == 0
        else f"{sharp} sharp joint(s) on the cable path",
    )


def check_screw_access_clear(form: PartForm) -> Finding:
    """A screwdriver approaches each screw from BELOW (-Z). The vertical
    access cylinder around the hole must clear the hook's floor-plan
    footprint — a hole over the hook or a lip cannot be driven at all.
    Born from a real print: v1-style centered holes landed over the lower
    lip."""
    from .regions import Rect2D

    if not form.holes:
        return _finding("form.screw_access_clear", True, "no fastener holes")
    lo, hi = form.section.outer.bbox()
    # Hook floor-plan: full extrusion width in X, profile u-range in Y.
    hook = Rect2D(0.0, lo.u, form.width, hi.u)
    head_r = form.frame.get("screw_head_r", 3.5)
    access_r = head_r + 1.5  # head seat + driver wobble
    blocked = []
    for hole in form.holes:
        x, y, _ = hole.at
        gap = hook.distance(Pt(x, y))
        if gap < access_r:
            blocked.append(f"({x:.1f},{y:.1f}) gap {gap:.1f} < {access_r:.1f}")
    return _finding(
        "form.screw_access_clear",
        not blocked,
        "all screws clear the hook footprint"
        if not blocked
        else "screws unreachable from below: " + "; ".join(blocked),
        critical=True,
        suggestion="" if not blocked else "increase screw_spacing / flange_l",
    )


def check_hex_field_in_safe_zone(form: PartForm) -> Finding:
    if not form.fields:
        return _finding(
            "form.hex_field_in_safe_zone", True, "no perforation field declared"
        )
    problems: list[str] = []
    total = 0
    for f in form.fields:
        total += len(f.centers)
        if f.window is None:
            problems.append("field has no window")
            continue
        r_hex = f.cell / math.sqrt(3.0)
        for cu, cv in f.centers:
            p = Pt(cu, cv)
            if not f.window.contains(p):
                problems.append(f"cell at ({cu:.1f},{cv:.1f}) outside window")
            for k in f.keepouts:
                if k.shape.distance(p) <= r_hex + k.clearance:
                    problems.append(
                        f"cell at ({cu:.1f},{cv:.1f}) violates keepout {k.name}"
                    )
    if problems:
        return _finding(
            "form.hex_field_in_safe_zone", False, "; ".join(problems[:5]), critical=True
        )
    if total == 0:
        return _finding(
            "form.hex_field_in_safe_zone",
            False,
            "perforation requested but zero cells fit",
            warn_only=True,
        )
    return _finding(
        "form.hex_field_in_safe_zone", True, f"{total} cells, all clear of keepouts"
    )


# -- registry wiring ---------------------------------------------------------
# Every form check registers under its KNOWN_CHECKS name with the uniform
# implementation signature (PartForm, FormCheckContext) -> Finding. The
# original functions stay public — tests and other archetype code call them
# directly with their natural arguments.

register_probe("form.profile_closed")(lambda form, ctx: check_profile_closed(form.section.outer))
register_probe("form.profile_smooth")(lambda form, ctx: check_profile_smooth(form.section.outer))
register_probe("form.mouth_opens_sideways")(lambda form, ctx: check_mouth_opens_sideways(form))
register_probe("form.mouth_gap_matches")(lambda form, ctx: check_mouth_gap_matches(form))
register_probe("form.lower_lip_longer_than_upper")(lambda form, ctx: check_lower_lip_longer(form))
register_probe("form.not_symmetric_c_ring")(lambda form, ctx: check_not_symmetric_c_ring(form))
register_probe("form.flange_above_cradle")(lambda form, ctx: check_flange_above_cradle(form))
register_probe("form.wall_thickness")(lambda form, ctx: check_wall_thickness(form))
register_probe("form.regions_present")(
    lambda form, ctx: check_regions_present(form, list(ctx.declared_region_ids))
)
register_probe("form.contact_edges_rounded")(lambda form, ctx: check_contact_edges_rounded(form))
register_probe("form.screw_access_clear")(lambda form, ctx: check_screw_access_clear(form))
register_probe("form.hex_field_in_safe_zone")(lambda form, ctx: check_hex_field_in_safe_zone(form))

#: Structural sanity every archetype gets whether it asks or not — mirrors
#: the always-on manufacturing suite at geometry level.
UNIVERSAL_FORM_CHECKS = (
    "form.profile_closed",
    "form.profile_smooth",
    "form.regions_present",
)


def validate_form(
    form: PartForm, archetype, extra_checks: tuple[str, ...] = ()
) -> list[Finding]:
    """Run the archetype's own form-level checks (plus the universal three,
    plus ``extra_checks`` — the form-level validators the instance's
    modifiers promised).

    ``archetype`` is a loaded ArchetypeSpec (typed loosely to keep this
    module import-light). Unknown names never reach here — the catalog
    loader fail-fast bound them; a declared-but-unimplemented form check
    yields an engine-gap WARN, never a silent skip.
    """
    ctx = FormCheckContext(
        declared_region_ids=tuple(r.id for r in archetype.regions)
    )
    findings: list[Finding] = []
    ran: set[str] = set()
    names = list(UNIVERSAL_FORM_CHECKS) + [
        n
        for n in (*archetype.validators, *extra_checks)
        if n not in UNIVERSAL_FORM_CHECKS
    ]
    for name in names:
        decl = KNOWN_CHECKS.get(name)
        if decl is None or decl.level is not Level.FORM or name in ran:
            continue
        ran.add(name)
        if decl.impl is None:
            findings.append(
                Finding(
                    check=name,
                    status=Status.WARN,
                    level=Level.FORM,
                    message=f"declared check {name!r} has no implementation — engine gap",
                    suggestion=f"implement form check {name!r}",
                )
            )
            continue
        findings.append(decl.impl(form, ctx))
    return findings
