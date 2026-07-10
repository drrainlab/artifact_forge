"""IR checks for the symmetric snap C-clip family — retention here is the
ARC, not asymmetric lips, so the family has its own physics checks:
coverage past half a circle and a mouth measurably narrower than the pipe.
Self-registers on import.
"""

from __future__ import annotations

from ..core.findings import Finding
from ..validators.probes import register_probe
from .part import PartForm
from .section import Pt
from .silhouette import cavity_coverage_deg

#: The molded pass rounds the mouth tips, shaving a few degrees of arc.
ARC_TOL_DEG = 9.0


from .checks_common import make_finding
_finding = make_finding


def check_snap_arc_coverage(form: PartForm) -> Finding:
    declared = form.frame.get("snap_arc_deg")
    if declared is None:
        return _finding("form.snap_arc_coverage", False, "no snap_arc_deg in frame")
    center = Pt(form.frame["cavity_center_u"], form.frame["cavity_center_v"])
    measured = cavity_coverage_deg(form.section.outer, center)
    ok = abs(measured - declared) <= ARC_TOL_DEG and measured > 185.0
    return _finding(
        "form.snap_arc_coverage",
        ok,
        f"cavity wraps {measured:.1f} deg vs declared {declared:.0f} deg",
        measured=measured,
        limit=declared,
    )


def check_snap_mouth_retains(form: PartForm) -> Finding:
    """Measured on the tagged mouth faces of the FINAL (molded) loop: the
    innermost tips must sit closer together than the pipe is wide — that
    distance IS the snap retention."""
    pipe_d = form.params.get("pipe_d")
    if pipe_d is None:
        return _finding("form.snap_mouth_retains", False, "no pipe_d param")
    center = Pt(form.frame["cavity_center_u"], form.frame["cavity_center_v"])
    faces = form.section.outer.tagged("mouth_face")
    if len(faces) < 2:
        return _finding(
            "form.snap_mouth_retains", False,
            f"expected 2 mouth faces, found {len(faces)}",
        )
    tips = []
    for seg in faces:
        tips.append(min((seg.a, seg.b), key=lambda q: q.dist(center)))
    gap = max(t1.dist(t2) for t1 in tips for t2 in tips)
    lo, hi = 0.4 * pipe_d, 0.97 * pipe_d
    ok = lo <= gap <= hi
    return _finding(
        "form.snap_mouth_retains",
        ok,
        f"mouth gap {gap:.2f} vs pipe {pipe_d:g} "
        f"(must stay within {lo:.1f}..{hi:.1f}: narrower retains, "
        "wider-than-pipe never snaps)",
        measured=gap,
        limit=hi,
    )


register_probe("form.snap_arc_coverage")(
    lambda form, ctx: check_snap_arc_coverage(form)
)
register_probe("form.snap_mouth_retains")(
    lambda form, ctx: check_snap_mouth_retains(form)
)
