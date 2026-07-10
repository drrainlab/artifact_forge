"""Cassette seat/span, secondary-channel, tongue-groove, profile-seat
and root-chamber checks.
"""
from __future__ import annotations

from ..core.findings import Finding, Level
from ..validators.probes import register_probe
from .part import PartForm
from .checks_common import make_finding
from .checks_water_common import (
    _boxes_overlap, _wet_regions, CONST_DEPTH_TOL, FLOOR_MARGIN_MIN, SEAT_CLEARANCE_BAND, TG_SIDE_CLEARANCE_BAND, TG_BOTTOM_MARGIN, LW_RIB_MIN, CASSETTE_COVER, CASSETTE_SPAN_MAX)

_finding = make_finding


def check_cassette_support_span_ok(form: PartForm) -> Finding:
    """The cassette must not sag over the open skeleton (VF-4.1): every
    window hides FULLY under the cassette seat footprint (>= CASSETTE_COVER
    margin inside — the cassette covers each opening), the support grid
    survives around them (perimeter ring + channel spine + ribs), and the
    worst unsupported span under the cassette floor stays in band.
    Trivially green with lightweight off."""
    f = form.frame
    wins = [c for c in form.cutboxes if "_lwin_" in c.name]
    troughs = [c for c in form.channels if "root_trough" in c.name]
    if troughs:
        # root chamber: the cassette spans the open-top troughs; each must
        # be no wider than the support span, with a rib between them
        problems: list[str] = []
        tw = f.get("root_trough_w", 0.0)
        if tw > CASSETTE_SPAN_MAX:
            problems.append(
                f"root trough {tw:g} wide > {CASSETTE_SPAN_MAX:g} — the cassette "
                "sags between the ribs")
        if f.get("root_trough_rib", 0.0) < LW_RIB_MIN:
            problems.append("root trough ribs too thin to carry the cassette")
        return _finding(
            "form.cassette_support_span_ok", not problems,
            f"{len(troughs)} root troughs, {tw:g} wide on {f.get('root_trough_rib',0):g} "
            "ribs — the cassette spans them stiffly"
            if not problems else "; ".join(problems),
            measured=tw, limit=CASSETTE_SPAN_MAX)
    if not f.get("lw_enabled", False) or not wins:
        return _finding("form.cassette_support_span_ok", True,
                        "solid slab under the cassette — full support")
    keys = ("seat_u0", "seat_v0", "seat_u1", "seat_v1", "channel_w", "lw_rib")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.cassette_support_span_ok", False,
                        f"no frame keys: {', '.join(missing)}")
    problems: list[str] = []
    worst = 0.0
    for win in wins:
        b = win.box
        # band edges are LEGAL: window layouts computed from the same seat
        # numbers land EXACTLY on the margin line — never fail float dust
        eps = 0.01
        if (b.x0 < f["seat_u0"] + CASSETTE_COVER - eps
                or b.x1 > f["seat_u1"] - CASSETTE_COVER + eps
                or b.y0 < f["seat_v0"] + CASSETTE_COVER - eps
                or b.y1 > f["seat_v1"] - CASSETTE_COVER + eps):
            problems.append(
                f"window {win.name!r} pokes out from under the cassette seat "
                f"(needs >= {CASSETTE_COVER:g} inside the footprint)")
        span = min(b.x1 - b.x0, b.y1 - b.y0)
        worst = max(worst, span)
        if span > CASSETTE_SPAN_MAX:
            problems.append(
                f"window {win.name!r} leaves a {span:.1f} unsupported span "
                f"under the cassette (max {CASSETTE_SPAN_MAX:g})")
    # the support grid: no two windows may merge (rib survives between them)
    for i in range(len(wins)):
        for j in range(i + 1, len(wins)):
            a, b = wins[i].box, wins[j].box
            gap_x = max(a.x0, b.x0) - min(a.x1, b.x1)
            gap_y = max(a.y0, b.y0) - min(a.y1, b.y1)
            if max(gap_x, gap_y) < f["lw_rib"] - 0.2:
                problems.append(
                    f"windows {wins[i].name!r}/{wins[j].name!r} merge — the "
                    "support rib between them is gone")
    # the channel spine: openings never cross the channel band (the spine
    # under the cassette's contact window is always solid)
    ch_half = f["channel_w"] / 2.0
    for win in wins:
        if win.box.x0 < ch_half and win.box.x1 > -ch_half:
            problems.append(f"window {win.name!r} eats the channel spine")
    return _finding(
        "form.cassette_support_span_ok", not problems,
        f"{len(wins)} openings fully under the cassette; worst unsupported "
        f"span {worst:.1f} <= {CASSETTE_SPAN_MAX:g} on the ring + spine + rib "
        "grid (the 2 mm cassette floor with its mesh spans this stiffly; "
        "channel-zone reinforcement arrives with VF-5 cassettes)"
        if not problems else "; ".join(problems),
        measured=worst, limit=CASSETTE_SPAN_MAX,
    )


def check_no_secondary_water_channel(form: PartForm) -> Finding:
    if form.channels:
        problems: list[str] = []
        # The rail owns exactly ONE transient pulse channel. Root-drainage
        # troughs (VF-5 root chamber) are a DIFFERENT, legalized subsystem
        # (passive_root_drainage_return) — level, mount-drained, named
        # *_root_trough_* — and do not count as a second pulse channel.
        pulse = [c for c in form.channels if "root_trough" not in c.name]
        if len(pulse) != 1:
            problems.append(f"{len(pulse)} pulse water channels declared — the rail owns exactly one")
        receiver = form.region("drip_receiver")
        if receiver is not None:
            for cut in form.cutboxes:
                b = cut.box
                if b.z0 > 0.05 and _boxes_overlap(b, receiver.box):
                    problems.append(
                        f"pocket {cut.name!r} would turn the drip receiver into a second trough")
        return _finding(
            "form.no_secondary_water_channel", not problems,
            "one water path; the drip receiver stays open"
            if not problems else "; ".join(problems),
        )
    if form.fields:
        problems = []
        if len(form.fields) != 1:
            problems.append(f"{len(form.fields)} floor fields — the mesh floor is exactly one grid")
        fld = form.fields[0]
        if fld.pattern != "slots":
            problems.append(f"floor field pattern {fld.pattern!r} is not an orthogonal slot grid")
        if fld.mapping != "planar" or fld.origin is not None or abs(fld.tilt_deg) > 1e-6:
            problems.append("floor field is not flat — a shaped mesh directs flow")
        return _finding(
            "form.no_secondary_water_channel", not problems,
            "one flat orthogonal mesh — holds coco, does not channel water"
            if not problems else "; ".join(problems),
        )
    return _finding("form.no_secondary_water_channel", False,
                    "no channel and no floor field — nothing to measure")


def check_cassette_seat_fit_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("seat_u0", "seat_v0", "seat_u1", "seat_v1",
            "seat_floor_z", "seat_clearance", "channel_top_z")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.cassette_seat_fit_ok", False,
                        f"no seat frame keys: {', '.join(missing)}")
    cassette_l = form.params.get("cassette_l")
    cassette_w = form.params.get("cassette_w")
    if cassette_l is None or cassette_w is None:
        return _finding("form.cassette_seat_fit_ok", False,
                        "no cassette_l/cassette_w params — the shared envelope is unbound")
    c = f["seat_clearance"]
    problems: list[str] = []
    if not (SEAT_CLEARANCE_BAND[0] <= c <= SEAT_CLEARANCE_BAND[1]):
        problems.append(
            f"seat clearance {c:g} outside {SEAT_CLEARANCE_BAND[0]}..{SEAT_CLEARANCE_BAND[1]}")
    want_u = cassette_l + 2.0 * c
    want_v = cassette_w + 2.0 * c
    got_u = f["seat_u1"] - f["seat_u0"]
    got_v = f["seat_v1"] - f["seat_v0"]
    if abs(got_u - want_u) > 0.1:
        problems.append(f"seat X extent {got_u:.2f} != cassette {cassette_l:g} + 2x{c:g}")
    if abs(got_v - want_v) > 0.1:
        problems.append(f"seat Y extent {got_v:.2f} != cassette {cassette_w:g} + 2x{c:g}")
    if abs(f["seat_floor_z"] - f["channel_top_z"]) > 0.05:
        problems.append(
            f"seat floor {f['seat_floor_z']:g} is not the channel entry plane "
            f"{f['channel_top_z']:g} — the cassette would dam or float over the water")
    return _finding(
        "form.cassette_seat_fit_ok", not problems,
        f"seat fits the shared cassette envelope with {c:g} clearance"
        if not problems else "; ".join(problems),
        measured=c, limit=SEAT_CLEARANCE_BAND[1],
    )


def check_tongue_groove_profile_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("tongue_w", "tongue_h", "tongue_len", "groove_w", "groove_depth",
            "edge_clearance", "tongue_cy", "groove_cy", "tongue_z0", "groove_z0")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.tongue_groove_profile_ok", False,
                        f"no tongue/groove frame keys: {', '.join(missing)}")
    problems: list[str] = []
    side = (f["groove_w"] - f["tongue_w"]) / 2.0
    if not (TG_SIDE_CLEARANCE_BAND[0] <= side <= TG_SIDE_CLEARANCE_BAND[1]):
        problems.append(
            f"per-side clearance {side:.2f} outside "
            f"{TG_SIDE_CLEARANCE_BAND[0]}..{TG_SIDE_CLEARANCE_BAND[1]}")
    if abs(side - f["edge_clearance"]) > 0.02:
        problems.append(
            f"measured clearance {side:.2f} != declared {f['edge_clearance']:g}")
    if f["tongue_len"] > f["groove_depth"] - TG_BOTTOM_MARGIN:
        problems.append(
            f"tongue {f['tongue_len']:g} bottoms in the groove {f['groove_depth']:g} — "
            "the joint must only align, never carry or seal")
    if abs(f["tongue_cy"] - f["groove_cy"]) > 0.05:
        problems.append("tongue and groove are not on the same line axis")
    if abs(f["tongue_z0"] - f["groove_z0"]) > 0.05:
        problems.append("tongue and groove sit at different heights")
    has_tongue = any("tongue" in r.name for r in form.ribs)
    has_groove = any("groove" in c.name for c in form.cutboxes)
    if not has_tongue:
        problems.append("no tongue rib on the part")
    if not has_groove:
        problems.append("no groove cut on the part")
    return _finding(
        "form.tongue_groove_profile_ok", not problems,
        f"groove = tongue + 2x{side:.2f}; the tongue floats {f['groove_depth'] - f['tongue_len']:.1f} short of the bottom"
        if not problems else "; ".join(problems),
        measured=side, limit=TG_SIDE_CLEARANCE_BAND[1],
    )


def check_profile_seat_dry_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("profile_size", "profile_slot_w", "profile_slot_clearance", "profile_slot_depth")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.profile_seat_dry_ok", False,
                        f"no profile seat frame keys: {', '.join(missing)}")
    slots = [c for c in form.cutboxes if "profile" in c.name]
    if not slots:
        return _finding("form.profile_seat_dry_ok", False,
                        "no profile slot cuts on the part")
    problems: list[str] = []
    want_w = f["profile_size"] + 2.0 * f["profile_slot_clearance"]
    if abs(f["profile_slot_w"] - want_w) > 0.05:
        problems.append(
            f"slot width {f['profile_slot_w']:g} != profile {f['profile_size']:g} "
            f"+ 2x{f['profile_slot_clearance']:g}")
    wet = _wet_regions(form)
    for slot in slots:
        for w in wet:
            if _boxes_overlap(slot.box, w.box):
                problems.append(f"profile slot {slot.name!r} intersects wet region {w.name!r}")
    return _finding(
        "form.profile_seat_dry_ok", not problems,
        f"{len(slots)} profile slot(s) fully outside the water path"
        if not problems else "; ".join(problems),
        measured=f["profile_slot_w"], limit=want_w,
    )

def check_root_chamber_ok(form: PartForm) -> Finding:
    """VF-5 root chamber: the open-top troughs form a valid, cleanable,
    self-draining root zone. Level const-depth (the MOUNT drains them, no
    geometry slope), running the FULL length so they exit both faces (a
    guaranteed forward exit under the mount, and they chain module-to-
    module to the collector), a solid blind bottom below for containment,
    and clear of the pulse channel spine. n/a-PASS when not a root
    chamber."""
    check = "form.root_chamber_ok"
    troughs = [c for c in form.channels if "root_trough" in c.name]
    if not troughs:
        return _finding(check, True, "no root chamber on this part — n/a")
    f = form.frame
    problems: list[str] = []
    y0, y1 = f.get("rail_y0"), f.get("rail_y1")
    ch_half = f.get("channel_w", 0.0) / 2.0
    floor_z = f.get("root_trough_floor_z")
    for c in troughs:
        if abs(c.depth_end - c.depth_start) > CONST_DEPTH_TOL:
            problems.append(
                f"{c.name!r} is not level — the mount drains the troughs, "
                "geometry slope is the old cascade")
        # full length: spans both faces so it drains forward under the mount
        lo, hi = min(c.y0, c.y1), max(c.y0, c.y1)
        if y0 is not None and (lo > y0 + 0.01 or hi < y1 - 0.01):
            problems.append(
                f"{c.name!r} does not span both faces — no guaranteed forward "
                "exit / module-to-module chaining")
        # clear of the pulse channel spine
        if abs(c.center_x) - c.width / 2.0 < ch_half + 2.0:
            problems.append(f"{c.name!r} eats into the channel spine")
    # blind containment bottom below the troughs
    if floor_z is None:
        problems.append("no root_trough_floor_z — blind bottom unproven")
    elif floor_z < FLOOR_MARGIN_MIN:
        problems.append(
            f"only {floor_z:g} solid below the troughs (needs >= "
            f"{FLOOR_MARGIN_MIN:g}) — the containment bottom is too thin")
    return _finding(
        check, not problems,
        f"{len(troughs)} level open-top root troughs over a {floor_z:g} blind "
        "bottom — roots grow in, the mount drains them forward, brush-open "
        "after the cassette lifts"
        if not problems else "; ".join(problems),
        measured=floor_z, limit=FLOOR_MARGIN_MIN,
    )


register_probe("form.root_chamber_ok")(
    lambda form, ctx: check_root_chamber_ok(form))
register_probe("form.cassette_support_span_ok")(
    lambda form, ctx: check_cassette_support_span_ok(form))
register_probe("form.no_secondary_water_channel")(
    lambda form, ctx: check_no_secondary_water_channel(form))
register_probe("form.cassette_seat_fit_ok")(
    lambda form, ctx: check_cassette_seat_fit_ok(form))
register_probe("form.tongue_groove_profile_ok")(
    lambda form, ctx: check_tongue_groove_profile_ok(form))
register_probe("form.profile_seat_dry_ok")(
    lambda form, ctx: check_profile_seat_dry_ok(form))

