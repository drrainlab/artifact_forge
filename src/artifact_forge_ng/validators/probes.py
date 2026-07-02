"""The check-name registry — the single vocabulary every YAML document's
``validators:``, ``forbidden_forms:``, ``contract:`` and ``verified_by:``
entries bind against at catalog load. An unknown name is a LOAD ERROR, never
a silent skip.

Declarations live here (importable without cadquery); geometry probe
implementations attach themselves via :func:`register_probe` when their
module imports (``validators/topology.py`` etc. — cad extra). A check whose
implementation is unavailable in this environment simply does not run, so
any feature it verifies stays honestly un-built.

Naming convention: ``<level>.<check>`` — e.g. ``form.mouth_opens_sideways``
(measured on the Form IR, no CAD) vs ``topology.mouth_opens_sideways``
(probed on the compiled solid).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..core.findings import Level


@dataclass
class CheckDecl:
    name: str
    level: Level
    description: str = ""
    #: Attached by the implementing module; signature depends on level:
    #: form checks take (PartForm) -> list[Finding];
    #: geometry probes take (solid, params, bbox) -> bool | None.
    impl: Callable[..., Any] | None = None


def _decl(name: str, level: Level, description: str) -> tuple[str, CheckDecl]:
    return name, CheckDecl(name=name, level=level, description=description)


KNOWN_CHECKS: dict[str, CheckDecl] = dict(
    [
        # -- form level: measured analytically on the Form IR, no CAD --------
        _decl("form.profile_closed", Level.FORM, "section profile is one closed simple CCW loop"),
        _decl("form.profile_smooth", Level.FORM, "profile joints are tangent or tagged intentional corners"),
        _decl("form.mouth_opens_sideways", Level.FORM, "mouth direction is +u (sideways), from tagged segments"),
        _decl("form.mouth_gap_matches", Level.FORM, "measured mouth gap equals the resolved parameter"),
        _decl("form.lower_lip_longer_than_upper", Level.FORM, "measured lower lip length > 1.5x upper"),
        _decl("form.not_symmetric_c_ring", Level.FORM, "profile matches the asymmetric side-hook family"),
        _decl("form.flange_above_cradle", Level.FORM, "flange plate sits above the hook body"),
        _decl("form.wall_thickness", Level.FORM, "wall between cavity and outer chain >= wall parameter"),
        _decl("form.regions_present", Level.FORM, "all semantic regions the archetype declares exist"),
        _decl("form.contact_edges_rounded", Level.FORM, "cable-contact segments carry the contact radius"),
        _decl("form.hex_field_in_safe_zone", Level.FORM, "hex field centers avoid every keepout region"),
        # -- topology level: probed on the compiled solid ---------------------
        _decl("topology.single_connected_solid", Level.TOPOLOGY, "exactly one connected valid solid"),
        _decl("topology.cavity_open", Level.TOPOLOGY, "the cable cavity is a real void along the cable axis"),
        _decl("topology.mouth_opens_sideways", Level.TOPOLOGY, "the mouth is open through the +Y wall"),
        _decl("topology.asymmetric_lips_geometry", Level.TOPOLOGY, "material reaches further only in the lower lip band"),
        _decl("topology.flange_above_cradle", Level.TOPOLOGY, "flange material sits above the cradle in Z"),
        _decl("topology.screw_holes_open", Level.TOPOLOGY, "screw holes pass through the flange"),
        _decl("topology.countersinks_present", Level.TOPOLOGY, "conical countersinks removed material at hole rims"),
        _decl("topology.hex_field_present", Level.TOPOLOGY, "hex perforation removed material in the safe zone"),
        # -- region level ------------------------------------------------------
        _decl("region.keepouts_preserved", Level.REGION, "no cut touched a fastener/stress keepout region"),
        _decl("region.snap_root_not_perforated", Level.REGION, "the high-stress snap root region is solid"),
        # -- manufacturing level ----------------------------------------------
        _decl("manufacturing.min_wall", Level.MANUFACTURING, "measured minimum wall >= printer minimum"),
        _decl("manufacturing.bed_fit", Level.MANUFACTURING, "bounding box fits the print bed"),
        _decl("manufacturing.overhang", Level.MANUFACTURING, "overhang fraction acceptable for the support policy"),
        # -- quality level ------------------------------------------------------
        _decl("quality.moldedness", Level.QUALITY, "molded-utility family score"),
        _decl("quality.boxiness", Level.QUALITY, "boxy-primitive penalty score"),
        _decl("quality.silhouette_match", Level.QUALITY, "mesh silhouette agrees with the Form IR"),
    ]
)

#: Forbidden form id -> the check that detects it is ABSENT. must_not_have
#: and forbidden_forms entries bind against this map.
FORBIDDEN_FORM_DETECTORS: dict[str, str] = {
    "symmetric_c_ring": "form.not_symmetric_c_ring",
    "closed_ring": "form.mouth_opens_sideways",
    "downward_entry": "form.mouth_opens_sideways",
    "boxy_rectangular_hook": "form.profile_smooth",
}


def known_check(name: str) -> bool:
    return name in KNOWN_CHECKS


def register_probe(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach an implementation to a declared check. Registering an
    undeclared name is a programming error and raises immediately."""

    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        decl = KNOWN_CHECKS.get(name)
        if decl is None:
            raise KeyError(f"cannot register probe for undeclared check {name!r}")
        decl.impl = fn
        return fn

    return wrap
