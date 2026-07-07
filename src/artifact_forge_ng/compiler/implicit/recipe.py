"""ImplicitRecipe — the analytic SDF assembly of one part.

ASSEMBLY ORDER IS LAW (violating it is exactly the bug class the fidelity
probes exist to catch):

1. **body** — hard union (min) of the exact functional solids
   (extruded section, plates, rib boxes);
2. **organic_base_shell** — the "grown, not decorated" layer: canvas pad
   (additive prism over the window minus masks, thickness falling off to
   zero toward every mask edge — interfaces never inflate), boss growth
   (spheres around fastener columns), asymmetry noise (few seeded
   low-frequency blobs in the safe canvas); blended among themselves with
   ``k_blend``, welded onto the body with ``k_weld`` (soften_rect_edges —
   the weld blend swallows the canvas' rectangular rims);
3. **skin** — rib capsules + node spheres smooth-unioned with ``k_blend``,
   then welded onto body+shell with ``k_weld``;
4. **window lips** — organic window prisms subtracted with ``smax``
   (``k_lip`` rounds the lips);
5. **HARD CUTS LAST** — fastener bores, countersink frusta, driver-access
   cylinders, bores, box cuts, non-organic field prisms are EXACT: no blob
   may narrow a functional hole, ever;
6. **keep_in** — hard intersection clips (a clamp half's mate plane).

Everything is a frozen dataclass of plain floats/tuples — a pure function
of the Form IR, so two runs produce byte-identical grids.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .sdf import (
    Frame,
    Profile2D,
    sd_box,
    sd_capsule,
    sd_cylinder_axis,
    sd_extruded_profile,
    sd_frustum_z,
    sd_prism_polygon,
    sd_rounded_rect_prism_z,
    sd_sphere,
    smax,
    smin,
)

Vec3 = tuple[float, float, float]
Poly2 = tuple[tuple[float, float], ...]


# ---------------------------------------------------------------------------
# body terms (hard union)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BodyProfile:
    """The extruded section — plane/width per ``plane_mapping``."""

    profile: Profile2D
    plane: str
    width_axis: str
    w0: float
    w1: float
    #: section-plane bbox (u0, v0, u1, v1) for bounds()
    uv_bbox: tuple[float, float, float, float]

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_extruded_profile(P, self.profile, self.plane, self.width_axis, self.w0, self.w1)

    def bounds(self) -> tuple[Vec3, Vec3]:
        u0, v0, u1, v1 = self.uv_bbox
        lo_uvw, hi_uvw = (u0, v0, self.w0), (u1, v1, self.w1)
        from ...form.section import plane_mapping

        m = plane_mapping(self.plane, self.width_axis)
        a = m(*lo_uvw)
        b = m(*hi_uvw)
        return (
            (min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2])),
            (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2])),
        )


@dataclass(frozen=True)
class RoundedPlate:
    x0: float
    y0: float
    x1: float
    y1: float
    corner_r: float
    z0: float
    z1: float

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_rounded_rect_prism_z(
            P, self.x0, self.y0, self.x1, self.y1, self.corner_r, self.z0, self.z1
        )

    def bounds(self) -> tuple[Vec3, Vec3]:
        return (self.x0, self.y0, self.z0), (self.x1, self.y1, self.z1)


@dataclass(frozen=True)
class BoxSolid:
    lo: Vec3
    hi: Vec3

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_box(P, self.lo, self.hi)

    def bounds(self) -> tuple[Vec3, Vec3]:
        return self.lo, self.hi


# ---------------------------------------------------------------------------
# organic_base_shell terms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Mask2D:
    """A pad-footprint exclusion in local (a, b): a keepout the canvas pad
    must fall off to zero toward. ``inflate`` widens it (region clearance
    plus the weld-blend margin, so smin bulges never reach an interface)."""

    kind: str  # "rect" | "circle"
    p0: float  # rect: u0 | circle: cu
    p1: float  # rect: v0 | circle: cv
    p2: float  # rect: u1 | circle: r
    p3: float  # rect: v1 | circle: unused
    inflate: float = 0.0

    def signed(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        if self.kind == "circle":
            return np.hypot(a - self.p0, b - self.p1) - (self.p2 + self.inflate)
        qa = np.maximum(self.p0 - a, a - self.p2)
        qb = np.maximum(self.p1 - b, b - self.p3)
        outside = np.hypot(np.maximum(qa, 0.0), np.maximum(qb, 0.0))
        inside = np.minimum(np.maximum(qa, qb), 0.0)
        return outside + inside - self.inflate


@dataclass(frozen=True)
class CanvasRegion:
    """The skin canvas footprint: window rect minus masks, in a planar
    frame. Shared by the pad term, the noise placement, the rectangularity
    metric and the clearance sampling — one region, one definition."""

    frame: Frame
    window: tuple[float, float, float, float]  # (a0, b0, a1, b1)
    masks: tuple[Mask2D, ...]

    def footprint_signed(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Signed distance to (window ∩ ¬masks): negative inside the canvas."""
        a0, b0, a1, b1 = self.window
        qa = np.maximum(a0 - a, a - a1)
        qb = np.maximum(b0 - b, b - b1)
        outside = np.hypot(np.maximum(qa, 0.0), np.maximum(qb, 0.0))
        inside = np.minimum(np.maximum(qa, qb), 0.0)
        g = outside + inside
        for m in self.masks:
            g = np.maximum(g, -m.signed(a, b))
        return g

    def contains_world(self, P: np.ndarray, above: float = 0.25) -> np.ndarray:
        """True for world points inside the canvas footprint AND at/above
        the panel surface (local n <= above)."""
        a, b, n = self.frame.to_local(P)
        return (self.footprint_signed(a, b) < 0.0) & (n <= above)


def _smoothstep(x: np.ndarray) -> np.ndarray:
    t = np.clip(x, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@dataclass(frozen=True)
class CanvasPad:
    """The additive "grown shell" prism over the canvas: thickness
    ``base_inflation`` deep inside, falling off to ZERO toward the window
    rim and every mask edge — bolt seats, keepouts and other interfaces
    never inflate. Rooted ``root_depth`` into the body so the weld union
    is seamless. Not a Euclidean SDF (the top follows a heightfield), but
    Lipschitz-bounded and exact at the zero level — all marching cubes
    needs."""

    canvas: CanvasRegion
    thickness: float
    falloff: float
    root_depth: float = 1.0

    def sdf(self, P: np.ndarray) -> np.ndarray:
        a, b, n = self.canvas.frame.to_local(P)
        g = self.canvas.footprint_signed(a, b)
        t = self.thickness * _smoothstep(-g / max(self.falloff, 1e-9))
        # pad occupies n in [-t(a,b), root_depth]  (n runs INTO the material)
        return np.maximum(g, np.maximum(n - self.root_depth, -n - t))

    def bounds(self) -> tuple[Vec3, Vec3]:
        a0, b0, a1, b1 = self.canvas.window
        corners = [
            self.canvas.frame.to_world(a, b, n)
            for a in (a0, a1)
            for b in (b0, b1)
            for n in (-self.thickness, self.root_depth)
        ]
        return (
            tuple(min(c[i] for c in corners) for i in range(3)),
            tuple(max(c[i] for c in corners) for i in range(3)),
        )


@dataclass(frozen=True)
class Blob:
    """A shell sphere: a grown boss around a fastener column, or one
    asymmetry-noise blob."""

    center: Vec3
    r: float

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_sphere(P, self.center, self.r)

    def bounds(self) -> tuple[Vec3, Vec3]:
        c, r = self.center, self.r
        return (c[0] - r, c[1] - r, c[2] - r), (c[0] + r, c[1] + r, c[2] + r)


# ---------------------------------------------------------------------------
# skin terms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Capsule:
    a: Vec3
    b: Vec3
    r: float

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_capsule(P, self.a, self.b, self.r)

    def bounds(self) -> tuple[Vec3, Vec3]:
        return (
            tuple(min(self.a[i], self.b[i]) - self.r for i in range(3)),
            tuple(max(self.a[i], self.b[i]) + self.r for i in range(3)),
        )


Sphere = Blob  # node blend spheres share the shell blob shape


# ---------------------------------------------------------------------------
# subtractive terms
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowPrism:
    """An organic window cutter: polygon in the panel frame's (a, b),
    extruded along local n over [n0, n1]. Subtracted with ``k_lip`` lips."""

    poly: Poly2
    frame: Frame
    n0: float
    n1: float

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_prism_polygon(P, self.poly, self.frame, self.n0, self.n1)


@dataclass(frozen=True)
class CylinderCut:
    axis: str
    center: Vec3
    r: float
    lo: float
    hi: float

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_cylinder_axis(P, self.axis, self.center, self.r, self.lo, self.hi)


@dataclass(frozen=True)
class FrustumCutZ:
    cx: float
    cy: float
    z0: float
    z1: float
    r0: float
    r1: float

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_frustum_z(P, self.cx, self.cy, self.z0, self.z1, self.r0, self.r1)


@dataclass(frozen=True)
class BoxCut:
    lo: Vec3
    hi: Vec3

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_box(P, self.lo, self.hi)


@dataclass(frozen=True)
class PrismCut:
    """A crisp (non-organic) field cell cutter — hex/voronoi/slot polygons
    stay engineering-exact, only organic windows get lips."""

    poly: Poly2
    frame: Frame
    n0: float
    n1: float

    def sdf(self, P: np.ndarray) -> np.ndarray:
        return sd_prism_polygon(P, self.poly, self.frame, self.n0, self.n1)


@dataclass(frozen=True)
class KeepInHalfSpace:
    """keep_in clip: material only where (P - point) . normal <= 0."""

    point: Vec3
    normal: Vec3

    def sdf(self, P: np.ndarray) -> np.ndarray:
        n = np.asarray(self.normal, dtype=np.float64)
        n = n / max(float(np.linalg.norm(n)), 1e-12)
        return (P - np.asarray(self.point, dtype=np.float64)) @ n


# ---------------------------------------------------------------------------
# the recipe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImplicitRecipe:
    body: tuple[object, ...]
    shell: tuple[object, ...] = ()
    skin_capsules: tuple[Capsule, ...] = ()
    skin_spheres: tuple[Sphere, ...] = ()
    window_prisms: tuple[WindowPrism, ...] = ()
    hard_cuts: tuple[object, ...] = ()
    keep_in: tuple[object, ...] = ()
    k_blend: float = 2.0
    k_weld: float = 3.0
    k_lip: float = 1.5
    #: the skin canvas — carried for the rectangularity metric and the
    #: clearance sampling; None when the form grew no shell/skin canvas.
    canvas: CanvasRegion | None = None

    # -- stage evaluators (the sabotage tests reorder THESE) -----------------

    def body_sdf(self, P: np.ndarray) -> np.ndarray:
        d = self.body[0].sdf(P)
        for term in self.body[1:]:
            d = np.minimum(d, term.sdf(P))
        return d

    def shell_sdf(self, P: np.ndarray) -> np.ndarray | None:
        if not self.shell:
            return None
        d = self.shell[0].sdf(P)
        for term in self.shell[1:]:
            d = smin(d, term.sdf(P), self.k_blend)
        return d

    def skin_sdf(self, P: np.ndarray) -> np.ndarray | None:
        terms = list(self.skin_capsules) + list(self.skin_spheres)
        if not terms:
            return None
        d = terms[0].sdf(P)
        for term in terms[1:]:
            d = smin(d, term.sdf(P), self.k_blend)
        return d

    def apply_window_lips(self, d: np.ndarray, P: np.ndarray) -> np.ndarray:
        for w in self.window_prisms:
            d = smax(d, -w.sdf(P), self.k_lip)
        return d

    def apply_hard_cuts(self, d: np.ndarray, P: np.ndarray) -> np.ndarray:
        for c in self.hard_cuts:
            d = np.maximum(d, -c.sdf(P))
        return d

    def apply_keep_in(self, d: np.ndarray, P: np.ndarray) -> np.ndarray:
        for k in self.keep_in:
            d = np.maximum(d, k.sdf(P))
        return d

    # -- THE LAW --------------------------------------------------------------

    def evaluate(self, P: np.ndarray) -> np.ndarray:
        """body → shell → skin → window lips → hard cuts LAST → keep_in.
        See the module docstring: this order is the contract the fidelity
        probes verify — hard cuts after every blob means no organic layer
        can ever narrow a fastener hole."""
        P = np.ascontiguousarray(P, dtype=np.float64)
        d = self.body_sdf(P)
        shell = self.shell_sdf(P)
        if shell is not None:
            d = smin(d, shell, self.k_weld)
        skin = self.skin_sdf(P)
        if skin is not None:
            d = smin(d, skin, self.k_weld)
        d = self.apply_window_lips(d, P)
        d = self.apply_hard_cuts(d, P)
        d = self.apply_keep_in(d, P)
        return d

    def bounds(self) -> tuple[Vec3, Vec3]:
        """AABB of every ADDITIVE term (cuts never extend the domain), plus
        the smooth-union bulge margin: smin can push material up to ~k/4
        beyond the union of the raw terms — without this margin the mesh is
        clipped by the grid wall (open boundary = non-manifold edges; seen
        on the clamp belly at exactly the grid floor plane)."""
        los: list[Vec3] = []
        his: list[Vec3] = []
        for term in (*self.body, *self.shell, *self.skin_capsules, *self.skin_spheres):
            lo, hi = term.bounds()
            los.append(lo)
            his.append(hi)
        bulge = max(self.k_blend, self.k_weld, self.k_lip, 0.0) / 4.0 + 0.5
        lo = tuple(min(p[i] for p in los) - bulge for i in range(3))
        hi = tuple(max(p[i] for p in his) + bulge for i in range(3))
        return lo, hi
