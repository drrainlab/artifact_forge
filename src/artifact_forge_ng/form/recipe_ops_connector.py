"""Connector recipe ops — a cylindrical hub growing axis-aligned socket
arms (elbow / tee / cross / 5-way): the trellis-connector family, and the
limb machinery the tube tee shares. Deliberate v1 scope: branches on the
frame axes only (±X, ±Y, +Z) — arbitrary angles need an oriented kernel
primitive that does not exist yet.

Model frame: hub axis = Z, standing on the bed. X/Y arms carry teardrop
bore roofs (printed as-modeled, no supports); their set screws enter from
the arm top, a +Z arm takes a horizontal one.
Measurement contract: :mod:`artifact_forge_ng.form.checks_connector`."""
from __future__ import annotations

from typing import Any

from ..core.fasteners import screw_spec
from .part import BoreFeature, PinFeature
from .profiles_revolve import loop_from_points
from .recipe_ops_core import RecipeError, RecipeOpDecl, RecipeState, _register
from .regions import Box3, Region
from .section import Pt, SectionProfile
from ..product.archetype import RegionRole

SOCKET_ENGAGE_K = 1.2   # socket depth >= k * rod diameter
SOCKET_WALL_MIN = 2.0   # wall around a socket bore, mm
PRESS_INTERFERENCE = 0.15  # diametral press fit for a printed rod

DIRS = ("+x", "-x", "+y", "-y", "+z")
_DIR_CODE = {d: float(i) for i, d in enumerate(DIRS)}


def _multi_socket_hub(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """The central body every socket arm welds into: a revolved cylinder
    standing on the bed."""
    if state.section is not None:
        raise RecipeError("multi_socket_hub must be the (single) base op")
    r_hub = p["hub_d"] / 2.0
    h = p["hub_h"]
    if r_hub < 6.0 or h < 14.0:
        raise RecipeError("hub under Ø12 x 14 leaves no room for sockets")
    pts = [Pt(0.0, 0.0), Pt(r_hub, 0.0), Pt(r_hub, h), Pt(0.0, h)]
    state.section = SectionProfile(
        name="recipe_revolve", outer=loop_from_points(pts),
        plane="XZ", width_axis="Y")
    state.kind = "profile_revolve"
    state.width = 2.0 * r_hub
    name = op_id or "hub"
    state.regions.append(Region(
        f"{name}_body", RegionRole.MOUNTING_SURFACE,
        Box3(-r_hub, -r_hub, 0.0, r_hub, r_hub, h)))
    state.datums["hub_center"] = {
        "at": [0.0, 0.0, h / 2.0], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(hub_r=r_hub, hub_h=h, socket_count=0.0)


_register(RecipeOpDecl(
    name="multi_socket_hub",
    kind="base",
    params={"hub_d": ("length", None), "hub_h": ("length", None)},
    validators=("topology.single_connected_solid",),
    apply=_multi_socket_hub,
    description="cylindrical connector hub the socket arms weld into",
))


def _socket_arm(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """One socket arm on a hub: a welded barrel along ±X/±Y/+Z with a
    blind rod socket bored from its mouth, optional set-screw pilot.
    Invoke once per branch — elbow, tee, cross and 5-way are recipes,
    not separate ops."""
    state.require_base("socket_arm")
    if int(round(p["enabled"])) == 0:
        return  # recipe-level branch toggle: this arm is off
    f = state.frame
    if "hub_r" not in f:
        raise RecipeError("socket_arm needs a multi_socket_hub base")
    d = p["dir"]
    if d not in DIRS:
        raise RecipeError(f"socket_arm dir {d!r} not in {DIRS}")
    if f.get(f"arm_{d}_used", 0.0) > 0.0:
        raise RecipeError(f"a socket arm already occupies {d}")
    rod_d = p["rod_d"]
    clearance = p["clearance"]
    wall = p["wall"]
    fit = p["fit"]
    if fit == "slip":
        bore_d = rod_d + clearance
    elif fit == "press":
        bore_d = rod_d - PRESS_INTERFERENCE
    else:
        raise RecipeError(f"fit {fit!r} not in (slip, press)")
    depth = p["depth"] if p["depth"] > 1e-9 else SOCKET_ENGAGE_K * rod_d
    outer_d = rod_d + 2.0 * clearance + 2.0 * wall
    r_hub, hub_h = f["hub_r"], f["hub_h"]
    name = op_id or f"arm_{d.replace('+', 'p').replace('-', 'm')}"

    if d == "+z":
        arm_len = depth + wall
        state.pins.append(PinFeature(
            name=f"{name}_barrel", axis="Z", at=(0.0, 0.0),
            d=outer_d, z0=hub_h - 0.6, length=arm_len + 0.6,
            bore_d=bore_d))
        mouth = hub_h + arm_len
        state.bores.append(BoreFeature(
            name=f"{name}_socket", axis="Z", d=bore_d,
            center=(0.0, 0.0, 0.0), span=(mouth - depth, mouth),
            overshoot=(0.0, 1.0)))
        inner_dist = mouth - depth - hub_h / 2.0  # above hub center
        datum_at = [0.0, 0.0, mouth]
        if p["set_screw"] != "none":
            spec = screw_spec(p["set_screw"])
            state.bores.append(BoreFeature(
                name=f"{name}_set_screw", axis="X", d=spec["tap"],
                center=(0.0, 0.0, mouth - depth / 2.0),
                span=(0.0, outer_d / 2.0 + 1.0), overshoot=(1.0, 1.0),
                roof="teardrop"))
    else:
        axis = "X" if d in ("+x", "-x") else "Y"
        sign = 1.0 if d.startswith("+") else -1.0
        z_arm = p["z"] if p["z"] > 1e-9 else hub_h / 2.0
        if z_arm - outer_d / 2.0 < 1.0 or z_arm + outer_d / 2.0 > hub_h - 1.0:
            raise RecipeError(
                f"arm Ø{outer_d:g} at z={z_arm:g} sticks past the hub "
                f"(needs 1 mm margin inside 0..{hub_h:g})")
        arm_len = depth + wall
        start = r_hub - 0.6 if sign > 0 else -(r_hub + arm_len - 0.6)
        pin_at = (0.0, z_arm)  # off-axis coords in world order
        state.pins.append(PinFeature(
            name=f"{name}_barrel", axis=axis, at=pin_at,
            d=outer_d, z0=start, length=arm_len + 0.6,
            bore_d=bore_d))
        mouth = sign * (r_hub + arm_len)
        span = (abs(mouth) - depth, abs(mouth)) if sign > 0 else (mouth, mouth + depth)
        # bore center: the two off-axis coordinates are (0, z_arm)
        center = (0.0, 0.0, z_arm) if axis == "X" else (0.0, 0.0, z_arm)
        state.bores.append(BoreFeature(
            name=f"{name}_socket", axis=axis, d=bore_d,
            center=center, span=span,
            overshoot=(0.0, 1.0) if sign > 0 else (1.0, 0.0),
            roof="teardrop"))
        inner_dist = abs(mouth) - depth  # blind end's distance from axis
        datum_at = [mouth if axis == "X" else 0.0,
                    mouth if axis == "Y" else 0.0, z_arm]
        if p["set_screw"] != "none":
            spec = screw_spec(p["set_screw"])
            mid = sign * (abs(mouth) - depth / 2.0)
            sx, sy = (mid, 0.0) if axis == "X" else (0.0, mid)
            state.bores.append(BoreFeature(
                name=f"{name}_set_screw", axis="Z", d=spec["tap"],
                center=(sx, sy, 0.0),
                span=(z_arm, z_arm + outer_d / 2.0 + 1.0),
                overshoot=(1.0, 1.0)))

    state.datums[f"socket_{d}"] = {
        "at": datum_at, "rotate": [0.0, 0.0, 0.0]}
    state.frame[f"arm_{d}_used"] = 1.0
    state.frame[f"{name}_rod_d"] = rod_d
    state.frame[f"{name}_socket_depth"] = depth
    state.frame[f"{name}_socket_bore_d"] = bore_d
    state.frame[f"{name}_wall_eff"] = (outer_d - bore_d) / 2.0
    state.frame[f"{name}_inner_dist"] = inner_dist
    state.frame[f"{name}_dir_code"] = _DIR_CODE[d]
    state.frame["socket_count"] = f.get("socket_count", 0.0) + 1.0


_register(RecipeOpDecl(
    name="socket_arm",
    kind="feature",
    params={
        "dir": ("choice", "+x"),
        "enabled": ("count", 1),
        "rod_d": ("length", None),
        "depth": ("length", 0.0),
        "wall": ("length", 3.0),
        "clearance": ("length", 0.3),
        "fit": ("choice", "slip"),
        "set_screw": ("choice", "none"),
        "z": ("length", 0.0),
    },
    validators=(
        "form.socket_engagement_ok",
        "form.socket_bores_isolated",
        "topology.pins_present",
        "topology.bores_open",
        "topology.single_connected_solid",
    ),
    apply=_socket_arm,
    description="one blind rod socket arm on a hub (±X/±Y/+Z only — the "
                "axis-aligned kernel is the honest v1 scope)",
))

# -- tee_body ---------------------------------------------------------------------


def _tee_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Branched tube connector. tee/cross: the barbed two-spigot Z-run of
    hose_adapter_body (invoked as its own base — the sanctioned wrap
    pattern) plus one or two SMOOTH branch spigots on the X axis at the
    flange. elbow: ONE barbed bottom spigot, a capped crown above the
    flange and a single branch — the run bore is BLIND and the water
    turns the corner. Barbs live on the Z ends only — a barb is a
    revolve and the revolve axis is Z; X branches are smooth push-fits
    for a hose clip."""
    from .recipe_ops_core import RECIPE_OPS

    config = p["config"]
    if config not in ("tee", "cross", "elbow"):
        raise RecipeError(
            f"config {config!r} not in (tee, cross, elbow) — a straight "
            "run IS hose_adapter_body")
    wall = p["wall"]
    branch_d = p["branch_d"] if p["branch_d"] > 1e-9 else p["run_d_a"]
    branch_len = p["branch_len"]
    branch_bore = branch_d - 2.0 * wall
    if branch_bore < 4.0:
        raise RecipeError(
            f"branch bore {branch_bore:.1f} < 4 — branch too small for "
            "the declared wall")

    if config == "elbow":
        from .profiles_revolve import loop_from_points, sawtooth

        if state.section is not None:
            raise RecipeError("tee_body must be the (single) base op")
        d_a, sl = p["run_d_a"], p["spigot_len"]
        barb_h, n = p["barb_h"], int(p["barb_count"])
        fl_t, lip = p["flange_t"], p["flange_lip"]
        r_crest = d_a / 2.0
        r_root = r_crest - barb_h
        r_bore = r_root - wall
        if r_bore < 2.0:
            raise RecipeError(
                f"bore radius {r_bore:.2f} < 2 — spigot too small for "
                "the declared wall")
        if n < 2:
            raise RecipeError("the spigot needs at least 2 barbs")
        r_fl = r_crest + lip
        z0, z1 = sl, sl + fl_t
        # the blind run bore must swallow the whole branch junction
        bore_top = max(z1 + 2.0, (z0 + z1) / 2.0 + branch_bore / 2.0 + 2.0)
        r_crown = r_bore + wall
        top = bore_top + max(wall, 3.0)

        pts = [Pt(r_bore, 0.0)]
        sawtooth(pts, r_root, r_crest, 0.0, z0, n, toward_tip_at_v0=True)
        pts += [
            Pt(r_fl, z0), Pt(r_fl, z1),
            Pt(r_crown, z1), Pt(r_crown, top),
            Pt(0.0, top), Pt(0.0, bore_top), Pt(r_bore, bore_top),
        ]
        state.section = SectionProfile(
            name="recipe_revolve", outer=loop_from_points(pts),
            plane="XZ", width_axis="Y")
        state.kind = "profile_revolve"
        state.width = 2.0 * r_fl
        state.regions.append(Region(
            f"{op_id or 'tee'}_flange", RegionRole.MOUNTING_SURFACE,
            Box3(-r_fl, -r_fl, z0, r_fl, r_fl, z1)))
        state.frame.update(
            spigot_d_a=d_a, barb_h_a=barb_h, barb_count_a=float(n),
            spigot_len_a=sl, bore_d=2.0 * r_bore,
            flange_z0=z0, flange_z1=z1, adapter_total_l=top,
            run_capped=1.0, run_bore_top=bore_top,
        )
    else:
        RECIPE_OPS["hose_adapter_body"].apply(state, {
            "spigot_d_a": p["run_d_a"],
            "spigot_d_b": p["run_d_b"] if p["run_d_b"] > 1e-9 else p["run_d_a"],
            "spigot_len_a": p["spigot_len"], "spigot_len_b": p["spigot_len"],
            "wall": wall, "barb_h": p["barb_h"],
            "barb_count_a": p["barb_count"], "barb_count_b": p["barb_count"],
            "flange_t": p["flange_t"], "flange_lip": p["flange_lip"],
        }, op_id)
        state.frame.update(run_capped=0.0, run_bore_top=0.0)

    f = state.frame
    z_fl = (f["flange_z0"] + f["flange_z1"]) / 2.0
    if branch_d > f["flange_z1"] - f["flange_z0"] + 2.0 * p["flange_lip"] + 6.0:
        # the branch must root in the flange band, not float on a spigot
        raise RecipeError(
            f"branch Ø{branch_d:g} overwhelms the {f['flange_z1'] - f['flange_z0']:g} "
            "flange — grow flange_t/flange_lip")
    r_fl = state.width / 2.0
    name = op_id or "tee"
    main_bore_r = f["bore_d"] / 2.0

    sides = (1.0, -1.0) if config == "cross" else (1.0,)
    for sign in sides:
        tag = "px" if sign > 0 else "mx"
        start = r_fl - 1.0 if sign > 0 else -(r_fl + branch_len - 1.0)
        state.pins.append(PinFeature(
            name=f"{name}_{tag}_spigot", axis="X", at=(0.0, z_fl),
            d=branch_d, z0=start, length=branch_len + 1.0,
            bore_d=branch_bore))
        span = (0.0, r_fl + branch_len) if sign > 0 else (-(r_fl + branch_len), 0.0)
        state.bores.append(BoreFeature(
            name=f"{name}_{tag}_bore", axis="X", d=branch_bore,
            center=(0.0, 0.0, z_fl), span=span,
            overshoot=(0.0, 1.0) if sign > 0 else (1.0, 0.0),
            roof="teardrop"))
        state.datums[f"branch_{tag}"] = {
            "at": [sign * (r_fl + branch_len), 0.0, z_fl],
            "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        tee_branch_d=branch_d, tee_branch_bore_d=branch_bore,
        tee_branch_len=branch_len, tee_branch_count=float(len(sides)),
        tee_branch_inner_x=0.0, tee_run_bore_r=main_bore_r,
        tee_run_wall=wall, tee_branch_wall=(branch_d - branch_bore) / 2.0,
        tee_branch_z=z_fl,
    )


_register(RecipeOpDecl(
    name="tee_body",
    kind="base",
    params={
        "config": ("choice", "tee"),
        "run_d_a": ("length", None),
        "run_d_b": ("length", 0.0),
        "spigot_len": ("length", 28.0),
        "branch_d": ("length", 0.0),
        "branch_len": ("length", 24.0),
        "wall": ("length", 2.4),
        "barb_h": ("length", 0.8),
        "barb_count": ("count", 3),
        "flange_t": ("length", 8.0),
        "flange_lip": ("length", 3.0),
    },
    validators=(
        "form.barb_retention_ok",
        "form.tube_wall_ok",
        "form.tube_run_open",
        "form.branch_path_connected",
        "topology.pins_present",
        "topology.bores_open",
        "topology.single_connected_solid",
    ),
    apply=_tee_body,
    description="barbed tube tee/cross: hose-adapter Z-run + smooth X "
                "branch spigots rooted in the stop flange",
))

# -- angled_socket_arm (oriented kernel, first client) ------------------------------

ANGLED_ELEV_BAND = (30.0, 80.0)  # printable diagonal band, degrees above horizon


def _angled_socket_arm(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """A DIAGONAL rod socket on the hub — the oriented kernel's first
    client (AngledPin/AngledBore: cylinders along an arbitrary unit
    vector). Elevation is banded to the printable diagonal: below 30°
    the socket's ceiling flattens toward an unsupported bridge, above
    80° it is just a worse +z arm. Ports stay undeclared — interface
    frames are axis-aligned by contract; the datum is published."""
    import math

    from .part import AngledBoreFeature, AngledPinFeature

    state.require_base("angled_socket_arm")
    if int(round(p["enabled"])) == 0:
        return
    f = state.frame
    if "hub_r" not in f:
        raise RecipeError("angled_socket_arm needs a multi_socket_hub base")
    el = p["elevation_deg"]
    lo, hi = ANGLED_ELEV_BAND
    if not lo <= el <= hi:
        raise RecipeError(
            f"elevation {el:g} outside [{lo:g}, {hi:g}] — flatter needs a "
            "teardrop 90° arm, steeper IS the +z arm")
    az = math.radians(p["azimuth_deg"])
    elr = math.radians(el)
    direction = (math.cos(elr) * math.cos(az),
                 math.cos(elr) * math.sin(az),
                 math.sin(elr))
    rod_d = p["rod_d"]
    clearance = p["clearance"]
    wall = p["wall"]
    fit = p["fit"]
    if fit == "slip":
        bore_d = rod_d + clearance
    elif fit == "press":
        bore_d = rod_d - PRESS_INTERFERENCE
    else:
        raise RecipeError(f"fit {fit!r} not in (slip, press)")
    depth = p["depth"] if p["depth"] > 1e-9 else SOCKET_ENGAGE_K * rod_d
    outer_d = rod_d + 2.0 * clearance + 2.0 * wall
    r_hub, hub_h = f["hub_r"], f["hub_h"]
    z_root = p["z"] if p["z"] > 1e-9 else hub_h * 0.4
    if z_root - outer_d / 2.0 < 0.5:
        raise RecipeError(
            f"diagonal arm root at z={z_root:g} dips under the hub floor")
    arm_len = depth + wall
    name = op_id or "brace"

    start = (0.0, 0.0, z_root)
    state.pins.append(AngledPinFeature(
        name=f"{name}_barrel", start=start, direction=direction,
        d=outer_d, length=r_hub + arm_len, bore_d=bore_d))
    mouth = (direction[0] * (r_hub + arm_len),
             direction[1] * (r_hub + arm_len),
             z_root + direction[2] * (r_hub + arm_len))
    state.bores.append(AngledBoreFeature(
        name=f"{name}_socket", start=mouth,
        direction=(-direction[0], -direction[1], -direction[2]),
        d=bore_d, length=depth))
    state.datums[f"socket_{name}"] = {
        "at": [mouth[0], mouth[1], mouth[2]], "rotate": [0.0, 0.0, 0.0]}
    state.frame[f"{name}_rod_d"] = rod_d
    state.frame[f"{name}_socket_depth"] = depth
    state.frame[f"{name}_socket_bore_d"] = bore_d
    state.frame[f"{name}_wall_eff"] = (outer_d - bore_d) / 2.0
    state.frame[f"{name}_inner_dist"] = r_hub + arm_len - depth
    state.frame[f"{name}_elevation_deg"] = el
    state.frame["socket_count"] = f.get("socket_count", 0.0) + 1.0


_register(RecipeOpDecl(
    name="angled_socket_arm",
    kind="feature",
    params={
        "azimuth_deg": ("number", 0.0),
        "elevation_deg": ("number", 45.0),
        "enabled": ("count", 1),
        "rod_d": ("length", None),
        "depth": ("length", 0.0),
        "wall": ("length", 3.0),
        "clearance": ("length", 0.3),
        "fit": ("choice", "slip"),
        "z": ("length", 0.0),
    },
    validators=(
        "form.socket_engagement_ok",
        "form.socket_bores_isolated",
        "form.angled_arm_printable",
        "topology.pins_present",
        "topology.bores_open",
        "topology.single_connected_solid",
    ),
    apply=_angled_socket_arm,
    description="diagonal rod socket on the hub (oriented kernel): "
                "elevation banded to the printable 30–80°",
))

# -- shaft_coupler_body (R2.14) ----------------------------------------------------

#: Diametral clearance band for a shaft in its coupler bore — snug
#: enough for the set screw to center it, loose enough to assemble.
COUPLER_FIT_BAND = (0.15, 0.4)
COUPLER_MID_WEB_MIN = 2.5
COUPLER_ENGAGE_K = 1.2   # bore depth >= k * its shaft diameter


def _shaft_coupler_body(state: RecipeState, p: dict[str, Any], op_id: str) -> None:
    """Rigid shaft coupler: a vertical cylinder with two coaxial BLIND
    bores (a solid mid web keeps the shafts from butting) and one
    teardrop set screw per section. Torque honesty: the set screws and
    the plastic carry it — stepper-to-leadscrew duty, never certified
    beyond hobby loads."""
    if state.section is not None:
        raise RecipeError("shaft_coupler_body must be the (single) base op")
    d_a, d_b = p["shaft_d_a"], p["shaft_d_b"]
    fit = p["fit_clearance"]
    body_d = p["body_d"] if p["body_d"] > 1e-9 else max(d_a, d_b) + 8.0
    length = p["length"]
    mid_web = p["mid_web"]
    set_screw = p["set_screw"]
    lo, hi = COUPLER_FIT_BAND
    if not lo <= fit <= hi:
        raise RecipeError(
            f"fit_clearance {fit:g} outside [{lo:g}, {hi:g}]")
    if mid_web < COUPLER_MID_WEB_MIN:
        raise RecipeError(
            f"mid web {mid_web:g} < {COUPLER_MID_WEB_MIN:g} — the shafts "
            "would butt through")
    bore_a, bore_b = d_a + fit, d_b + fit
    wall_a = (body_d - bore_a) / 2.0
    wall_b = (body_d - bore_b) / 2.0
    if min(wall_a, wall_b) < 3.0:
        raise RecipeError(
            f"body Ø{body_d:g} leaves {min(wall_a, wall_b):.1f} wall "
            "around a bore (min 3)")
    depth_a = (length - mid_web) / 2.0
    depth_b = length - mid_web - depth_a
    if depth_a < COUPLER_ENGAGE_K * d_a or depth_b < COUPLER_ENGAGE_K * d_b:
        raise RecipeError(
            f"length {length:g} gives {depth_a:g}/{depth_b:g} engagement — "
            f"needs {COUPLER_ENGAGE_K:g}x each shaft "
            f"({COUPLER_ENGAGE_K * d_a:g}/{COUPLER_ENGAGE_K * d_b:g})")
    screw_spec(set_screw)  # unknown size fails loudly

    r_body = body_d / 2.0
    pts = [Pt(0.0, 0.0), Pt(r_body, 0.0), Pt(r_body, length), Pt(0.0, length)]
    state.section = SectionProfile(
        name="recipe_revolve", outer=loop_from_points(pts),
        plane="XZ", width_axis="Y")
    state.kind = "profile_revolve"
    state.width = body_d

    name = op_id or "coupler"
    state.bores.append(BoreFeature(
        name=f"{name}_bore_a", axis="Z", d=bore_a,
        center=(0.0, 0.0, 0.0), span=(0.0, depth_a), overshoot=(1.0, 0.0)))
    state.bores.append(BoreFeature(
        name=f"{name}_bore_b", axis="Z", d=bore_b,
        center=(0.0, 0.0, 0.0), span=(length - depth_b, length),
        overshoot=(0.0, 1.0)))
    spec = screw_spec(set_screw)
    for tag, z in (("a", depth_a / 2.0), ("b", length - depth_b / 2.0)):
        state.bores.append(BoreFeature(
            name=f"{name}_set_screw_{tag}", axis="X", d=spec["tap"],
            center=(0.0, 0.0, z), span=(0.0, r_body + 1.0),
            overshoot=(1.0, 1.0), roof="teardrop"))
    state.regions.append(Region(
        f"{name}_body", RegionRole.MOUNTING_SURFACE,
        Box3(-r_body, -r_body, 0.0, r_body, r_body, length)))
    state.datums["shaft_a"] = {"at": [0.0, 0.0, 0.0], "rotate": [0.0, 0.0, 0.0]}
    state.datums["shaft_b"] = {"at": [0.0, 0.0, length], "rotate": [0.0, 0.0, 0.0]}
    state.frame.update(
        coupler_shaft_a=d_a, coupler_shaft_b=d_b,
        coupler_bore_a=bore_a, coupler_bore_b=bore_b,
        coupler_depth_a=depth_a, coupler_depth_b=depth_b,
        coupler_mid_web=mid_web, coupler_wall=min(wall_a, wall_b),
        coupler_fit=fit,
    )


_register(RecipeOpDecl(
    name="shaft_coupler_body",
    kind="base",
    params={
        "shaft_d_a": ("length", None),
        "shaft_d_b": ("length", None),
        "fit_clearance": ("length", 0.25),
        "body_d": ("length", 0.0),
        "length": ("length", 25.0),
        "mid_web": ("length", 3.0),
        "set_screw": ("choice", "m4"),
    },
    validators=(
        "form.coupler_bores_ok",
        "form.coupler_torque_unverified",
        "topology.bores_open",
        "topology.pockets_present",
        "topology.single_connected_solid",
    ),
    apply=_shaft_coupler_body,
    description="rigid shaft coupler: two blind coaxial bores over a "
                "solid mid web + a teardrop set screw per section",
))
