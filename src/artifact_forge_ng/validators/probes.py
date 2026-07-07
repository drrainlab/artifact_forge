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
        _decl("form.field_cells_present", Level.FORM, "every declared field kept at least one cell after keepouts"),
        _decl("form.mount_face_flat", Level.FORM, "the in-profile mounting face is one flat top edge spanning the tongue"),
        _decl("form.constant_section", Level.FORM, "the part is a pure constant-section extrusion (small transverse holes allowed)"),
        _decl("form.shell_walls_ok", Level.FORM, "box-shell interior keeps the declared wall and floor thickness"),
        _decl("form.snap_arc_coverage", Level.FORM, "snap-clip cavity wraps the declared retention arc"),
        _decl("form.snap_mouth_retains", Level.FORM, "snap-clip mouth is measurably narrower than the held diameter"),
        # -- wall tool mount form checks (impls in form/checks_wallmount.py) --
        _decl("form.tool_saddle_radius_ok", Level.FORM, "saddle arc radius/center match the declared tool diameter and standoff"),
        _decl("form.tool_clearance_ok", Level.FORM, "effective saddle bore leaves the declared radial clearance around the tool"),
        _decl("form.retention_angle_ok", Level.FORM, "saddle arc wraps the declared capture angle, past half a circle"),
        _decl("form.mouth_gap_ok", Level.FORM, "mouth throat is narrower than the tool (retains) yet wide enough to insert"),
        _decl("form.mount_hole_positions_ok", Level.FORM, "two anchor holes on the flange centerline, clear of the collar and the edges"),
        _decl("form.ribs_connect_saddle_to_flange", Level.FORM, "ring fuses into the flange and every gusset rib bridges flange to ring flank"),
        _decl("form.anchor_wall_strength_unverified", Level.FORM, "honesty warning: wall material and anchor rating are external assumptions"),
        # -- biomorphic exoskeleton form checks (impls in form/checks_exoskeleton.py)
        _decl("form.rib_graph_connected", Level.FORM, "exoskeleton rib graph is a single component containing every root"),
        _decl("form.no_rib_islands", Level.FORM, "no rib node or component is disconnected from every anchor root"),
        _decl("form.rib_roots_touch_substrate", Level.FORM, "every rib root lands on an anchor region/edge within tolerance"),
        _decl("form.min_rib_diameter_ok", Level.FORM, "measured minimum rib diameter meets the declared floor"),
        _decl("form.windows_inside_safe_regions", Level.FORM, "every organic window polygon stays inside its window and clear of keepouts"),
        _decl("form.load_paths_connected", Level.FORM, "every declared load path routes through the rib graph from source to anchor"),
        _decl("form.no_load_path_through_keepout", Level.FORM, "declared load path polylines stay clear of keepout masks"),
        _decl("form.primary_load_path_has_ribs", Level.FORM, "the primary load path carries thickened ribs (Bio-3)"),
        # -- branch clamp form checks (impls in form/checks_clamp.py) ---------
        _decl("form.saddle_geometry_ok", Level.FORM, "saddle arc radius/center match the branch and the mouth opens at the mating plane"),
        _decl("form.pad_lands_present", Level.FORM, "the saddle carries its flat recessed TPU pad lands"),
        _decl("form.clamp_channel_clear", Level.FORM, "the axial cable channel spans the body with open ends and clear walls"),
        _decl("form.dovetail_rail_profile", Level.FORM, "the rail section is a real dovetail — top measurably wider than root"),
        # -- wearable cuff form checks (impls in form/checks_wearable.py) -----
        _decl("form.body_clearance_ok", Level.FORM, "arm cavity radius equals the measured limb radius plus the declared skin clearance"),
        _decl("form.arm_mouth_dons_ok", Level.FORM, "the cuff mouth is wide enough to don over flesh yet narrower than the limb diameter"),
        _decl("form.comfort_edge_radius_ok", Level.FORM, "every body-contact edge joint carries a fillet at least comfort_edge_r"),
        _decl("form.pad_recess_exists", Level.FORM, "all declared TPU pad lands are present and recessed outward from the skin"),
        _decl("form.payload_mount_not_on_skin_side", Level.FORM, "the payload clip sits outside the arm ring and opens away from the body"),
        _decl("form.payload_retention_ok", Level.FORM, "payload cavity coverage and mouth gap give real snap retention"),
        _decl("form.strap_access_ok", Level.FORM, "each strap tab carries a through slot pair clear of the arm circle with a solid strap bar"),
        _decl("form.dovetail_socket_profile_ok", Level.FORM, "the payload socket groove is a measured female dovetail at the declared widths and depth"),
        _decl("form.dovetail_foot_profile_ok", Level.FORM, "the adapter foot is a measured male dovetail whose free end is the wide end"),
        # -- vertical farm water checks (impls in form/checks_water.py) -------
        _decl("form.water_channel_slope_ok", Level.FORM, "channel floor falls monotonically toward the outlet at 1.0-1.5 degrees"),
        _decl("form.water_channel_dims_ok", Level.FORM, "channel width/depth/bottom radius in band and the run spans both body faces"),
        _decl("form.no_standing_water_ir", Level.FORM, "no blind pocket or above-bottom floor can hold water in the wet path"),
        _decl("form.overflow_lip_geometry_ok", Level.FORM, "overflow lip stays sharp (no blend zone) with the declared air gap relief below"),
        _decl("form.no_secondary_water_channel", Level.FORM, "exactly one water path; the drip receiver and cassette floor form no second trough"),
        _decl("form.cassette_seat_fit_ok", Level.FORM, "seat pocket matches the shared cassette envelope minus clearance, floor above the channel"),
        _decl("form.tongue_groove_profile_ok", Level.FORM, "groove = tongue + 2x clearance in the 0.3-0.5 band and the tongue never bottoms"),
        _decl("form.profile_seat_dry_ok", Level.FORM, "aluminum profile pocket sits fully outside every wet region"),
        # -- vertical farm cassette checks (impls in form/checks_substrate_cassette.py)
        _decl("form.mesh_floor_orthogonal_ok", Level.FORM, "floor mesh is one planar orthogonal slot grid, cell 4-8mm, ribs >= 1.2mm"),
        _decl("form.cassette_no_reservoir", Level.FORM, "the meshed floor covers the tray and nothing below it can hold water"),
        _decl("form.contact_window_geometry_ok", Level.FORM, "contact window drop 1-2mm, centered over the channel, meshed underside"),
        _decl("form.snap_pockets_cleanable", Level.FORM, "every snap window pierces the full wall — no blind wet pocket"),
        # -- vertical farm fluid adapters (VF-3; impls in form/checks_water.py)
        _decl("form.hose_bore_ok", Level.FORM, "the hose push-in bore matches the declared tube OD plus a real grip clearance and opens through both ends"),
        _decl("form.spout_drop_path_ok", Level.FORM, "the inlet cap's spout descends below the saddle plane, fits the rail corridor, and carries a straight vertical water path"),
        _decl("form.collector_tray_drains", Level.FORM, "the catch tray floor falls monotonically to a drain bore sitting at the floor's lowest point"),
        # -- VF-4 profile-carried row (impls in checks_water.py / carrier.py)
        _decl("form.profile_ref_geometry_ok", Level.FORM, "the profile reference proxy: sloped top monotonic, long enough for its stations, slope in band"),
        _decl("form.lift_access_ok", Level.FORM, "rim carries two finger notches wide enough for tool-free removal"),
        # -- interface level (wave A1, form-time) ------------------------------
        _decl("interface.frame_exists", Level.FORM, "every declared interface's datum is published on the form with its type's frame keys"),
        _decl("interface.keepouts_preserved", Level.FORM, "no cut touched a declared interface keepout region"),
        _decl("interface.frame_orthonormal", Level.FORM, "every port frame is an orthonormal axis-aligned triad (frameless ports WARN for one deprecation cycle)"),
        _decl("interface.normal_points_outward", Level.FORM, "each port normal leaves the part: no material along +normal, material behind the port"),
        _decl("interface.up_consistent", Level.FORM, "port up/axis agree with the type semantics (slide axes in the port plane, flow axes on the normal)"),
        # -- topology level: probed on the compiled solid ---------------------
        _decl("topology.single_connected_solid", Level.TOPOLOGY, "exactly one connected valid solid"),
        _decl("topology.cavity_open", Level.TOPOLOGY, "the cable cavity is a real void along the cable axis"),
        _decl("topology.mouth_opens_sideways", Level.TOPOLOGY, "the mouth is open through the +Y wall"),
        _decl("topology.asymmetric_lips_geometry", Level.TOPOLOGY, "material reaches further only in the lower lip band"),
        _decl("topology.flange_above_cradle", Level.TOPOLOGY, "flange material sits above the cradle in Z"),
        _decl("topology.screw_holes_open", Level.TOPOLOGY, "screw holes pass through the flange"),
        _decl("topology.countersinks_present", Level.TOPOLOGY, "conical countersinks removed material at hole rims"),
        _decl("topology.hex_field_present", Level.TOPOLOGY, "hex perforation removed material in the safe zone"),
        _decl("topology.tool_void_open", Level.TOPOLOGY, "the tool cylinder and its mouth window are real voids on the solid"),
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
        _decl("topology.bar_follows_arc", Level.TOPOLOGY, "the swept bar is solid along its whole declared arc"),
        # -- biomorphic / clamp topology probes --------------------------------
        _decl("topology.rail_present", Level.TOPOLOGY, "the dovetail rail core is solid material along the body"),
        _decl("topology.payload_void_open", Level.TOPOLOGY, "the payload cylinder and its upward mouth window are real voids on the solid"),
        _decl("topology.exoskeleton_ribs_materialized", Level.TOPOLOGY, "every rib graph edge is solid material on the compiled part (Bio-3)"),
        _decl("topology.organic_windows_open", Level.TOPOLOGY, "every organic window removed material through the panel (Bio-3)"),
        # -- vertical farm topology probes --------------------------------------
        _decl("topology.water_channel_open", Level.TOPOLOGY, "the water path is void along the sampled centerline just above the floor"),
        _decl("topology.water_channel_floor_solid", Level.TOPOLOGY, "material is solid just below the channel floor — no leaks into the body"),
        _decl("topology.overflow_relief_open", Level.TOPOLOGY, "the air-gap relief under the overflow lip is a real void"),
        _decl("topology.contact_window_present", Level.TOPOLOGY, "the lowered contact slab exists under the floor AND the mesh pierces it — material in the band, never solid, never gone"),
        _decl("topology.fluid_path_open", Level.TOPOLOGY, "the adapter's water path (tube bore, spout drop or tray-to-drain run) is void on the compiled solid"),
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
        _decl("assembly.clamp_gap_ir", Level.ASSEMBLY, "posed clamp halves keep the declared compression gap with coincident saddle centers"),
        # -- interface level (wave A1, assembly-time) --------------------------
        _decl("interface.mate_compatible", Level.ASSEMBLY, "every joint lands on declared ports of one type with complementary genders and mutual accepts"),
        _decl("interface.clearance_ok", Level.ASSEMBLY, "mated ports declare the same fit within its type's clearance band"),
        _decl("interface.fastener_access_ok", Level.ASSEMBLY, "every fastened interface's screw axes stay reachable in the pose"),
        _decl("interface.swap_part_builds", Level.ASSEMBLY, "a compatible counterpart swapped into the assembly still validates"),
        _decl("interface.mate_frames_opposed", Level.ASSEMBLY, "mated port normals oppose in the pose; orientation-sensitive types keep up/axis agreement"),
        _decl("assembly.fluid_joint_ir", Level.ASSEMBLY, "fluid handover flows downhill with compatible channel widths in the pose"),
        _decl("assembly.no_orphan_ports", Level.ASSEMBLY, "every required interface of every part is mated by some joint"),
        _decl("assembly.dovetail_ir", Level.ASSEMBLY, "male dovetail rides its groove with the clearance band, never bottoms, full engagement"),
        # -- vertical farm assembly checks (impls in assembly/joints.py) -------
        _decl("assembly.removable_insert_ir", Level.ASSEMBLY, "cassette drops into the seat with the clearance band, window over the channel, pulse-only water contact"),
        _decl("assembly.tongue_groove_ir", Level.ASSEMBLY, "adjacent modules align on tongue/groove with channel centerlines continuous at the pitch"),
        _decl("assembly.saddle_hang_ir", Level.ASSEMBLY, "auxiliary verification: the adapter's saddle really straddles the rail wall in the pose the fluid joint set, and its spout/bib fits the corridor"),
        _decl("assembly.profile_perch_ir", Level.ASSEMBLY, "the rail's bottom groove seats on the aluminum profile: width fit in band, axes aligned"),
        _decl("assembly.row_supported", Level.ASSEMBLY, "every rail in a carried row rests on the profile's sloped support line at its station — no cell hangs on a fluid joint"),
        _decl("assembly.row_pitch_aligned", Level.ASSEMBLY, "adjacent rails march at the module pitch and the profile stations land under their grooves"),
        _decl("assembly.profile_slope_feeds_downhill", Level.ASSEMBLY, "the carrier's global slope matches the fluid cascade — the profile preserves every downhill handover"),
        # -- region level ------------------------------------------------------
        _decl("region.keepouts_preserved", Level.REGION, "no cut touched a fastener/stress keepout region"),
        _decl("region.snap_root_not_perforated", Level.REGION, "the high-stress snap root region is solid"),
        # -- manufacturing level ----------------------------------------------
        _decl("manufacturing.min_wall", Level.MANUFACTURING, "measured minimum wall >= printer minimum"),
        _decl("manufacturing.bed_fit", Level.MANUFACTURING, "bounding box fits the print bed"),
        _decl("manufacturing.overhang", Level.MANUFACTURING, "overhang fraction acceptable for the support policy"),
        _decl("manufacturing.max_opening_span", Level.MANUFACTURING, "widest through-wall opening bridges without support"),
        # -- vertical farm cleanability (n/a fast-path on non-water parts) ------
        _decl("manufacturing.brush_access_to_water_channel", Level.MANUFACTURING, "the water channel opens to free air along its whole run and is wide enough to brush"),
        _decl("manufacturing.no_hidden_wet_crevices", Level.MANUFACTURING, "no sub-2mm crevice between cuts inside a wet region — water enters, a brush cannot"),
        _decl("manufacturing.no_unwashable_snap_pockets", Level.MANUFACTURING, "every snap window is void through the full wall on the compiled solid"),
        _decl("manufacturing.reference_geometry", Level.MANUFACTURING, "honesty note: this part is external hardware reference — manufacturability unverified by design"),
        # -- implicit exoskeleton skin (Bio-4M; findings emitted by the skin export stage)
        _decl("manufacturing.mesh_watertight", Level.MANUFACTURING, "exported implicit-skin mesh is edge-manifold watertight"),
        _decl("manufacturing.mesh_min_feature", Level.MANUFACTURING, "informational facet statistics of the implicit-skin mesh"),
        _decl("manufacturing.implicit_skin_fidelity", Level.MANUFACTURING, "analytic SDF honors the IR: ribs solid, windows void, functional holes exact"),
        _decl("manufacturing.skin_assembly_clearance", Level.MANUFACTURING, "skin never crosses mate/rail/seat/saddle/exit interfaces in the assembled pose"),
        _decl("manufacturing.boss_growth_preserves_fastener_access", Level.MANUFACTURING, "grown bosses keep head seats, driver access and open bores"),
        # -- quality level ------------------------------------------------------
        _decl("quality.moldedness", Level.QUALITY, "molded-utility family score"),
        _decl("quality.boxiness", Level.QUALITY, "boxy-primitive penalty score"),
        _decl("quality.silhouette_match", Level.QUALITY, "mesh silhouette agrees with the Form IR"),
        # -- Bio-4M visual metrics (gate on the pre-flight demo plate; WARN-only elsewhere)
        _decl("quality.rectangularity_reduced", Level.QUALITY, "skin-zone surface is measurably non-rectangular (axis-normal area fraction below threshold)"),
        _decl("quality.window_shadow_present", Level.QUALITY, "organic window recesses are deep enough to read as shadows, not engraving"),
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
    # biomorphic pack (docs/BIOMORPHIC.md): the clamp's must_not_have set
    "blocked_cable_channel": "topology.bores_open",
    "closed_branch_hole_without_split": "form.saddle_geometry_ok",
    "weak_saddle_contact": "form.pad_lands_present",
    "perforated_bolt_boss": "region.keepouts_preserved",
    "floating_ribs": "topology.ribs_present",
    # wearable cuff (wave P2): the cuff's must_not_have set
    "closed_cuff_ring": "form.arm_mouth_dons_ok",
    "payload_on_skin_side": "form.payload_mount_not_on_skin_side",
    "sharp_body_edges": "form.comfort_edge_radius_ok",
    # vertical farm pack (docs/VERTICAL_FARM_PACK.md): transient water honesty
    "closed_water_reservoir": "form.no_standing_water_ir",
    "dead_water_pocket": "form.no_standing_water_ir",
    "secondary_water_channel": "form.no_secondary_water_channel",
    "permanent_substrate_flooding": "form.contact_window_geometry_ok",
    "hidden_wet_cavity": "manufacturing.no_hidden_wet_crevices",
    "uncleanable_snap_cavity": "form.snap_pockets_cleanable",
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
