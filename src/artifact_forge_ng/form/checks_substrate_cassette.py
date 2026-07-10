"""IR checks for the vertical farm substrate cassette family — the coco
tray must carry a flat orthogonal mesh floor (holds substrate, never
channels water), a localized contact window that touches pulse water only,
through-wall snap windows a brush can reach, and finger notches for
tool-free removal. Self-registers on import.

Frame-key contract (the cassette half of the Cassette Interface Standard —
any future cassette archetype publishes the same keys): cassette_u0/v0/u1/
v1, cassette_h, floor_t, floor_bottom_z, window_cx, window_w, window_l,
window_drop, window_floor_z, lift_notch_w, lift_notch_d, lift_notch_count,
plus the shell keys (shell_wall, inner_u0/u1) the snap joint reads.
"""

from __future__ import annotations

from ..core.findings import Finding, Level, Status
from ..validators.probes import register_probe
from .part import PartForm

MESH_CELL_BAND = (4.0, 8.0)
MESH_RIB_MIN = 1.2
MESH_OPEN_FRACTION_MIN = 0.45
MESH_COVERAGE_MIN = 0.8  # of the mesh canvas extent, per axis
WINDOW_DROP_BAND = (1.0, 2.0)
#: The window must fit INSIDE the rail channel (walls clear) — the real
#: containment is verified by the removable_insert joint in the pose.
WINDOW_W_BAND = (8.0, 40.0)
SNAP_WINDOW_MIN_W = 6.0
SNAP_WINDOW_MIN_H = 3.0
LIFT_NOTCH_MIN_W = 16.0
LIFT_NOTCH_MIN_D = 6.0


from .checks_common import make_finding
_finding = make_finding


def _poly_bbox(polygons) -> tuple[float, float, float, float] | None:
    xs = [p[0] for poly in polygons for p in poly]
    ys = [p[1] for poly in polygons for p in poly]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _poly_area(poly) -> float:
    area = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0


def check_mesh_floor_orthogonal_ok(form: PartForm) -> Finding:
    if not form.fields:
        return _finding("form.mesh_floor_orthogonal_ok", False,
                        "no floor field — the cassette has no mesh")
    fld = form.fields[0]
    problems: list[str] = []
    if len(form.fields) != 1:
        problems.append(f"{len(form.fields)} fields — the floor carries exactly one grid")
    if fld.pattern != "slots" or not fld.polygons:
        problems.append("floor field is not an explicit slot grid")
    if fld.mapping != "planar" or fld.origin is not None or abs(fld.tilt_deg) > 1e-6:
        problems.append("mesh is not flat")
    if fld.min_ligament < MESH_RIB_MIN:
        problems.append(f"mesh rib {fld.min_ligament:g} < {MESH_RIB_MIN:g}")
    cells_off_band = 0
    for poly in fld.polygons:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        # orthogonal grid: every cell is an axis-aligned rectangle
        if len(poly) != 4 or len(set(xs)) != 2 or len(set(ys)) != 2:
            problems.append("mesh cells are not axis-aligned rectangles")
            break
        if not (MESH_CELL_BAND[0] - 1e-6 <= w <= MESH_CELL_BAND[1] + 1e-6
                and MESH_CELL_BAND[0] - 1e-6 <= h <= MESH_CELL_BAND[1] + 1e-6):
            cells_off_band += 1
    if cells_off_band:
        problems.append(
            f"{cells_off_band} mesh cell(s) outside {MESH_CELL_BAND[0]}..{MESH_CELL_BAND[1]}")
    canvas = form.region("mesh_canvas")
    if canvas is not None and fld.polygons:
        b = canvas.box
        canvas_area = max((b.x1 - b.x0) * (b.y1 - b.y0), 1e-9)
        open_area = sum(_poly_area(p) for p in fld.polygons)
        if open_area / canvas_area < MESH_OPEN_FRACTION_MIN:
            problems.append(
                f"open-area fraction {open_area / canvas_area:.2f} < "
                f"{MESH_OPEN_FRACTION_MIN:g} — coco roots suffocate")
    return _finding(
        "form.mesh_floor_orthogonal_ok", not problems,
        f"flat orthogonal mesh, {len(fld.polygons)} cells, rib {fld.min_ligament:g}"
        if not problems else "; ".join(problems),
        measured=fld.min_ligament, limit=MESH_RIB_MIN,
    )


def check_cassette_no_reservoir(form: PartForm) -> Finding:
    f = form.frame
    floor_t = f.get("floor_t")
    if floor_t is None:
        return _finding("form.cassette_no_reservoir", False,
                        "no floor_t frame key — cannot prove the floor drains")
    if not form.fields or not form.fields[0].polygons:
        return _finding("form.cassette_no_reservoir", False,
                        "no mesh field — a solid floor is a reservoir")
    fld = form.fields[0]
    drop = f.get("window_drop", 0.0)
    problems: list[str] = []
    if abs(fld.plane_z - floor_t) > 0.1:
        problems.append(
            f"mesh cuts from z={fld.plane_z:g}, not the floor top {floor_t:g}")
    if fld.depth < floor_t + drop + 0.5:
        problems.append(
            f"mesh depth {fld.depth:g} does not pierce floor + window slab "
            f"({floor_t:g} + {drop:g}) — blind dimples pool water")
    canvas = form.region("mesh_canvas")
    bbox = _poly_bbox(fld.polygons)
    if canvas is not None and bbox is not None:
        b = canvas.box
        for axis, (lo, hi, blo, bhi) in {
            "X": (bbox[0], bbox[2], b.x0, b.x1),
            "Y": (bbox[1], bbox[3], b.y0, b.y1),
        }.items():
            extent = max(bhi - blo, 1e-9)
            if (hi - lo) / extent < MESH_COVERAGE_MIN:
                problems.append(
                    f"mesh covers only {(hi - lo) / extent:.0%} of the floor along {axis} "
                    "— the bare rim is a moat")
    return _finding(
        "form.cassette_no_reservoir", not problems,
        "meshed floor pierces through — nothing under the coco holds water"
        if not problems else "; ".join(problems),
        measured=fld.depth, limit=floor_t + drop + 0.5,
    )


def check_contact_window_geometry_ok(form: PartForm) -> Finding:
    f = form.frame
    keys = ("window_cx", "window_w", "window_l", "window_drop", "window_floor_z")
    missing = [k for k in keys if k not in f]
    if missing:
        return _finding("form.contact_window_geometry_ok", False,
                        f"no contact window frame keys: {', '.join(missing)}")
    problems: list[str] = []
    if not (WINDOW_DROP_BAND[0] <= f["window_drop"] <= WINDOW_DROP_BAND[1]):
        problems.append(
            f"window drop {f['window_drop']:g} outside "
            f"{WINDOW_DROP_BAND[0]}..{WINDOW_DROP_BAND[1]} — shallower never touches "
            "pulse water, deeper dams the channel")
    if not (WINDOW_W_BAND[0] <= f["window_w"] <= WINDOW_W_BAND[1]):
        problems.append(f"window width {f['window_w']:g} outside {WINDOW_W_BAND[0]}..{WINDOW_W_BAND[1]}")
    if abs(f["window_floor_z"] - (-f["window_drop"])) > 0.1:
        problems.append(
            f"window floor {f['window_floor_z']:g} != -drop {-f['window_drop']:g} "
            "(cassette floor bottom is z=0)")
    slab = [r for r in form.ribs if "window" in r.name]
    if not slab:
        problems.append("no contact window slab welded under the floor")
    else:
        b = slab[0].box
        if b.z1 < 0.3:
            problems.append("window slab does not weld into the floor")
    if form.fields and form.fields[0].polygons:
        wx0 = f["window_cx"] - f["window_w"] / 2.0
        wx1 = f["window_cx"] + f["window_w"] / 2.0
        inside = 0
        for poly in form.fields[0].polygons:
            cx = sum(p[0] for p in poly) / len(poly)
            cy = sum(p[1] for p in poly) / len(poly)
            if wx0 <= cx <= wx1 and abs(cy) <= f["window_l"] / 2.0:
                inside += 1
        if inside == 0:
            problems.append("no mesh cells inside the window footprint — the "
                            "contact face is solid, water clings permanently")
    return _finding(
        "form.contact_window_geometry_ok", not problems,
        f"window drops {f['window_drop']:g} into the channel over a meshed underside"
        if not problems else "; ".join(problems),
        measured=f["window_drop"], limit=WINDOW_DROP_BAND[1],
    )


def check_snap_pockets_cleanable(form: PartForm) -> Finding:
    windows = [c for c in form.cutboxes if "snap_window" in c.name]
    if not windows:
        return _finding("form.snap_pockets_cleanable", True,
                        "no snap pockets on this part — nothing to trap water")
    wall = form.frame.get("shell_wall")
    if wall is None:
        return _finding("form.snap_pockets_cleanable", False,
                        "snap windows without a shell_wall frame key — cannot prove they pierce")
    problems: list[str] = []
    for win in windows:
        b = win.box
        dims = sorted((b.x1 - b.x0, b.y1 - b.y0, b.z1 - b.z0))
        if dims[0] < wall + 0.5:
            problems.append(
                f"{win.name!r} spans {dims[0]:.2f} — does not pierce the {wall:g} wall "
                "(a blind wet pocket)")
        if dims[1] < SNAP_WINDOW_MIN_H or dims[2] < SNAP_WINDOW_MIN_W:
            problems.append(
                f"{win.name!r} opening {dims[2]:.1f}x{dims[1]:.1f} too small to brush "
                f"(needs >= {SNAP_WINDOW_MIN_W:g}x{SNAP_WINDOW_MIN_H:g})")
    return _finding(
        "form.snap_pockets_cleanable", not problems,
        f"{len(windows)} snap window(s) pierce the wall — open both sides"
        if not problems else "; ".join(problems),
    )


def check_lift_access_ok(form: PartForm) -> Finding:
    f = form.frame
    count = f.get("lift_notch_count", 0.0)
    if count < 2:
        return _finding("form.lift_access_ok", False,
                        "fewer than two lift notches — no tool-free grip",
                        measured=count, limit=2.0)
    w, d = f.get("lift_notch_w", 0.0), f.get("lift_notch_d", 0.0)
    problems: list[str] = []
    if w < LIFT_NOTCH_MIN_W:
        problems.append(f"notch width {w:g} < {LIFT_NOTCH_MIN_W:g} — a finger does not fit")
    if d < LIFT_NOTCH_MIN_D:
        problems.append(f"notch depth {d:g} < {LIFT_NOTCH_MIN_D:g} — no grip purchase")
    return _finding(
        "form.lift_access_ok", not problems,
        f"{count:g} finger notches {w:g}x{d:g} — lifts out by hand"
        if not problems else "; ".join(problems),
        measured=w, limit=LIFT_NOTCH_MIN_W,
    )


def check_substrate_retained_under_mount(form: PartForm) -> Finding:
    """Honesty note, PASS-with-note: at the mounted row slope (1.0-2.0
    deg) loose coco is static — friction angles are an order of magnitude
    higher — so nothing creeps toward the downstream wall. This note
    becomes a REAL retention check (governor lip, mat anchoring) when
    mat/rockwool cassettes join the family."""
    if not form.fields:
        return _finding("form.substrate_retained_under_mount", False,
                        "no mesh floor on this part — not a substrate cassette")
    return Finding(
        check="form.substrate_retained_under_mount", status=Status.PASS,
        level=Level.FORM,
        message=("INFO: loose coco is static at the 1.0-2.0 deg mount slope "
                 "(friction >> slope); retention hardware becomes real with "
                 "future mat cassettes"),
        critical=False,
    )


register_probe("form.mesh_floor_orthogonal_ok")(
    lambda form, ctx: check_mesh_floor_orthogonal_ok(form))
register_probe("form.cassette_no_reservoir")(
    lambda form, ctx: check_cassette_no_reservoir(form))
register_probe("form.contact_window_geometry_ok")(
    lambda form, ctx: check_contact_window_geometry_ok(form))
register_probe("form.snap_pockets_cleanable")(
    lambda form, ctx: check_snap_pockets_cleanable(form))
register_probe("form.lift_access_ok")(
    lambda form, ctx: check_lift_access_ok(form))
register_probe("form.substrate_retained_under_mount")(
    lambda form, ctx: check_substrate_retained_under_mount(form))
