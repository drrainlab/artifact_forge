"""Mode profiles — the first mode scaffold, not a mode framework.

A mode is BEHAVIOR, not a flag: it names the context blocks an instance
must carry (``required_context``) and the summary tags the pipeline
surfaces. Fields like default_priorities / protected_roles arrive with
their consumers (the same law as region roles) — this registry only
grows a field when something measurable reads it.

The registry is the single source of truth for legal mode names:
``ProductInstance.mode`` validates against ``MODE_PROFILES`` keys, so
adding a mode here is the whole act of introducing it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModeProfile:
    #: ProductInstance field names that must be present (not None) for the
    #: mode to make sense — enforced at instance schema validation.
    required_context: tuple[str, ...] = ()
    #: Informational tags surfaced in the pipeline summary.
    summary_tags: tuple[str, ...] = ()


MODE_PROFILES: dict[str, ModeProfile] = {
    "engineering": ModeProfile(),
    "wearable": ModeProfile(
        required_context=("body_fit",),
        summary_tags=("body_fit", "comfort", "strap_mount"),
    ),
}
