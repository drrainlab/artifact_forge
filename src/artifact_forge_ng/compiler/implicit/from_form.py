"""PartForm -> ImplicitRecipe (Bio-4M stages A+B integration).

Compiles the Form IR of a constant-section part carrying an organic skin
into the analytic SDF recipe, plus the probe points the export stage
samples on the ANALYTIC SDF (assembly-order bugs and frame-sign bugs die
here, not in a slicer).

Two canvas mappings:

* **planar** — horizontal/tilted panels (the demo plate): full
  organic_base_shell (canvas pad + boss growth + asymmetry noise),
  through-cut windows, mounting-plane keep_in;
* **profile_surface** — the developable section-sweep (the organic clamp,
  stage B): rib capsules/node spheres come from
  ``compiler.exoskeleton.exoskeleton_capsule_chains`` (the ONE geometry
  source shared with the BRep twin), windows are RECESSES carved in
  per-window tangent frames, keep_in clips at the mating plane, and the
  base envelope (canvas pad + asymmetry noise) is honestly SKIPPED —
  curved-canvas inflation is Bio-5 scope; boss growth (world-space
  spheres) stays.

A skin request is honored graph-less too: a form with organic windows but
no exoskeleton (the clamp's upper half) gets shell + lipped recesses.

Honest refusals: anything this stage cannot represent exactly raises
:class:`UnsupportedFormForImplicit` — the pipeline turns it into a loud
PipelineFailure. There is NO silent BRep fallback under a skin request.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

import numpy as np

from ...core.fasteners import hole_cut_dims
from ...form.part import FieldFeature, HoleFeature, PartForm
from ...form.regions import Circle2D, Rect2D, Region2D
from .recipe import (
    Blob,
    BodyProfile,
    BoxCut,
    BoxSolid,
    CanvasPad,
    CanvasRegion,
    Capsule,
    CylinderCut,
    FrustumCutZ,
    ImplicitRecipe,
    KeepInHalfSpace,
    Mask2D,
    PrismCut,
    RoundedPlate,
    Sphere,
    WindowPrism,
)
from .sdf import Frame, Profile2D, planar_frame


class ImplicitSkinError(Exception):
    """The implicit skin engine cannot honor the request."""


class UnsupportedFormForImplicit(ImplicitSkinError):
    """This form family is outside the implicit engine's honest scope."""


#: Never emit a capsule/sphere thinner than this — mirrors
#: compiler/exoskeleton.MIN_SOLID_R (kept in sync via the chains source).
MIN_SOLID_R = 0.4

#: Fastener boss growth radius = head radius + this (plan: r = head_r + 3).
BOSS_EXTRA_R = 3.0

#: Organic windows shallower than this read as engraving, not shadow
#: (quality.window_shadow_present).
INNER_SHADOW_DEPTH_MIN = 2.5

#: How far a recess prism reaches OUTSIDE a curved surface: enough to slice
#: through any boss overhang shading a window rim plus the lip radius, but
#: short — a long outward prism near a concave fillet would gouge the
#: neighbouring wall.
CURVED_PRISM_ABOVE = 4.5


@dataclass(frozen=True)
class NoiseSpec:
    """asymmetry_noise — deliberately conservative (review #2): a few
    seeded LOW-FREQUENCY blobs in the safe canvas, tiny amplitude, hard
    displacement cap, mandatory clearance to every keepout, never near
    interfaces. Fully deterministic from the seed."""

    count: int = 4
    amplitude: float = 1.0
    max_surface_displacement: float = 1.5
    min_clearance_to_keepouts: float = 3.0
    forbidden_near_interfaces: bool = True
    #: blob radius range; the effective max is additionally capped so a
    #: blob never reaches past the panel's far (mounting) face.
    r_min: float = 2.5
    r_max: float = 9.0


@dataclass(frozen=True)
class ProbePoint:
    xyz: tuple[float, float, float]
    expect: str  # "solid" | "void"
    label: str


@dataclass(frozen=True)
class SkinProbes:
    """Analytic-SDF sample points, grouped by the finding they feed."""

    fidelity: tuple[ProbePoint, ...]
    boss: tuple[ProbePoint, ...]
    clearance: tuple[ProbePoint, ...]


@dataclass(frozen=True)
class _SkinContext:
    """The canvas the skin grows on — from the ExoskeletonIR when present,
    else from the graph-less organic FieldFeature (bone windows)."""

    mapping: str  # "planar" | "profile_surface"
    window: Rect2D | None
    masks: tuple[Region2D, ...]
    depth: float
    seed: int
    min_rib_d: float
    min_ligament: float
    origin: tuple[float, float, float] | None
    tilt_deg: float
    plane_z: float


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _poly_centroid(poly: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    area2 = 0.0
    cu = 0.0
    cv = 0.0
    for (x0, y0), (x1, y1) in zip(poly, tuple(poly[1:]) + (poly[0],)):
        cr = x0 * y1 - x1 * y0
        area2 += cr
        cu += (x0 + x1) * cr
        cv += (y0 + y1) * cr
    if abs(area2) < 1e-9:
        n = len(poly)
        return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)
    return (cu / (3.0 * area2), cv / (3.0 * area2))


def _masks_2d(masks: tuple[Region2D, ...], extra_inflate: float) -> tuple[Mask2D, ...]:
    out: list[Mask2D] = []
    for region in masks:
        s = region.shape
        inflate = float(region.clearance) + extra_inflate
        if isinstance(s, Circle2D):
            out.append(Mask2D("circle", s.center.u, s.center.v, s.r, 0.0, inflate))
        elif isinstance(s, Rect2D):
            out.append(Mask2D("rect", s.u0, s.v0, s.u1, s.v1, inflate))
    return tuple(out)


def _hex_vertices(cell: float) -> tuple[tuple[float, float], ...]:
    """Flat-to-flat hexagon vertices — EXACTLY compiler/fields.cut_field."""
    r_hex = cell / math.sqrt(3.0)
    return tuple(
        (r_hex * math.cos(math.radians(30 + 60 * k)),
         r_hex * math.sin(math.radians(30 + 60 * k)))
        for k in range(6)
    )


def _organic_fields(form: PartForm) -> list[FieldFeature]:
    return [f for f in form.fields if f.pattern == "organic"]


def _refuse_unsupported(form: PartForm) -> None:
    if form.kind != "section_extrude":
        raise UnsupportedFormForImplicit(
            f"kind {form.kind!r}: the implicit skin engine covers planar "
            "constant-section extrusions only; profile_revolve/"
            "section_sweep bodies are out of implicit scope"
        )
    if form.pins:
        raise UnsupportedFormForImplicit(
            f"{len(form.pins)} pin feature(s): press-fit pins are not "
            "represented in the implicit recipe yet"
        )
    if form.lofts:
        raise UnsupportedFormForImplicit(
            f"{len(form.lofts)} loft feature(s): lofted arms are not "
            "represented in the implicit recipe yet"
        )
    for f in form.fields:
        if f.mapping == "cylindrical":
            raise UnsupportedFormForImplicit(
                "cylindrical field mapping: cylinder-wall skins are Bio-5 scope"
            )
        if f.mapping == "profile_surface" and f.surface is None:
            raise UnsupportedFormForImplicit(
                "profile_surface field without its surface map — broken IR"
            )
    if form.exoskeleton is None and not _organic_fields(form):
        raise UnsupportedFormForImplicit(
            "the form carries no exoskeleton and no organic windows — "
            "nothing to skin (add apply_biomorphic_exoskeleton / "
            "add_bone_windows or drop style.skin)"
        )


def _skin_context(form: PartForm) -> _SkinContext:
    ir = form.exoskeleton
    if ir is not None:
        return _SkinContext(
            mapping="profile_surface" if ir.mapping == "profile_surface" else "planar",
            window=ir.window,
            masks=ir.masks,
            depth=float(ir.depth),
            seed=int(ir.seed),
            min_rib_d=float(ir.min_rib_d),
            min_ligament=float(ir.min_ligament),
            origin=ir.origin,
            tilt_deg=ir.tilt_deg,
            plane_z=ir.plane_z,
        )
    f0 = _organic_fields(form)[0]  # guaranteed by _refuse_unsupported
    return _SkinContext(
        mapping="profile_surface" if f0.mapping == "profile_surface" else "planar",
        window=f0.window,
        masks=tuple(f0.keepouts),
        depth=float(f0.depth),
        seed=zlib.crc32(form.name.encode()) & 0xFFFF,
        min_rib_d=0.0,
        min_ligament=float(f0.min_ligament),
        origin=f0.origin,
        tilt_deg=f0.tilt_deg,
        plane_z=f0.plane_z,
    )


# ---------------------------------------------------------------------------
# skin geometry (the ONE source shared with the BRep twin)
# ---------------------------------------------------------------------------


def _skin_geometry(form: PartForm) -> tuple[tuple[Capsule, ...], tuple[Sphere, ...]]:
    """Rib capsules + node spheres from
    ``compiler.exoskeleton.exoskeleton_capsule_chains`` — the geometry
    source the BRep twin materializes from, so the two paths cannot drift
    (the bio-4m-integration seam, now closed). Planar chains are single
    chords (byte-identical to the stage-A path); profile_surface chains
    are polylines hugging the developable surface — each chord becomes one
    capsule, and consecutive chords share their knots, so the smooth union
    bridges them seamlessly."""
    if form.exoskeleton is None:
        return (), ()
    # lazy: compiler/exoskeleton imports cadquery at module level; the
    # implicit package stays cadquery-free at import time.
    from ..exoskeleton import exoskeleton_capsule_chains

    chains, blends = exoskeleton_capsule_chains(form)
    capsules: list[Capsule] = []
    for ch in chains:
        for a3, b3 in zip(ch.polyline, ch.polyline[1:]):
            if math.dist(a3, b3) < 1e-9:
                continue
            capsules.append(Capsule(a3, b3, max(float(ch.radius), MIN_SOLID_R)))
    spheres = tuple(Sphere(nb.center, float(nb.radius)) for nb in blends)
    return tuple(capsules), spheres


def _window_prisms(
    form: PartForm, above_reach: float, k_lip: float
) -> tuple[tuple[WindowPrism, ...], bool]:
    """Organic windows as lipped prisms. Planar fields cut THROUGH the
    panel (depth + overshoot); profile_surface fields are RECESSES carved
    in the tangent frame of each polygon's centroid (a = the surface
    tangent dP/ds, b = the extrusion +X, n = the inward normal) with the
    floor at EXACTLY ``field.depth`` — the same intent the BRep recess
    cutter (compiler/fields._cut_profile_surface_field) reads."""
    prisms: list[WindowPrism] = []
    through = True
    for f in _organic_fields(form):
        if f.mapping == "profile_surface" and f.surface is not None:
            through = False
            surface = f.surface
            eps = 1e-3
            for poly in f.polygons:
                if len(poly) < 3:
                    continue
                sc, xc = _poly_centroid(poly)
                _u, _v, nu, nv = surface.sample(sc)
                p0 = surface.to_world(sc, xc, 0.0)
                ps = surface.to_world(sc + eps, xc, 0.0)
                s_len = math.dist(p0, ps)
                if s_len < 1e-9:
                    continue
                s_dir = tuple((b - a) / s_len for a, b in zip(p0, ps))
                frame = Frame(
                    origin=p0,
                    a_axis=s_dir,
                    b_axis=(1.0, 0.0, 0.0),
                    n_axis=(0.0, -nu, -nv),
                )
                local = tuple((p[0] - sc, p[1] - xc) for p in poly)
                prisms.append(WindowPrism(
                    local, frame, -(CURVED_PRISM_ABOVE + k_lip), f.depth
                ))
        else:
            frame = planar_frame(f.origin, f.tilt_deg, f.plane_z)
            for poly in f.polygons:
                prisms.append(WindowPrism(
                    tuple(poly), frame, -above_reach, f.depth + 1.0
                ))
    return tuple(prisms), through


# ---------------------------------------------------------------------------
# hard cuts
# ---------------------------------------------------------------------------


def _hole_cuts(hole: HoleFeature, above_reach: float) -> list[object]:
    """One fastener hole as EXACT hard cuts, dimensioned by the same
    ``hole_cut_dims`` the BRep cutter uses. Includes the driver-access
    cylinder past the head seat — boss growth may swallow the column, but
    the fastener access is carved back out LAST, by law."""
    dims = hole_cut_dims(hole.screw, hole.through, hole.head_style)
    x, y, z_top = hole.at
    cuts: list[object] = [
        CylinderCut(
            "Z", (x, y, 0.0), dims["bore_d"] / 2.0,
            z_top - hole.through - 1.0, z_top + above_reach,
        )
    ]
    if not hole.countersink:
        return cuts
    if hole.head_style == "cylinder":
        cb = dims["cb_depth"]
        if hole.countersink_face == "bottom":
            z_seat = z_top - hole.through
            cuts.append(CylinderCut(
                "Z", (x, y, 0.0), dims["seat_r"],
                z_seat - above_reach, z_seat + cb,
            ))
        else:
            cuts.append(CylinderCut(
                "Z", (x, y, 0.0), dims["seat_r"],
                z_top - cb, z_top + above_reach,
            ))
        return cuts
    cs = dims["cs_depth"]
    if hole.countersink_face == "bottom":
        z_seat = z_top - hole.through
        cuts.append(FrustumCutZ(x, y, z_seat, z_seat + cs, dims["seat_r"], dims["cs_tip_r"]))
        # driver access: the column below the seat stays open through any
        # grown boss material on the underside.
        cuts.append(CylinderCut(
            "Z", (x, y, 0.0), dims["seat_r"], z_seat - above_reach, z_seat,
        ))
    else:
        cuts.append(FrustumCutZ(x, y, z_top - cs, z_top, dims["cs_tip_r"], dims["seat_r"]))
        # driver access: the column above the seat stays open through any
        # grown boss/pad material.
        cuts.append(CylinderCut(
            "Z", (x, y, 0.0), dims["seat_r"], z_top, z_top + above_reach,
        ))
    return cuts


def _field_cuts(f: FieldFeature, above_reach: float) -> list[object]:
    """Non-organic fields stay CRISP — hard prism/cylinder cuts with the
    exact same depths the BRep cutter uses; only organic windows get lips."""
    if f.mapping == "profile_surface":
        raise UnsupportedFormForImplicit(
            "crisp (non-organic) fields on a profile_surface canvas are "
            "not represented in the implicit recipe yet"
        )
    if f.origin is not None and abs(f.tilt_deg) > 1e-9:
        raise UnsupportedFormForImplicit(
            "tilted non-organic field: oriented crisp fields are not "
            "represented in the implicit recipe yet"
        )
    frame = planar_frame(f.origin, f.tilt_deg, f.plane_z)
    depth = f.depth + (2.0 if f.depth > 2.0 else 1.0)  # mirror compiler/fields
    cuts: list[object] = []
    if f.centers and f.pattern == "round":
        for cx, cy in f.centers:
            w = frame.to_world(cx, cy, 0.0)
            cuts.append(CylinderCut(
                "Z", (w[0], w[1], 0.0), f.cell / 2.0,
                w[2] - depth, w[2] + above_reach,
            ))
    elif f.centers:
        hexagon = _hex_vertices(f.cell)
        for cx, cy in f.centers:
            poly = tuple((cx + vx, cy + vy) for vx, vy in hexagon)
            cuts.append(PrismCut(poly, frame, -above_reach, depth))
    for poly in f.polygons:
        cuts.append(PrismCut(tuple(poly), frame, -above_reach, depth))
    return cuts


# ---------------------------------------------------------------------------
# asymmetry noise (planar canvases only)
# ---------------------------------------------------------------------------


def _noise_blobs(
    canvas: CanvasRegion, seed: int, spec: NoiseSpec, panel: Frame, depth: float
) -> tuple[Blob, ...]:
    """Seeded low-frequency blobs in the safe canvas. Placement is a
    deterministic candidate scan: a candidate is accepted only when its
    whole protruding cap keeps ``min_clearance_to_keepouts`` from every
    mask/window edge (masks ARE the interfaces —
    ``forbidden_near_interfaces`` is structural here, not a runtime flag).
    Radii are capped so no blob reaches past the panel's far face."""
    a0, b0, a1, b1 = canvas.window
    rng = np.random.default_rng(seed ^ 0xB10B)
    blobs: list[Blob] = []
    amplitude = min(spec.amplitude, spec.max_surface_displacement - 0.2)
    if amplitude <= 0.05:
        return ()
    # center sits (r - amplitude) into the material; the deepest sphere
    # point is 2r - amplitude — keep it inside the panel thickness.
    r_max = min(spec.r_max, (depth + amplitude) / 2.0 - 0.1)
    if r_max <= spec.r_min:
        return ()
    for _ in range(60):
        if len(blobs) >= spec.count:
            break
        a = float(rng.uniform(a0, a1))
        b = float(rng.uniform(b0, b1))
        r = float(rng.uniform(spec.r_min, r_max))
        # lateral reach of the protruding cap
        cap_r = math.sqrt(max(amplitude * (2.0 * r - amplitude), 0.0))
        g = float(canvas.footprint_signed(np.asarray([a]), np.asarray([b]))[0])
        if g > -(spec.min_clearance_to_keepouts + cap_r):
            continue
        # center sits (r - amplitude) below the panel surface: the blob
        # pokes exactly `amplitude` above it (n runs INTO the material).
        center = panel.to_world(a, b, r - amplitude)
        blobs.append(Blob(center, r))
    return tuple(blobs)


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------


def _fidelity_probes(form: PartForm) -> tuple[ProbePoint, ...]:
    pts: list[ProbePoint] = []
    ir = form.exoskeleton
    if ir is not None:
        graph = ir.graph
        radii = graph.edge_radius or tuple(ir.min_rib_d / 2.0 for _ in graph.edges)
        for (i, j), r in zip(graph.edges, radii):
            na, nb = graph.nodes[i], graph.nodes[j]
            mid_a = (na[0] + nb[0]) / 2.0
            mid_b = (na[1] + nb[1]) / 2.0
            rr = max(float(r), MIN_SOLID_R)
            # the local edge midpoint maps to a polyline KNOT (chains use
            # even chord counts), so this sits ON the capsule, proud side.
            pts.append(ProbePoint(
                ir.local_to_world(mid_a, mid_b, -rr / 2.0),
                "solid", f"capsule[{i}-{j}] proud midpoint",
            ))
    for f_idx, f in enumerate(_organic_fields(form)):
        for w_idx, poly in enumerate(f.polygons):
            ca, cb = _poly_centroid(poly)
            pts.append(ProbePoint(
                f.local_to_world(ca, cb, f.depth / 2.0),
                "void", f"window[{f_idx}.{w_idx}] centroid mid-depth",
            ))
    for h_idx, hole in enumerate(form.holes):
        dims = hole_cut_dims(hole.screw, hole.through, hole.head_style)
        x, y, z_top = hole.at
        bore_r = dims["bore_d"] / 2.0
        for frac in (0.25, 0.5, 0.75):
            pts.append(ProbePoint(
                (x, y, z_top - hole.through * frac),
                "void", f"hole[{h_idx}] axis at {frac:g} depth",
            ))
        # The wall ring must sit in the PLAIN bore band — clear of the
        # counterbore/countersink pocket (on the clamp wings cb_depth is
        # through/2, so a naive mid-through ring lands exactly on the seat
        # floor and reads void).
        top_clear = bot_clear = 0.0
        if hole.countersink:
            d_seat = (dims["cb_depth"] if hole.head_style == "cylinder"
                      else dims["cs_depth"])
            if hole.countersink_face == "top":
                top_clear = d_seat
            else:
                bot_clear = d_seat
        z_lo = z_top - hole.through + bot_clear + 0.8
        z_hi = z_top - top_clear - 0.8
        if z_hi > z_lo:
            ring_r = bore_r + 0.3
            z_ring = (z_lo + z_hi) / 2.0
            for k in range(8):
                ang = 2.0 * math.pi * k / 8.0
                pts.append(ProbePoint(
                    (x + ring_r * math.cos(ang), y + ring_r * math.sin(ang),
                     z_ring),
                    "solid", f"hole[{h_idx}] wall ring at bore_r+0.3",
                ))
    return tuple(pts)


def _boss_probes(
    form: PartForm, above_reach: float, shell_on: bool
) -> tuple[ProbePoint, ...]:
    pts: list[ProbePoint] = []
    for h_idx, hole in enumerate(form.holes):
        dims = hole_cut_dims(hole.screw, hole.through, hole.head_style)
        x, y, z_top = hole.at
        bore_r = dims["bore_d"] / 2.0
        seat_r = dims["seat_r"]
        if hole.countersink:
            top_seat = hole.countersink_face == "top"
            z_seat = z_top if top_seat else z_top - hole.through
            out = 1.0 if top_seat else -1.0  # away from the material
            if hole.head_style == "cylinder":
                d = dims["cb_depth"] / 2.0
                ring = (bore_r + seat_r) / 2.0
            else:
                d = dims["cs_depth"] * 0.3
                r_cone = seat_r - (seat_r - dims["cs_tip_r"]) * (d / dims["cs_depth"])
                ring = max(bore_r + 0.15, min(r_cone - 0.2, seat_r - 0.3))
            for k in range(4):
                ang = 2.0 * math.pi * k / 4.0
                pts.append(ProbePoint(
                    (x + ring * math.cos(ang), y + ring * math.sin(ang),
                     z_seat - out * d),
                    "void", f"hole[{h_idx}] head-seat ring",
                ))
            pts.append(ProbePoint(
                (x, y, z_seat + out * 1.5),
                "void", f"hole[{h_idx}] driver access near",
            ))
            pts.append(ProbePoint(
                (x, y, z_seat + out * 0.6 * above_reach),
                "void", f"hole[{h_idx}] driver access far",
            ))
            pts.append(ProbePoint(
                (x + seat_r - 0.3, y, z_seat + out * 1.5),
                "void", f"hole[{h_idx}] driver access rim",
            ))
            if shell_on:
                annulus_r = seat_r + 1.2
                pts.append(ProbePoint(
                    (x + annulus_r, y, z_seat + out * 0.8),
                    "solid", f"hole[{h_idx}] grown boss annulus",
                ))
                pts.append(ProbePoint(
                    (x - annulus_r, y, z_seat + out * 0.8),
                    "solid", f"hole[{h_idx}] grown boss annulus",
                ))
        pts.append(ProbePoint(
            (x, y, z_top - hole.through / 2.0),
            "void", f"hole[{h_idx}] bore open after hard cut",
        ))
    return tuple(pts)


def _clearance_probes(
    form: PartForm,
    ctx: _SkinContext,
    canvas: CanvasRegion | None,
    mate_plane: tuple[float, float] | None,
) -> tuple[ProbePoint, ...]:
    """Interface clearances on the analytic SDF. Clamp halves: a grid of
    samples just PAST the mating plane over the whole section footprint —
    the skin must never cross it (keep_in enforces; this probe verifies,
    feeding manufacturing.skin_assembly_clearance). Planar panels: the
    mounting face stays flat and nothing spills past the section outline."""
    from ...form.section import plane_mapping

    pts: list[ProbePoint] = []
    lo, hi = form.section.outer.bbox()
    if mate_plane is not None:
        mate_z, side = mate_plane
        z = mate_z + side * 0.3
        for fu in (0.1, 0.3, 0.5, 0.7, 0.9):
            for fx in (0.2, 0.5, 0.8):
                u = lo.u + (hi.u - lo.u) * fu
                x = form.width * fx
                pts.append(ProbePoint(
                    (x, u, z), "void",
                    "skin never crosses the mating plane",
                ))
        return tuple(pts)
    if canvas is None or ctx.window is None:
        return ()
    frame = planar_frame(ctx.origin, ctx.tilt_deg, ctx.plane_z)
    a0, b0 = ctx.window.u0, ctx.window.v0
    a1, b1 = ctx.window.u1, ctx.window.v1
    bottom_n = ctx.depth + 0.3  # just past the panel's far face
    for fa in (0.15, 0.5, 0.85):
        for fb in (0.2, 0.5, 0.8):
            a = a0 + (a1 - a0) * fa
            b = b0 + (b1 - b0) * fb
            pts.append(ProbePoint(
                frame.to_world(a, b, bottom_n),
                "void", "mounting face stays flat (below panel bottom)",
            ))
    m = plane_mapping(form.section.plane, form.section.width_axis)
    w_mid = form.width / 2.0
    for u, v in (
        (lo.u - 1.5, (lo.v + hi.v) / 2.0),
        (hi.u + 1.5, (lo.v + hi.v) / 2.0),
        ((lo.u + hi.u) / 2.0, lo.v - 1.5),
        ((lo.u + hi.u) / 2.0, hi.v + 1.5),
    ):
        pts.append(ProbePoint(
            m(u, v, w_mid), "void", "no skin spill past the section outline",
        ))
    return tuple(pts)


# ---------------------------------------------------------------------------
# the compiler
# ---------------------------------------------------------------------------


def recipe_from_form(
    form: PartForm,
) -> tuple[ImplicitRecipe, SkinProbes, dict[str, object]]:
    """PartForm -> (recipe, analytic probe points, exports meta)."""
    _refuse_unsupported(form)
    ctx = _skin_context(form)
    curved = ctx.mapping == "profile_surface"
    style = form.style

    k_blend = float(style.skin_k_blend)
    k_weld = float(style.skin_k_weld)
    k_lip = float(style.skin_k_lip)
    base_inflation = float(style.base_inflation)
    shell_on = base_inflation > 1e-9
    shell_notes: list[str] = []

    # -- skin geometry (shared with the BRep twin) -----------------------------
    capsules, spheres = _skin_geometry(form)

    # -- how far material can grow above the surface ---------------------------
    max_rib_r = max([c.r for c in capsules], default=0.0)
    max_node_r = max([s.r for s in spheres], default=0.0)
    countersunk = [h for h in form.holes if h.countersink]
    max_head_r = 0.0
    for hole in countersunk:
        max_head_r = max(max_head_r, hole_cut_dims(hole.screw, hole.through)["head_r"])
    boss_r = (max_head_r + BOSS_EXTRA_R) if (shell_on and countersunk) else 0.0
    noise = NoiseSpec()
    pad_h = (base_inflation + noise.amplitude) if (shell_on and not curved) else 0.0
    proud = max(max_rib_r, max_node_r, boss_r, pad_h)
    above_reach = proud + k_lip + 2.0

    # -- body ------------------------------------------------------------------
    lo, hi = form.section.outer.bbox()
    body: list[object] = [
        BodyProfile(
            Profile2D(form.section.outer),
            form.section.plane,
            form.section.width_axis,
            0.0,
            form.width,
            (lo.u, lo.v, hi.u, hi.v),
        )
    ]
    for plate in form.plates:
        body.append(RoundedPlate(
            plate.x0, plate.y0, plate.x1, plate.y1,
            plate.corner_r, plate.z_bottom, plate.z_top,
        ))
    for rib in form.ribs:
        b = rib.box
        body.append(BoxSolid((b.x0, b.y0, b.z0), (b.x1, b.y1, b.z1)))

    # -- organic_base_shell ------------------------------------------------------
    panel = None if curved else planar_frame(ctx.origin, ctx.tilt_deg, ctx.plane_z)
    metric_canvas: CanvasRegion | None = None
    if panel is not None and ctx.window is not None:
        win = ctx.window
        metric_canvas = CanvasRegion(
            panel, (win.u0, win.v0, win.u1, win.v1), _masks_2d(ctx.masks, 0.0)
        )
    shell: list[object] = []
    if shell_on:
        if curved:
            shell_notes.append(
                "organic_base_shell canvas pad + asymmetry noise on curved "
                "profile_surface canvases: no implementation yet (Bio-5 "
                "scope) — boss growth applied, base_inflation ignored"
            )
        elif metric_canvas is not None:
            # pad masks widen by the weld radius so smin bulges die out
            # before any interface edge (preserve_interfaces).
            win = ctx.window
            pad_canvas = CanvasRegion(
                panel, (win.u0, win.v0, win.u1, win.v1),
                _masks_2d(ctx.masks, k_weld),
            )
            falloff = max(6.0, min(win.width, win.height) / 4.0)
            shell.append(CanvasPad(pad_canvas, base_inflation, falloff, root_depth=1.0))
        for hole in countersunk:
            dims = hole_cut_dims(hole.screw, hole.through, hole.head_style)
            x, y, z_top = hole.at
            z_seat = z_top if hole.countersink_face == "top" else z_top - hole.through
            # boss grows ON the surface around the fastener column at its
            # head-seat face; the hard bore/access cuts reopen it, by law.
            shell.append(Blob((x, y, z_seat), dims["head_r"] + BOSS_EXTRA_R))
        if shell and isinstance(shell[0], CanvasPad):
            shell.extend(_noise_blobs(
                shell[0].canvas, ctx.seed, noise, panel, ctx.depth
            ))

    # -- organic windows ----------------------------------------------------------
    prisms, through = _window_prisms(form, above_reach, k_lip)

    # -- hard cuts LAST ------------------------------------------------------------
    cuts: list[object] = []
    for hole in form.holes:
        cuts.extend(_hole_cuts(hole, above_reach))
    for bore in form.bores:
        lo_b = bore.span[0] - bore.overshoot[0]
        hi_b = bore.span[1] + bore.overshoot[1]
        cuts.append(CylinderCut(bore.axis, bore.center, bore.d / 2.0, lo_b, hi_b))
    for cutbox in form.cutboxes:
        b = cutbox.box
        cuts.append(BoxCut((b.x0, b.y0, b.z0), (b.x1, b.y1, b.z1)))
    for f in form.fields:
        if f.pattern == "organic":
            continue  # organic windows already carved with lips
        cuts.extend(_field_cuts(f, above_reach))

    # -- keep_in ---------------------------------------------------------------------
    body_lo = tuple(min(term.bounds()[0][i] for term in body) for i in range(3))
    body_hi = tuple(max(term.bounds()[1][i] for term in body) for i in range(3))
    keep_in: tuple[object, ...] = ()
    mate_plane: tuple[float, float] | None = None
    mate_z = form.frame.get("mate_z")
    if mate_z is not None:
        # clamp half: the skin must NEVER cross the mating plane (the
        # assembled pair's compression gap depends on it). The mate face
        # bounds the body's top (lower half) or bottom (upper half, modeled
        # mate-face-down) — clip on whichever side it sits.
        side = 1.0 if abs(mate_z - body_hi[2]) <= abs(mate_z - body_lo[2]) else -1.0
        keep_in = (KeepInHalfSpace((0.0, 0.0, float(mate_z)), (0.0, 0.0, side)),)
        mate_plane = (float(mate_z), side)
    elif ctx.origin is None and not curved:
        # planar panel: the mounting-plane analog — organic material never
        # crosses the panel's far face when that face is a FREE body face.
        bottom_z = ctx.plane_z - ctx.depth
        if abs(bottom_z - body_lo[2]) < 1e-6:
            keep_in = (KeepInHalfSpace((0.0, 0.0, bottom_z), (0.0, 0.0, -1.0)),)

    recipe = ImplicitRecipe(
        body=tuple(body),
        shell=tuple(shell),
        skin_capsules=capsules,
        skin_spheres=spheres,
        window_prisms=prisms,
        hard_cuts=tuple(cuts),
        keep_in=keep_in,
        k_blend=k_blend,
        k_weld=k_weld,
        k_lip=k_lip,
        canvas=metric_canvas,
    )

    probes = SkinProbes(
        fidelity=_fidelity_probes(form),
        boss=_boss_probes(form, above_reach, shell_on),
        clearance=_clearance_probes(form, ctx, metric_canvas, mate_plane),
    )

    window_depths = [f.depth for f in _organic_fields(form)]
    meta: dict[str, object] = {
        "mapping": ctx.mapping,
        "k_blend": round(k_blend, 4),
        "k_weld": round(k_weld, 4),
        "k_lip": round(k_lip, 4),
        "base_inflation": round(base_inflation, 4),
        "shell_terms": len(shell),
        "skin_capsules": len(capsules),
        "skin_spheres": len(spheres),
        "window_prisms": len(prisms),
        "hard_cuts": len(cuts),
        "min_rib_d": ctx.min_rib_d,
        "min_ligament": ctx.min_ligament,
        "window_depth_min": min(window_depths, default=0.0),
        "shell_notes": shell_notes,
        "organic_windows": {
            "mode": "through" if through else "recessed",
            "through_cuts": bool(through),
            "reason": (
                "windows pierce the full panel thickness — legal on a plate"
                if through
                else "recessed to protect the saddle/channel behind the "
                "curved shell — a through-cut would breach them"
            ),
        },
    }
    return recipe, probes, meta
