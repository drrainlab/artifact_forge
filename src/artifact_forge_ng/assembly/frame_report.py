"""The frame/carrier report (VF-4) — the mechanical-support story of a
carried row, symmetric to the water report: which profiles carry which
rails, at what slope, with what contact quality. Derived from frame keys,
poses and the carrier findings — never re-measured here.

Scope honesty (printed into every report): VF-4 validates the support
REFERENCE — the profile part is a reference proxy of a standard straight
2020/3030 extrusion mounted at the global row slope. Anti-slide locking,
vibration and full-surface seating are deferred to VF-4.1.
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

    def verdict(check: str) -> str:
        hits = [j for j in joint_findings if j.check == check]
        if not hits:
            return "unchecked"
        return "pass" if all(h.status.value == "pass" for h in hits) else "FAIL"

    supported = next((j for j in joint_findings
                      if j.check == "assembly.row_supported"), None)
    profile_entries = []
    for prof in profiles:
        f = states[prof].form.frame
        profile_entries.append({
            "ref": prof,
            "size": f"{int(f['profile_size'])}{int(f['profile_size'])}",
            "slope_deg": round(f["profile_slope_deg"], 3),
            "length_mm": round(f["profile_len"], 1),
            "geometry": ("reference proxy — standard straight profile "
                         "mounted at the global row slope"),
        })
    rail_entries = []
    for rail in rails:
        perched_on = sorted({j.b_ref for j in perch_joints if j.a_ref == rail})
        rail_entries.append({
            "ref": rail,
            "perched_on": perched_on,
            "contact": "upstream_edge",
        })
    return {
        "carrier": profile_entries,
        "rails": rail_entries,
        "support_verdict": verdict("assembly.row_supported"),
        "pitch_verdict": verdict("assembly.row_pitch_aligned"),
        "slope_verdict": verdict("assembly.profile_slope_feeds_downhill"),
        "span_gap_mm": (round(supported.measured, 2)
                        if supported is not None and supported.measured is not None
                        else None),
        "scope": (
            "VF-4 validates the profile-carried support REFERENCE; "
            "anti-slide locking / vibration / full-surface seating "
            "deferred to VF-4.1"
        ),
    }
