"""Vertical-farm check declarations — the VF vocabulary the pack adds to
KNOWN_CHECKS at registration (same fail-fast semantics as core names)."""
from __future__ import annotations

from artifact_forge_ng.core.findings import Level
from artifact_forge_ng.validators.probes import KNOWN_CHECKS, CheckDecl


def _decl(name: str, level: Level, description: str):
    return name, CheckDecl(name=name, level=level, description=description)


VF_CHECKS = dict(
    [
        _decl("form.water_channel_dims_ok", Level.FORM, "channel width/depth/bottom radius in band and the run spans both body faces"),
        _decl("form.no_standing_water_ir", Level.FORM, "no blind pocket or above-bottom floor can hold water in the wet path"),
        _decl("form.no_secondary_water_channel", Level.FORM, "exactly one water path; the drip receiver and cassette floor form no second trough"),
        _decl("form.cassette_seat_fit_ok", Level.FORM, "seat pocket matches the shared cassette envelope minus clearance, floor above the channel"),
        _decl("form.tongue_groove_profile_ok", Level.FORM, "groove = tongue + 2x clearance in the 0.3-0.5 band and the tongue never bottoms"),
        _decl("form.profile_seat_dry_ok", Level.FORM, "aluminum profile pocket sits fully outside every wet region"),
        _decl("form.mesh_floor_orthogonal_ok", Level.FORM, "floor mesh is one planar orthogonal slot grid, cell 4-8mm, ribs >= 1.2mm"),
        _decl("form.cassette_no_reservoir", Level.FORM, "the meshed floor covers the tray and nothing below it can hold water"),
        _decl("form.contact_window_geometry_ok", Level.FORM, "contact window drop 1-2mm, centered over the channel, meshed underside"),
        _decl("form.snap_pockets_cleanable", Level.FORM, "every snap window pierces the full wall — no blind wet pocket"),
        _decl("form.hose_bore_ok", Level.FORM, "the hose push-in bore matches the declared tube OD plus a real grip clearance and opens through both ends"),
        _decl("form.spout_drop_path_ok", Level.FORM, "the inlet cap's spout descends below the saddle plane, fits the rail corridor, and carries a straight vertical water path"),
        _decl("form.collector_tray_drains", Level.FORM, "the catch tray floor falls monotonically to a drain bore sitting at the floor's lowest point"),
        _decl("form.profile_ref_geometry_ok", Level.FORM, "the profile reference proxy: sloped top monotonic, long enough for its stations, slope in band"),
        _decl("form.water_channel_constant_depth_ok", Level.FORM, "the channel floor is level end to end (constant depth) — the row slope comes from the mount, never the rail"),
        _decl("form.lap_joint_geometry_ok", Level.FORM, "lap lip continues the channel floor plane into a through, open-bottom receiver with the declared overlap and clearances"),
        _decl("form.lap_slot_leak_path_controlled", Level.FORM, "seam-slot drips fall through open air into the wet-safe zone — clear of profiles, magnets and dry zones"),
        _decl("form.drainage_requires_mount", Level.FORM, "honesty note: a constant-depth channel drains only under the mounted row slope (1.0-2.0 deg) — buildable horizontal, operational mounted"),
        _decl("form.magnet_pockets_outside_water_zone", Level.FORM, "every module magnet pocket sits in dry body — no magnet face sees water"),
        _decl("form.magnet_pockets_do_not_break_wall", Level.FORM, "magnet pockets stay blind (never pierce the face) and keep >= 1.2 plastic to any wet zone"),
        _decl("form.dock_pockets_dry", Level.FORM, "endcap dock magnets are blind vertical (Z) pockets, press-fit, >= 1.2 plastic to every wet zone — the collector/cap arm docks onto the rail wall top"),
        _decl("form.screen_open_area_ratio_ok", Level.FORM, "VF-8 drain screen: total open area (bottom mesh + wall slots) is generous vs the drain bore so the basket never chokes the flow"),
        _decl("form.screen_debris_capacity_ok", Level.FORM, "VF-8 drain screen: the basket holds a real debris reservoir above the mesh — not full after one watering"),
        _decl("form.collector_sump_is_lowest_point", Level.FORM, "VF-8: the strainer sump well floor is the collector's absolute low point and the vertical drain descends from it"),
        _decl("form.tray_floor_slopes_to_sump", Level.FORM, "VF-8: the collector tray floor slopes to the sump from every side — a converging funnel cut with its mouth over the drain"),
        _decl("form.basket_not_transverse_flow_barrier", Level.FORM, "VF-8: the strainer sits in a sunken well fed by a funnel wider than the mouth — water falls IN from every side rather than being walled off across the tray"),
        _decl("form.no_standing_water_before_screen", Level.FORM, "VF-8: the funnel descends monotonically to the drain at the sump low point, so nothing stands upstream of the screen"),
        _decl("form.lightweight_windows_dry_ok", Level.FORM, "lightweight dry-shell windows: open-bottom, clear of every functional zone, >= 2.4 cover under the seat floor, ribs present between windows"),
        _decl("form.substrate_retained_under_mount", Level.FORM, "honesty note: the substrate must not creep downstream under the mounted slope (static for coco; real retention checks arrive with mat cassettes)"),
        _decl("form.root_chamber_ok", Level.FORM, "the root chamber troughs are level, full-length (mount-drained), open-top, over a solid blind containment bottom, clear of the pulse channel"),
        _decl("form.cassette_support_span_ok", Level.FORM, "every skeleton window hides fully under the cassette with a support grid around it — worst unsupported span under the cassette floor stays in band"),
        _decl("form.collector_receiver_matches_final_lap", Level.FORM, "the collector mouth is a real end receiver for the final lap lip: wide enough, 6-8 capture depth, a low drip apron past the lip tip"),
        _decl("form.receiver_open_top_cleanable", Level.FORM, "the receiver capture zone is open to the sky, the apron is a low curb (never a wall), and the zone flows into the open tray — a brush goes wherever a drop goes"),
        _decl("form.collector_drain_bore_supportless", Level.FORM, "the drain bore prints without support: vertical, or a teardrop roof on a horizontal run"),
        _decl("form.collector_structure_sturdy", Level.FORM, "the collector tray hangs on two full side walls (not thin columns): thick enough, rooted at the tray bottom, welded into the arm"),
        _decl("form.lift_access_ok", Level.FORM, "rim carries two finger notches wide enough for tool-free removal"),
        _decl("topology.water_channel_open", Level.TOPOLOGY, "the water path is void along the sampled centerline just above the floor"),
        _decl("topology.water_channel_floor_solid", Level.TOPOLOGY, "material is solid just below the channel floor — no leaks into the body"),
        _decl("topology.contact_window_present", Level.TOPOLOGY, "the lowered contact slab exists under the floor AND the mesh pierces it — material in the band, never solid, never gone"),
        _decl("topology.fluid_path_open", Level.TOPOLOGY, "the adapter's water path (tube bore, spout drop or tray-to-drain run) is void on the compiled solid"),
        _decl("assembly.fluid_joint_ir", Level.ASSEMBLY, "fluid handover flows downhill with compatible channel widths in the pose"),
        _decl("assembly.removable_insert_ir", Level.ASSEMBLY, "cassette drops into the seat with the clearance band, window over the channel, pulse-only water contact"),
        _decl("assembly.tongue_groove_ir", Level.ASSEMBLY, "adjacent modules align on tongue/groove with channel centerlines continuous at the pitch"),
        _decl("assembly.saddle_hang_ir", Level.ASSEMBLY, "auxiliary verification: the adapter's saddle really straddles the rail wall in the pose the fluid joint set, and its spout/bib fits the corridor"),
        _decl("assembly.profile_perch_ir", Level.ASSEMBLY, "the rail's bottom groove seats on the aluminum profile: width fit in band, axes aligned"),
        _decl("assembly.lap_flow_ir", Level.ASSEMBLY, "adjacent rails mate flush: lip in the receiver at the declared overlap, floors coplanar, controlled face gap"),
        _decl("assembly.row_flush_aligned", Level.ASSEMBLY, "all rails share one row plane (dZ=0) and march at module_w + face_gap — stair steps are forbidden"),
        _decl("assembly.profile_support_full_length", Level.ASSEMBLY, "every rail groove is coplanar with the straight profile top — full seating, zero span gap"),
        _decl("assembly.magnet_alignment_ok", Level.ASSEMBLY, "adjacent modules' magnet pockets are coaxial in the pose (alignment only — never seal, never support)"),
        _decl("assembly.cassettes_removable_under_mount", Level.ASSEMBLY, "every cassette stays hand-removable with the row mounted at its slope"),
        _decl("assembly.collector_captures_drain_edge", Level.ASSEMBLY, "in the pose the final lap lip tip sits INSIDE the collector receiver volume — an end receiver, not a part standing nearby"),
        _decl("assembly.collector_mouth_envelopes_outlet_lip", Level.ASSEMBLY, "the receiver mouth envelopes the posed lip across X with real side margin"),
        _decl("assembly.collector_removable_by_hand", Level.ASSEMBLY, "no collector material above the captured lip — the receiver has no ceiling, so the collector lifts straight off"),
        _decl("assembly.collector_catches_root_drainage", Level.ASSEMBLY, "the collector tray mouth spans the final rail's root troughs so the passive root drainage lands in the tray"),
        _decl("assembly.endcap_docks_to_rail", Level.ASSEMBLY, "the endcap's dock magnets land on a matching rail dock pocket across the arm/wall-top contact — the magnetic dock actually mates in the pose"),
        _decl("assembly.screen_normal_no_bypass", Level.ASSEMBLY, "VF-8: the drop-in screen basket seats over the collector drain so water reaches it only through the mesh (no side bypass), can't slide off the drain, lifts out tool-free, and by default its rim sits above the tray overflow so a clog spills the open tray visibly"),
        _decl("assembly.drain_inside_screen_footprint", Level.ASSEMBLY, "VF-8: the collector drain bore is fully enclosed by the basket footprint in the assembled pose — water enters only through the mesh"),
        _decl("assembly.screen_removable_from_sump", Level.ASSEMBLY, "VF-8: the basket stands proud of the sump well and lifts straight out tool-free (drop-in, no snap/screw)"),
        _decl("assembly.cap_drip_lands_in_channel_safe_floor", Level.ASSEMBLY, "VF-9: the inlet cap drips onto a channel-safe floor (the floored lip-seat pocket or the solid channel floor right after it), never a through hole that drops the water to the level below"),
        _decl("assembly.cap_chute_drains_under_mount", Level.ASSEMBLY, "VF-9.2: the cap's level open chute drains toward its drip tip IN THE MOUNTED POSE — virtual heights under the declared row tilt descend from the chamber end to the nose tip"),
        _decl("form.cap_water_path_visible", Level.FORM, "VF-9.2: the inlet cap contains no closed horizontal water tunnel — a vertical socket+orifice, a short covered drop chamber, then an open-top chute the eye can follow to the drip tip"),
        _decl("assembly.lap_joint_no_external_downward_leak", Level.ASSEMBLY, "VF-9: the module-to-module lap seam has NO open path straight down — the receiver is a floored lip-seat, water crosses over the nested lip, only the controlled top tip-slot stays open"),
        _decl("form.lap_receiver_has_floor", Level.FORM, "VF-9: the inlet lap receiver is a top-open pocket with a SOLID bottom (a floored lip-seat), not a through hole under the water path"),
        _decl("form.lap_receiver_residual_volume_ok", Level.FORM, "VF-9: the lap receiver is a SHALLOW lip-seat (depth <= 2mm, length <= the lip overlap), not a small reservoir that holds a deep wet pocket when the neighbour's lip is absent"),
        _decl("form.rail_universal_inlet_accepts_cap_and_lap", Level.FORM, "VF-9: the rail inlet is universal — a floored receiver that both catches an inlet-cap drip and seats a neighbour's lap lip (no special capped variant)"),
        _decl("manufacturing.no_through_holes_in_wet_lap_zone", Level.MANUFACTURING, "VF-9 invariant: no cutbox with an open bottom sits under the active water path (a TRANSIENT_WATER_PATH region), except the sanctioned collector drain — no leaks straight down"),
        _decl("manufacturing.supportless_lightweight_windows_ok", Level.MANUFACTURING, "bottom-entered pockets never hide a support-critical flat ceiling — through/vaulted/skeleton, probed on the solid"),
        _decl("manufacturing.cap_supportless_verified", Level.MANUFACTURING, "VF-9 Part B: the inlet cap prints support-free as-modeled — the saddle-slot rest ledge is a short one-sided overhang (not a floating cantilever) and a nose column reaches the bed to anchor the roof; closes the VF-7c saddle-bridge blind spot"),
        _decl("manufacturing.brush_access_to_water_channel", Level.MANUFACTURING, "the water channel opens to free air along its whole run and is wide enough to brush"),
        _decl("manufacturing.no_hidden_wet_crevices", Level.MANUFACTURING, "no sub-2mm crevice between cuts inside a wet region — water enters, a brush cannot"),
        _decl("manufacturing.no_unwashable_snap_pockets", Level.MANUFACTURING, "every snap window is void through the full wall on the compiled solid"),
    _decl("assembly.row_drains_under_mount", Level.ASSEMBLY, "under the declared mount_context slope the whole water path descends monotonically — no context, out-of-band or reversed slope FAILS"),
    ]
)


#: VF forbidden-form vocabulary -> detector check (merged into the core map).
VF_FORBIDDEN_FORMS = {
    "closed_water_reservoir": "form.no_standing_water_ir",
    "dead_water_pocket": "form.no_standing_water_ir",
    "secondary_water_channel": "form.no_secondary_water_channel",
    "permanent_substrate_flooding": "form.contact_window_geometry_ok",
    "hidden_wet_cavity": "manufacturing.no_hidden_wet_crevices",
    "uncleanable_snap_cavity": "form.snap_pockets_cleanable",
}


def declare() -> None:
    """Idempotent: importing any part of the pack declares the vocabulary."""
    for name, decl in VF_CHECKS.items():
        existing = KNOWN_CHECKS.get(name)
        if existing is None:
            KNOWN_CHECKS[name] = decl
        elif existing is not decl:
            raise RuntimeError(f"VF pack: check {name!r} already declared "
                               "by someone else")
    from artifact_forge_ng.validators.probes import FORBIDDEN_FORM_DETECTORS
    FORBIDDEN_FORM_DETECTORS.update(VF_FORBIDDEN_FORMS)
