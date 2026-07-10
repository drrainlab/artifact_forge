"""VF-4.1 end-receiver checks — the collector as the final lap
receiver.
"""
from __future__ import annotations

from artifact_forge_ng.core.findings import Finding
from artifact_forge_ng.validators.probes import register_probe
from artifact_forge_ng.form.part import PartForm
from artifact_forge_ng.form.regions import Box3
from artifact_forge_ng.form.checks_common import make_finding
from .common import (
    _boxes_overlap)

_finding = make_finding


# -- VF-4.1: the collector is an END RECEIVER, not a part standing nearby ----

RECEIVER_CAPTURE_BAND = (6.0, 8.0)
RECEIVER_SIDE_MARGIN = 1.4  # mouth over lip, per side
RECEIVER_APRON_BAND = (2.4, 3.5)  # a low curb over the handover plane
RECEIVER_TIP_MARGIN = 2.0  # lip tip to the apron wall
RECEIVER_LIFT_WINDOW = 15.0  # clear vertical exit over the captured lip


def _receiver_keys(form: PartForm):
    keys = ("receiver_mouth_w", "receiver_capture_depth", "receiver_apron_z",
            "receiver_cheek_x0", "receiver_lip_overhang", "receiver_lip_w",
            "handover_dz")
    missing = [k for k in keys if k not in form.frame]
    return missing


def check_collector_receiver_matches_final_lap(form: PartForm) -> Finding:
    """The mouth is built FOR the final lap lip: wide enough to envelope
    it, deep enough to capture the tip with margin to the apron, the apron
    high enough that runoff drops cannot escape."""
    check = "form.collector_receiver_matches_final_lap"
    missing = _receiver_keys(form)
    if missing:
        return _finding(check, False, f"no receiver frame keys: {', '.join(missing)}")
    f = form.frame
    problems: list[str] = []
    if f["receiver_mouth_w"] < f["receiver_lip_w"] + 2.0 * RECEIVER_SIDE_MARGIN:
        problems.append(
            f"mouth {f['receiver_mouth_w']:g} does not envelope the "
            f"{f['receiver_lip_w']:g} lip with {RECEIVER_SIDE_MARGIN:g}/side")
    cd = f["receiver_capture_depth"]
    if not (RECEIVER_CAPTURE_BAND[0] - 1e-9 <= cd <= RECEIVER_CAPTURE_BAND[1] + 1e-9):
        problems.append(
            f"capture depth {cd:g} outside "
            f"{RECEIVER_CAPTURE_BAND[0]}..{RECEIVER_CAPTURE_BAND[1]}")
    if cd - f["receiver_lip_overhang"] < RECEIVER_TIP_MARGIN - 1e-9:
        problems.append(
            f"lip tip lands {cd - f['receiver_lip_overhang']:g} from the apron "
            f"(needs >= {RECEIVER_TIP_MARGIN:g})")
    if f["receiver_apron_z"] < RECEIVER_APRON_BAND[0] - 1e-9:
        problems.append(
            f"apron top {f['receiver_apron_z']:g} above the handover plane is "
            f"below {RECEIVER_APRON_BAND[0]:g} — runoff drops can escape the mouth")
    cheeks = [r for r in form.ribs if "cheek" in r.name]
    if len(cheeks) != 2:
        problems.append(f"{len(cheeks)} cheek rib(s) — the wet zone needs both flanks")
    elif abs(abs(cheeks[0].box.x0 + cheeks[0].box.x1)
             - abs(cheeks[1].box.x0 + cheeks[1].box.x1)) > 0.2:
        problems.append("cheeks are not symmetric about the lip centerline")
    return _finding(
        check, not problems,
        f"end receiver: mouth {f['receiver_mouth_w']:g} over the "
        f"{f['receiver_lip_w']:g} lip, capture {cd:g} with "
        f"{cd - f['receiver_lip_overhang']:g} tip margin, apron at "
        f"{f['receiver_apron_z']:g}"
        if not problems else "; ".join(problems),
        measured=cd, limit=RECEIVER_CAPTURE_BAND[1],
    )


def check_receiver_open_top_cleanable(form: PartForm) -> Finding:
    """Capture is worthless if it breeds biofilm: the capture zone is open
    to the sky (a brush and an eye enter from above), the apron is a low
    curb — never a wall walling off a blind slot — and the zone flows
    straight into the open tray (a falling drop's path IS the brush path)."""
    check = "form.receiver_open_top_cleanable"
    missing = _receiver_keys(form)
    if missing:
        return _finding(check, False, f"no receiver frame keys: {', '.join(missing)}")
    f = form.frame
    dz = f["handover_dz"]
    cheek_x0 = f["receiver_cheek_x0"]
    cd = f["receiver_capture_depth"]
    problems: list[str] = []
    # (a) open top: within the lift window no collector material hangs
    # over the capture footprint between the cheeks
    footprint = Box3(-cheek_x0 + 0.05, -cd, dz + 1.6,
                     cheek_x0 - 0.05, -0.05, dz + RECEIVER_LIFT_WINDOW)
    for feat in list(form.ribs) + list(form.plates):
        fb = getattr(feat, "box", None)
        if fb is None:
            b = feat  # PlateFeature has explicit coords
            fb = Box3(b.x0, b.y0, b.z_bottom, b.x1, b.y1, b.z_bottom + b.thickness)
        if _boxes_overlap(fb, footprint):
            problems.append(
                f"{feat.name!r} roofs the capture zone — no ceiling over the "
                "mouth, ever")
    # (b) the apron is a curb, not a wall
    if f["receiver_apron_z"] > RECEIVER_APRON_BAND[1] + 1e-9:
        problems.append(
            f"apron {f['receiver_apron_z']:g} over the handover plane rises "
            f"past {RECEIVER_APRON_BAND[1]:g} — a deep narrow slot collects "
            "coco and biofilm a brush cannot reach")
    # (c) continuity: nothing blocks the tray void between the capture
    # zone and the drain end below the rim
    if form.channels:
        tray = form.channels[0]
        void = Box3(-tray.width / 2.0 + 0.05, tray.y1 + 0.1, dz - 2.0,
                    tray.width / 2.0 - 0.05, tray.y0 - 0.1,
                    f["receiver_apron_z"] + dz - 0.1)
        for feat in form.ribs:
            if _boxes_overlap(feat.box, void):
                problems.append(
                    f"{feat.name!r} walls the receiver off from the open tray")
    side = (f["receiver_mouth_w"] - f["receiver_lip_w"]) / 2.0
    return _finding(
        check, not problems,
        f"open-top receiver: {side:.1f}/side around the lip, curb apron "
        f"{f['receiver_apron_z']:g}, capture zone continuous with the "
        f"{form.channels[0].width if form.channels else 0:g}-wide open tray "
        "(brush >= d8 enters wherever a drop falls)"
        if not problems else "; ".join(problems),
        measured=side,
    )


def check_collector_drain_bore_supportless(form: PartForm) -> Finding:
    """The drain prints without support: vertical, or teardrop-roofed on a
    horizontal run."""
    check = "form.collector_drain_bore_supportless"
    drains = [b for b in form.bores if "drain" in b.name]
    if not drains:
        return _finding(check, False, "no drain bore on the collector")
    problems = [
        f"drain {b.name!r} d{b.d:g} is a horizontal circle — it sags on FDM"
        for b in drains
        if b.axis in ("X", "Y") and b.roof != "teardrop"
    ]
    return _finding(
        check, not problems,
        "drain prints supportless (vertical or teardrop-roofed)"
        if not problems else "; ".join(problems),
        suggestion="" if not problems else 'BoreFeature(roof="teardrop")',
    )


register_probe("form.collector_receiver_matches_final_lap")(


lambda form, ctx: check_collector_receiver_matches_final_lap(form))
register_probe("form.receiver_open_top_cleanable")(
    lambda form, ctx: check_receiver_open_top_cleanable(form))
register_probe("form.collector_drain_bore_supportless")(
    lambda form, ctx: check_collector_drain_bore_supportless(form))
