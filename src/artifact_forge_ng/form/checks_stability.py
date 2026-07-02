"""IR checks for free-standing stands — the device slot really fits the
declared device at the declared tilt, and the combined part+device center
of mass stays inside the base footprint. Self-registers.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm
from .section import LineSeg

#: PETG density, g/mm^3 — nominal; the check carries a mm-scale margin.
PETG_DENSITY = 1.24e-3


def _finding(check: str, ok: bool, message: str, **kw) -> Finding:
    return Finding(
        check=check,
        status=Status.PASS if ok else Status.FAIL,
        level=Level.FORM,
        message=message,
        critical=not ok,
        **kw,
    )


def check_device_slot_fits(form: PartForm) -> Finding:
    """Measured slot (lip inner face to the support-face foot, exact from
    tagged segments) vs the space the tilted device needs."""
    f = form.frame
    thickness = form.params.get("device_thickness")
    sin_t = f.get("tilt_sin")
    if thickness is None or sin_t is None:
        return _finding("form.device_slot_fits", False, "slot unmeasurable")
    lips = [
        s for s in form.section.outer.tagged("lip_inner") if isinstance(s, LineSeg)
    ]
    rests = [
        s for s in form.section.outer.tagged("device_rest") if isinstance(s, LineSeg)
    ]
    if not lips or not rests:
        return _finding("form.device_slot_fits", False, "lip/rest tags missing")
    lip_u = max(s.a.u for s in lips)
    rest_foot_u = min(min(s.a.u, s.b.u) for s in rests)
    measured = rest_foot_u - lip_u
    needed = thickness / sin_t
    ok = measured >= needed - 1e-6
    return _finding(
        "form.device_slot_fits",
        ok,
        f"slot {measured:.2f} vs device needs {needed:.2f} at this tilt",
        measured=measured,
        limit=needed,
        unit="mm",
    )


def check_stability_footprint(form: PartForm) -> Finding:
    """Combined COM (part from the profile centroid + nominal device on the
    rest) must stay inside [margin, base_depth - margin]."""
    f = form.frame
    params = form.params
    needed = ("u_rest", "device_dir_u", "base_depth", "base_t")
    if any(k not in f for k in needed):
        return _finding("form.stability_footprint", False, "frame lacks stand keys")
    device_mass = params.get("device_mass", 220.0)
    com_len = params.get("device_com_len", 70.0)
    margin = params.get("stability_margin", 5.0)

    loop = form.section.outer
    centroid = loop.centroid()
    part_mass = abs(loop.area()) * form.width * PETG_DENSITY

    device_u = f["u_rest"] + f["device_dir_u"] * com_len
    com_u = (part_mass * centroid.u + device_mass * device_u) / (
        part_mass + device_mass
    )
    lo, hi = margin, f["base_depth"] - margin
    ok = lo <= com_u <= hi
    return _finding(
        "form.stability_footprint",
        ok,
        (
            f"combined COM at u={com_u:.1f} (part {part_mass:.0f} g at "
            f"{centroid.u:.1f}, device {device_mass:g} g at {device_u:.1f}) "
            f"vs base [{lo:g}, {hi:g}]"
        ),
        measured=com_u,
        limit=hi,
        unit="mm",
        suggestion="" if ok else "deepen base_depth or reduce tilt/rest_len",
    )


register_probe("form.device_slot_fits")(lambda form, ctx: check_device_slot_fits(form))
register_probe("form.stability_footprint")(
    lambda form, ctx: check_stability_footprint(form)
)
