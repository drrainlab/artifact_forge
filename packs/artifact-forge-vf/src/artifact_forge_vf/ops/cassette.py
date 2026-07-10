"""Vertical-farm substrate cassette ops — tray body, contact window,
mesh floor, lift tabs, screen wall slots.
"""
from __future__ import annotations

from typing import Any
from artifact_forge_ng.product.archetype import RegionRole
from artifact_forge_ng.form.regions import Box3, Region
from artifact_forge_ng.form.part import CutBoxFeature, FieldFeature, RibFeature
from artifact_forge_ng.form.recipe_ops_core import RECIPE_OPS, RecipeError, RecipeOpDecl, RecipeState, _register


# -- substrate_tray_body (base) -------------------------------------------------


def _substrate_tray_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The removable cassette shell: a rounded_box_shell that ALSO
    publishes the Cassette Interface Standard frame keys (cassette_*) and
    the seat/rim datums the removable_insert and snap joints read."""
    shell = RECIPE_OPS["rounded_box_shell"]
    shell.apply(state, {
        "l": p["cassette_l"], "w": p["cassette_w"], "h": p["h"],
        "wall": p["wall"], "floor_t": p["floor_t"], "corner_r": p["corner_r"],
    }, op_id or "tray")
    f = state.frame
    state.frame.update(
        cassette_u0=f["outline_u0"], cassette_v0=f["outline_v0"],
        cassette_u1=f["outline_u1"], cassette_v1=f["outline_v1"],
        cassette_h=f["shell_h"], floor_bottom_z=0.0,
    )
    state.datums["seat"] = {"at": [0.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]}


_register(RecipeOpDecl(
    name="substrate_tray_body",
    kind="base",
    params={
        "cassette_l": ("length", None), "cassette_w": ("length", None),
        "h": ("length", 26.0), "wall": ("length", 2.4),
        "floor_t": ("length", 2.0), "corner_r": ("length", 3.0),
    },
    validators=(
        "form.shell_walls_ok", "topology.cutout_present",
        "topology.single_connected_solid",
    ),
    apply=_substrate_tray_body,
    description="removable substrate cassette shell publishing the "
                "Cassette Interface Standard keys",
))


# -- contact_window (feature) ---------------------------------------------------


def _contact_window(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The localized lowered window: a slab welded UNDER the cassette
    floor that reaches window_drop into the channel's upper zone — pulse
    water touches the substrate through the mesh, drained water never
    does. Run BEFORE mesh_floor so the mesh knows how deep to pierce."""
    state.require_base("contact_window")
    f = state.frame
    if "floor_t" not in f:
        raise RecipeError("contact_window needs a substrate_tray_body base")
    w, length, drop = p["window_w"], p["window_l"], p["drop"]
    cx, cy = p["cx"], p["cy"]
    if (cx - w / 2.0 < f["inner_u0"] + 2.0 or cx + w / 2.0 > f["inner_u1"] - 2.0
            or cy - length / 2.0 < f["inner_v0"] + 2.0
            or cy + length / 2.0 > f["inner_v1"] - 2.0):
        raise RecipeError("contact window does not fit inside the tray floor")
    name = op_id or "window"
    slab = Box3(cx - w / 2.0, cy - length / 2.0, -drop,
                cx + w / 2.0, cy + length / 2.0, 0.6)
    state.ribs.append(RibFeature(name=f"{name}_slab", box=slab))
    state.regions.append(Region(
        "contact_window", RegionRole.TRANSIENT_WATER_PATH,
        Box3(slab.x0, slab.y0, -drop - 0.1, slab.x1, slab.y1, 0.6),
    ))
    state.frame.update(
        window_cx=cx, window_w=w, window_l=length,
        window_drop=drop, window_floor_z=-drop,
    )


_register(RecipeOpDecl(
    name="contact_window",
    kind="feature",
    params={
        # narrower than the rail channel so the slab drops INTO it —
        # contact area comes from window_l along the flow, not width
        "window_w": ("length", 12.0), "window_l": ("length", 60.0),
        "drop": ("length", 1.5), "cx": ("length", 0.0), "cy": ("length", 0.0),
    },
    validators=("form.contact_window_geometry_ok", "topology.contact_window_present"),
    apply=_contact_window,
    description="lowered substrate-contact slab under the floor — pulse "
                "water reach, never permanent flooding",
))


# -- mesh_floor (feature) --------------------------------------------------------


def _mesh_floor(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The flat orthogonal mesh: an axis-aligned grid of square through
    cells across the tray floor. Holds coco, aerates roots, directs
    nothing. Pierces the contact-window slab too (fields cut last)."""
    state.require_base("mesh_floor")
    f = state.frame
    if "floor_t" not in f:
        raise RecipeError("mesh_floor needs a substrate_tray_body base")
    cell, rib, margin = p["cell"], p["rib"], p["margin"]
    u0, v0 = f["inner_u0"] + margin, f["inner_v0"] + margin
    u1, v1 = f["inner_u1"] - margin, f["inner_v1"] - margin
    if u1 - u0 < cell or v1 - v0 < cell:
        raise RecipeError("tray floor too small for a single mesh cell")
    pitch = cell + rib
    nx = int((u1 - u0 + rib) // pitch)
    ny = int((v1 - v0 + rib) // pitch)
    x_start = (u0 + u1) / 2.0 - (nx - 1) * pitch / 2.0
    y_start = (v0 + v1) / 2.0 - (ny - 1) * pitch / 2.0
    half = cell / 2.0
    polygons = tuple(
        (
            (x_start + i * pitch - half, y_start + j * pitch - half),
            (x_start + i * pitch + half, y_start + j * pitch - half),
            (x_start + i * pitch + half, y_start + j * pitch + half),
            (x_start + i * pitch - half, y_start + j * pitch + half),
        )
        for i in range(nx) for j in range(ny)
    )
    drop = f.get("window_drop", 0.0)
    state.fields.append(FieldFeature(
        plane_z=f["floor_t"], centers=(), cell=cell,
        depth=f["floor_t"] + drop + 1.0, pattern="slots",
        polygons=polygons, min_ligament=rib,
    ))
    state.regions.append(Region(
        "mesh_canvas", RegionRole.SUBSTRATE_SUPPORT_MESH,
        Box3(u0, v0, -0.1, u1, v1, f["floor_t"]),
    ))
    state.frame.update(mesh_cell=cell, mesh_rib=rib)


_register(RecipeOpDecl(
    name="mesh_floor",
    kind="feature",
    params={
        "cell": ("length", 6.0), "rib": ("length", 1.3),
        "margin": ("length", 6.0),
    },
    validators=(
        "form.mesh_floor_orthogonal_ok", "form.cassette_no_reservoir",
        "form.min_ligament_ok", "form.no_secondary_water_channel",
        "topology.hex_field_present",
    ),
    apply=_mesh_floor,
    description="flat orthogonal through-mesh across the cassette floor",
))


# -- lift_tabs (feature) ----------------------------------------------------------


def _lift_tabs(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Two open finger notches through the +-Y rim — the cassette lifts
    out of the rail by hand, no tools, nothing to unscrew."""
    state.require_base("lift_tabs")
    f = state.frame
    if "shell_wall" not in f:
        raise RecipeError("lift_tabs needs a substrate_tray_body base")
    w, d = p["notch_w"], p["notch_d"]
    h, wall = f["shell_h"], f["shell_wall"]
    name = op_id or "lift"
    for i, (lo, hi) in enumerate((
        (f["outline_v0"] - 1.0, f["outline_v0"] + wall + 1.0),
        (f["outline_v1"] - wall - 1.0, f["outline_v1"] + 1.0),
    )):
        state.cutboxes.append(CutBoxFeature(
            name=f"{name}_notch_{i}",
            box=Box3(-w / 2.0, lo, h - d, w / 2.0, hi, h + 1.0),
        ))
    state.frame.update(lift_notch_w=w, lift_notch_d=d, lift_notch_count=2.0)


_register(RecipeOpDecl(
    name="lift_tabs",
    kind="feature",
    params={"notch_w": ("length", 18.0), "notch_d": ("length", 8.0)},
    validators=("form.lift_access_ok", "topology.cutout_present"),
    apply=_lift_tabs,
    description="finger notches through the rim for tool-free removal",
))


# -- screen_wall_slots (feature) -----------------------------------------------


def _screen_wall_slots(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """VF-8 drain-screen basket features (on a substrate_tray_body cup): a FINE
    bottom mesh (the filter — square through-cells) plus WIDE vertical wall
    slots (fail-safe side-flow when the bottom silts up), and the sizing keys
    (open area, debris reservoir, rim/floor z, footprint) the seat joint and
    screen checks read. This does NOT reuse mesh_floor — that op carries
    coco-cassette validators (cell 4-8mm, open >=0.45) a fine strainer must not
    subscribe to."""
    state.require_base("screen_wall_slots")
    f = state.frame
    if "shell_h" not in f:
        raise RecipeError("screen_wall_slots needs a substrate_tray_body base")
    u0, v0, u1, v1 = f["outline_u0"], f["outline_v0"], f["outline_u1"], f["outline_v1"]
    iu0, iv0, iu1, iv1 = f["inner_u0"], f["inner_v0"], f["inner_u1"], f["inner_v1"]
    h, wall = f["shell_h"], f["shell_wall"]
    floor_t = f.get("floor_t", 2.0)
    cell, rib, margin = p.get("mesh_cell", 2.0), p.get("mesh_rib", 1.3), p.get("mesh_margin", 2.0)
    slot_w = p.get("slot_w", 7.0)
    slot_h = p.get("slot_h", 6.0)
    name = op_id or "screen"

    # -- fine bottom mesh (the filter) — square through-cells, like mesh_floor
    mu0, mv0 = iu0 + margin, iv0 + margin
    mu1, mv1 = iu1 - margin, iv1 - margin
    if mu1 - mu0 < cell or mv1 - mv0 < cell:
        raise RecipeError("screen floor too small for a single mesh cell")
    pitch = cell + rib
    nx = max(1, int((mu1 - mu0 + rib) // pitch))
    ny = max(1, int((mv1 - mv0 + rib) // pitch))
    x0 = (mu0 + mu1) / 2.0 - (nx - 1) * pitch / 2.0
    y0 = (mv0 + mv1) / 2.0 - (ny - 1) * pitch / 2.0
    half = cell / 2.0
    polygons = tuple(
        ((x0 + i * pitch - half, y0 + j * pitch - half),
         (x0 + i * pitch + half, y0 + j * pitch - half),
         (x0 + i * pitch + half, y0 + j * pitch + half),
         (x0 + i * pitch - half, y0 + j * pitch + half))
        for i in range(nx) for j in range(ny)
    )
    state.fields.append(FieldFeature(
        plane_z=floor_t, centers=(), cell=cell, depth=floor_t + 1.0,
        pattern="slots", polygons=polygons, min_ligament=rib,
    ))
    state.regions.append(Region(
        "mesh_canvas", RegionRole.SUBSTRATE_SUPPORT_MESH,
        Box3(mu0, mv0, -0.1, mu1, mv1, floor_t)))
    mesh_area = nx * ny * cell * cell

    # -- wide vertical wall slots (the primary filter surface for a compact
    # cup — the shallow-tray basket has little bottom mesh, so ALL FOUR walls
    # carry tall side slots). Fail-safe side-flow: a silted bottom drains out
    # the sides, and a clog rises visibly in the OPEN tray.
    z0 = floor_t + 1.5
    z1 = min(z0 + slot_h, h - 2.0)
    slot_span = max(0.0, z1 - z0)
    inner_x, inner_y = iu1 - iu0, iv1 - iv0
    slot_area = 0.0

    def _wall_slots(span, along_x, w0, w1):
        n = max(1, int((span + 3.0) // (slot_w + 3.0)))
        used = n * slot_w + (n - 1) * 3.0
        start = -used / 2.0 + slot_w / 2.0
        area = 0.0
        for i in range(n):
            c = start + i * (slot_w + 3.0)
            if along_x:
                box = Box3(c - slot_w / 2.0, w0, z0, c + slot_w / 2.0, w1, z1)
            else:
                box = Box3(w0, c - slot_w / 2.0, z0, w1, c + slot_w / 2.0, z1)
            state.cutboxes.append(CutBoxFeature(
                name=f"{name}_slot_{'x' if along_x else 'y'}{i}_{w0:.0f}", box=box))
            area += slot_w * slot_span
        return n, area

    nx_f, a = _wall_slots(inner_x, True, v0 - 1.0, v0 + wall + 1.0); slot_area += a
    nx_b, a = _wall_slots(inner_x, True, v1 - wall - 1.0, v1 + 1.0); slot_area += a
    ny_l, a = _wall_slots(inner_y, False, u0 - 1.0, u0 + wall + 1.0); slot_area += a
    ny_r, a = _wall_slots(inner_y, False, u1 - wall - 1.0, u1 + 1.0); slot_area += a
    n = nx_f + nx_b + ny_l + ny_r

    inner_w = iu1 - iu0
    inner_d = iv1 - iv0
    debris_ml = (inner_w * inner_d * max(0.0, h - floor_t - 2.0)) / 1000.0
    state.frame.update(
        screen_u0=u0, screen_v0=v0, screen_u1=u1, screen_v1=v1,
        screen_rim_z=h, screen_floor_z=floor_t, screen_wall_t=wall,
        screen_slot_count=float(n), screen_mesh_cells=float(nx * ny),
        screen_mesh_area_mm2=mesh_area, screen_slot_area_mm2=slot_area,
        screen_open_area_mm2=mesh_area + slot_area,
        screen_debris_volume_ml=debris_ml,
    )


_register(RecipeOpDecl(
    name="screen_wall_slots",
    kind="feature",
    params={
        "mesh_cell": ("length", 2.0), "mesh_rib": ("length", 1.3),
        "mesh_margin": ("length", 2.0),
        "slot_w": ("length", 7.0), "slot_h": ("length", 6.0),
    },
    validators=(
        "form.screen_open_area_ratio_ok",
        "form.screen_debris_capacity_ok",
        "form.min_ligament_ok",
        "topology.hex_field_present",
    ),
    apply=_screen_wall_slots,
    description="VF-8 drain-screen: fine bottom filter mesh + wide fail-safe "
                "wall slots + sizing keys for a drop-in strainer basket",
))


