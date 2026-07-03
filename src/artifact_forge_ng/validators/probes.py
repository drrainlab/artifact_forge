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
        _decl("form.screw_access_clear", Level.FORM, "a screwdriver reaches every screw from below without hitting the hook"),
        # -- phase-5 form checks (impls in form/checks_*.py) ------------------
        _decl("form.slots_open_topped", Level.FORM, "every comb slot's throat reaches the profile's top edge"),
        _decl("form.slot_throat_retention", Level.FORM, "measured throat width is narrower than the cable (snap retention)"),
        _decl("form.teeth_count_matches", Level.FORM, "number of slot cavities equals the declared slot count"),
        _decl("form.tunnel_fits_tie", Level.FORM, "measured tunnel section fits the declared tie plus clearances"),
        _decl("form.tip_lip_present", Level.FORM, "the hook tip lip rises by the declared lip height"),
        _decl("form.bay_open_top", Level.FORM, "the hook bay entry between lip tip and plate stays open"),
        _decl("form.channel_inside_walls", Level.FORM, "every bore keeps the minimum wall inside its host section"),
        _decl("form.revolve_profile_clear_of_axis", Level.FORM, "the half-section never touches or crosses the revolve axis"),
        _decl("form.stability_footprint", Level.FORM, "combined part+device COM stays inside the base footprint"),
        _decl("form.min_web_between_holes", Level.FORM, "no two holes closer than the minimum web"),
        _decl("form.holes_within_outline", Level.FORM, "every hole keeps the minimum web to the outline"),
        _decl("form.cuts_respect_keepouts", Level.FORM, "no bore or box cut intersects a keepout region"),
        _decl("form.device_slot_fits", Level.FORM, "measured device slot fits the declared device thickness at tilt"),
        _decl("form.min_ligament_ok", Level.FORM, "webs between field cells meet the declared minimum ligament"),
        _decl("form.mount_face_flat", Level.FORM, "the in-profile mounting face is one flat top edge spanning the tongue"),
        _decl("form.constant_section", Level.FORM, "the part is a pure constant-section extrusion (small transverse holes allowed)"),
        _decl("form.shell_walls_ok", Level.FORM, "box-shell interior keeps the declared wall and floor thickness"),
        _decl("form.snap_arc_coverage", Level.FORM, "snap-clip cavity wraps the declared retention arc"),
        _decl("form.snap_mouth_retains", Level.FORM, "snap-clip mouth is measurably narrower than the held diameter"),
        # -- topology level: probed on the compiled solid ---------------------
        _decl("topology.single_connected_solid", Level.TOPOLOGY, "exactly one connected valid solid"),
        _decl("topology.cavity_open", Level.TOPOLOGY, "the cable cavity is a real void along the cable axis"),
        _decl("topology.mouth_opens_sideways", Level.TOPOLOGY, "the mouth is open through the +Y wall"),
        _decl("topology.asymmetric_lips_geometry", Level.TOPOLOGY, "material reaches further only in the lower lip band"),
        _decl("topology.flange_above_cradle", Level.TOPOLOGY, "flange material sits above the cradle in Z"),
        _decl("topology.screw_holes_open", Level.TOPOLOGY, "screw holes pass through the flange"),
        _decl("topology.countersinks_present", Level.TOPOLOGY, "conical countersinks removed material at hole rims"),
        _decl("topology.hex_field_present", Level.TOPOLOGY, "hex perforation removed material in the safe zone"),
        # -- phase-5 topology probes ------------------------------------------
        _decl("topology.bores_open", Level.TOPOLOGY, "every declared bore is void along its span"),
        _decl("topology.channel_continuous", Level.TOPOLOGY, "the wiring channel is void along its full L-path"),
        _decl("topology.slots_open", Level.TOPOLOGY, "every comb slot's cavity and throat are void"),
        _decl("topology.tunnel_open", Level.TOPOLOGY, "the tie tunnel is void along the extrusion axis"),
        _decl("topology.revolve_cavity_open", Level.TOPOLOGY, "the revolved cavity is void along the axis end to end"),
        _decl("topology.cutout_present", Level.TOPOLOGY, "every declared box cut removed material"),
        _decl("topology.bay_open", Level.TOPOLOGY, "the hook bay entry gap is void on the compiled solid"),
        _decl("topology.ribs_present", Level.TOPOLOGY, "every declared rib welded on as real material"),
        _decl("topology.pockets_present", Level.TOPOLOGY, "every blind pocket removed material without piercing through"),
        _decl("topology.seat_lips_present", Level.TOPOLOGY, "every bearing seat keeps its retaining lip ring solid"),
        _decl("topology.arm_reaches_tip", Level.TOPOLOGY, "the cantilever/loft arm is solid out to its tip"),
        _decl("topology.pins_present", Level.TOPOLOGY, "every alignment/press-fit pin is real material along its length"),
        # -- assembly level: cross-part checks in the assembled pose ----------
        _decl("assembly.screw_joint_ir", Level.ASSEMBLY, "bolt patterns coincide with compatible diameters in the pose"),
        _decl("assembly.joint_pose", Level.ASSEMBLY, "every part is posed by a joint against existing datums"),
        _decl("assembly.no_interference", Level.ASSEMBLY, "placed parts touch but never overlap"),
        _decl("assembly.screw_axes_clear", Level.ASSEMBLY, "every joint screw axis is void through the assembled stack"),
        _decl("assembly.channel_continuous_across", Level.ASSEMBLY, "the cable path is void through EVERY part in the pose"),
        _decl("assembly.lid_seat_ir", Level.ASSEMBLY, "lid plug dimensions chain to the shell interior minus clearance"),
        _decl("assembly.press_fit_ir", Level.ASSEMBLY, "pins land on receiving bores with the declared interference"),
        _decl("assembly.pins_engage", Level.ASSEMBLY, "every pin physically occupies its receiving bore in the pose"),
        _decl("assembly.lid_seats", Level.ASSEMBLY, "the lid plug sits inside the shell rim in the pose"),
        _decl("assembly.butt_pin_ir", Level.ASSEMBLY, "butt-split halves share one section and align on end pins"),
        _decl("assembly.snap_joint_ir", Level.ASSEMBLY, "snap hooks reach their windows with printable flexure strain"),
        _decl("assembly.hooks_engage", Level.ASSEMBLY, "every snap hook lip occupies its window in the pose"),
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
    # phase-5 families (forbidden forms stay per-archetype: a springy
    # symmetric C is legal for a broom clip, closed_slot never is for a comb)
    "closed_slot": "form.slots_open_topped",
    "blocked_tunnel": "topology.tunnel_open",
    "blocked_channel": "topology.channel_continuous",
    "profile_crosses_axis": "form.revolve_profile_clear_of_axis",
    "tipping_stand": "form.stability_footprint",
    "closed_bay": "form.bay_open_top",
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
