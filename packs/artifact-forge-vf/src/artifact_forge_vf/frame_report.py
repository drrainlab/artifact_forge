"""The frame/carrier report (VF correction) — the mechanical-support story
of a tilted flush row, symmetric to the water report: standard straight
profiles carry flush modules FULL LENGTH (span gap zero), and the physical
slope comes from the MOUNT (mount_context), never from any part. Derived
from frame keys, poses and the carrier findings — never re-measured here.
"""

from __future__ import annotations

from typing import Any

from .carrier import _profile_refs, _rail_refs


def build_frame_report(
    asm: Any,
    states: dict[str, Any],
    joint_findings: list[Any],
) -> dict[str, Any] | None:
    perch_joints = [j for j in asm.joints if j.type == "profile_perch"]
    if not perch_joints:
        return None
    profiles = _profile_refs(asm, states)
    rails = _rail_refs(asm, states)
    mount = getattr(asm, "mount_context", None)

    def verdict(check: str) -> str:
        hits = [j for j in joint_findings if j.check == check]
        if not hits:
            return "unchecked"
        return "pass" if all(h.status.value == "pass" for h in hits) else "FAIL"

    profile_entries = []
    for prof in profiles:
        f = states[prof].form.frame
        profile_entries.append({
            "ref": prof,
            "size": f"{int(f['profile_size'])}{int(f['profile_size'])}",
            "slope_deg": round(f.get("profile_slope_deg", 0.0), 3),
            "length_mm": round(f["profile_len"], 1),
            "geometry": ("standard straight profile, cut to length — "
                         "modeled straight; the row slope is the mount's"),
        })
    rail_entries = []
    for rail in rails:
        perched_on = sorted({j.b_ref for j in perch_joints if j.a_ref == rail})
        rail_entries.append({
            "ref": rail,
            "perched_on": perched_on,
            "contact": "full_length",
        })
    flush_ok = verdict("assembly.row_flush_aligned") == "pass"
    support_ok = verdict("assembly.profile_support_full_length") == "pass"
    magnet_count = sum(
        int(s.form.frame.get("magnet_count", 0) or 0)
        for s in states.values() if s.form is not None)
    out = {
        "carrier": profile_entries,
        "rails": rail_entries,
        "slope_source": "physical_mount",
        "slope_deg": (round(mount.slope_deg, 3) if mount is not None else None),
        "mount": (mount.slope_source if mount is not None
                  else "UNDECLARED — no mount_context"),
        "full_profile_seating": support_ok,
        "span_gap_mm": 0 if support_ok else None,
        "stair_step": not flush_ok,
        "modules_flush": flush_ok,
        "support_verdict": verdict("assembly.profile_support_full_length"),
        "flush_verdict": verdict("assembly.row_flush_aligned"),
        "drainage_verdict": verdict("assembly.row_drains_under_mount"),
        "scope": (
            "tilted flush row: straight profiles, full seating, slope by "
            "mount; anti-slide retention under the mounted slope — VF-4.2"
        ),
    }
    if magnet_count:
        out["magnet_installation"] = {
            "method": "press_fit_dry_face",
            "water_exposed": False,
            "role": "alignment_only",
            "count": magnet_count,
        }
    return out
