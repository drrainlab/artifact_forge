"""Interface layer (wave A1) — typed connection ports.

An INTERFACE is a declared, typed, gendered connection point on an
archetype: the formalization of what the Cassette Interface Standard and
the cuff payload seat already were implicitly (datums + frame keys +
shared params + a joint that measures the fit in the pose).

Layering:

* the TYPE registry (here) says what kinds of connections exist, which
  joints realize them and which frame keys each side must publish;
* the archetype's ``interfaces:`` block (InterfaceSpec) declares concrete
  ports — id, type, gender, datum anchor, clearance, target region,
  protected keepouts, accepts-filter, assembly role;
* legality of a mate = same type + complementary gender + accepts both
  ways + a joint the type recognizes. DEPTH stays in the joint IR checks
  (they measure real dimensional chains in the pose) — the interface
  layer never duplicates the measurement, it makes the connection
  DECLARED, discoverable (``forge compat``) and swappable.

The registry grows a field only when a consumer reads it — the region
role law applied to interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..core.values import parse_quantity

Gender = Literal["male", "female", "neutral"]

#: Axis tokens — port frames are AXIS-ALIGNED by design, matching the
#: quarter-turn pose philosophy: deterministic, composable, no arbitrary
#: vectors until a real client needs them.
AXIS_VECTORS: dict[str, tuple[int, int, int]] = {
    "+X": (1, 0, 0), "-X": (-1, 0, 0),
    "+Y": (0, 1, 0), "-Y": (0, -1, 0),
    "+Z": (0, 0, 1), "-Z": (0, 0, -1),
}


class FrameSpec(BaseModel):
    """Orientation of a port (A1.5): origin is the datum; ``normal`` points
    OUT of the part through the connection; ``up`` disambiguates rotation
    about the normal; optional ``axis`` is the slide/flow direction.
    Orthonormality is loader-fail-fast AND re-reported by the
    interface.frame_orthonormal check (honesty: the report shows the triad
    that was actually used)."""

    model_config = ConfigDict(extra="forbid")

    normal: str
    up: str
    axis: str | None = None

    @field_validator("normal", "up", "axis")
    @classmethod
    def _token(cls, v: str | None) -> str | None:
        if v is not None and v not in AXIS_VECTORS:
            raise ValueError(
                f"frame direction {v!r} not an axis token "
                f"({sorted(AXIS_VECTORS)})")
        return v

    @model_validator(mode="after")
    def _orthonormal(self) -> "FrameSpec":
        n, u = AXIS_VECTORS[self.normal], AXIS_VECTORS[self.up]
        if abs(sum(a * b for a, b in zip(n, u))) > 0:
            raise ValueError(
                f"frame normal {self.normal} and up {self.up} are not "
                "orthogonal")
        # axis is free by type semantics: slide axes lie in the port plane
        # (dovetail), flow axes ride the normal (fluid) — the TYPE's checks
        # judge it, the frame only guarantees it is a legal token.
        return self

    def vectors(self) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return AXIS_VECTORS[self.normal], AXIS_VECTORS[self.up]


@dataclass(frozen=True)
class InterfaceTypeDecl:
    """One entry of the interface-type vocabulary."""

    name: str
    description: str
    #: Joint types (assembly/joints.py registry) that realize this
    #: interface in an assembly. Empty = not yet joinable (declared ahead
    #: of its joint — an honest engine gap, the modifier pattern).
    joints: tuple[str, ...]
    #: Genders a port of this type may declare.
    genders: tuple[str, ...] = ("male", "female")
    #: Frame keys the built form must publish for interface.frame_exists
    #: (per gender; "*" applies to both).
    frame_keys: dict[str, tuple[str, ...]] | None = None
    #: Sane clearance band (mm) for interface.clearance_ok.
    clearance_band: tuple[float, float] = (0.0, 2.0)
    #: True when the connection is a fastened one — interface.
    #: fastener_access_ok applies.
    fastened: bool = False
    #: True when rotation about the normal MATTERS (flow direction, line
    #: continuity) — mate_frames_opposed then demands up-agreement, not
    #: just opposed normals. Symmetric fits (snap pairs, dovetail feet)
    #: stay insensitive.
    orientation_sensitive: bool = False

    def keys_for(self, gender: str) -> tuple[str, ...]:
        if not self.frame_keys:
            return ()
        return self.frame_keys.get(gender, ()) + self.frame_keys.get("*", ())


def _decl(name: str, description: str, joints: tuple[str, ...], **kw: Any
          ) -> tuple[str, InterfaceTypeDecl]:
    return name, InterfaceTypeDecl(name, description, joints, **kw)


#: The A1 vocabulary. Types whose joints tuple is empty are declared ahead
#: of their joint (fluid line fittings land with their adapters).
INTERFACE_TYPES: dict[str, InterfaceTypeDecl] = dict([
    _decl("screw_pattern",
          "bolt circle / hole pattern fastened with screws",
          ("screw_joint",), fastened=True,
          frame_keys={"*": ("mount_bc", "mount_bc_n")}),
    _decl("heatset_insert_pattern",
          "screw pattern landing in heatset inserts (female carries brass)",
          ("screw_joint",), fastened=True),
    _decl("strap_slot_pair",
          "webbing strap closure through a slot pair (soft counterpart)",
          (), genders=("neutral",)),
    _decl("cylindrical_payload_socket",
          "cylinder seat with arc retention (flashlight / prop / tool)",
          ("snap_joint",),
          frame_keys={"female": ("payload_r_inner", "payload_mouth_gap")}),
    _decl("dovetail_rail",
          "trapezoid slide interface: male ridge in a female groove",
          ("dovetail_joint",),
          frame_keys={
              "male": ("dovetail_top_w", "dovetail_root_w", "dovetail_h"),
              "female": ("groove_top_w", "groove_bottom_w", "groove_depth"),
          },
          clearance_band=(0.1, 0.8)),
    _decl("snap_joint",
          "hook-and-window snap closure",
          ("snap_joint",)),
    _decl("tongue_groove",
          "line alignment tongue/groove (aligns, never carries, never seals)",
          ("tongue_groove",), clearance_band=(0.1, 1.0),
          orientation_sensitive=True),
    _decl("removable_insert",
          "tool-free drop-in seat with a graspable rim (cassette standard)",
          ("removable_insert",),
          frame_keys={
              "female": ("seat_u0", "seat_v0", "seat_u1", "seat_v1"),
              "male": ("cassette_u0", "cassette_v0", "cassette_u1",
                       "cassette_v1", "cassette_h"),
          },
          clearance_band=(0.3, 1.5)),
    _decl("fluid_inlet",
          "water/nutrient line entry (receives — female side): a drip "
          "target or a flush lap receiver",
          ("fluid_joint", "lap_flow_joint"), orientation_sensitive=True),
    _decl("fluid_outlet",
          "water/nutrient line exit (hands out — male): a drip edge or a "
          "flush lap lip",
          ("fluid_joint", "lap_flow_joint"), orientation_sensitive=True),
    _decl("cable_pass",
          "cable/wire pass-through continuity point",
          (), genders=("neutral",)),
    _decl("hose_port",
          "push-in bore for external tubing (silicone hose) — mates "
          "HARDWARE, never a printed part; the tube lands in the BOM",
          (), genders=("neutral",)),
    _decl("profile_seat",
          "rail bottom groove seated on an aluminum profile carrier "
          "(male = the profile's support line, female = the groove)",
          ("profile_perch",), orientation_sensitive=True,
          clearance_band=(0.1, 0.5)),
])


class InterfaceSpec(BaseModel):
    """One declared port on an archetype (the A1 common contract)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    gender: Gender = "neutral"
    #: Frame anchor: a datum the builder publishes on the form. Verified
    #: by interface.frame_exists at validate time (datums are runtime).
    datum: str
    #: Nominal mating clearance (mm) this side is designed around.
    clearance: float | None = None
    #: Target region the interface occupies (loader-validated id).
    region: str | None = None
    #: Region ids no cut/modifier may touch while this port is to stay
    #: usable — interface.keepouts_preserved measures it.
    keepouts: list[str] = []
    #: Mate filter: archetype ids or object_class names this port accepts.
    #: Empty = accepts any compatible counterpart.
    accepts: list[str] = []
    #: required = an assembly containing this part must mate the port
    #: (assembly.no_orphan_ports); optional = free-standing use is fine.
    assembly_role: Literal["required", "optional"] = "optional"
    #: Port orientation (A1.5). Optional for one deprecation cycle —
    #: frame checks WARN on frameless ports; new ports must declare it.
    frame: FrameSpec | None = None

    @field_validator("clearance", mode="before")
    @classmethod
    def _parse_clearance(cls, v: Any) -> Any:
        if isinstance(v, str):
            return parse_quantity(v, "length", where="interface")
        return v

    @field_validator("type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in INTERFACE_TYPES:
            raise ValueError(
                f"unknown interface type {v!r}; known: {sorted(INTERFACE_TYPES)}"
            )
        return v

    def decl(self) -> InterfaceTypeDecl:
        return INTERFACE_TYPES[self.type]


#: Cross-type pairs that mate each other (directional connections where
#: the two ends are DIFFERENT types by nature).
COMPLEMENT_TYPES: dict[str, str] = {
    "fluid_outlet": "fluid_inlet",
    "fluid_inlet": "fluid_outlet",
}


def types_mate(a_type: str, b_type: str) -> bool:
    return a_type == b_type or COMPLEMENT_TYPES.get(a_type) == b_type


def mate_problems(
    a: InterfaceSpec, b: InterfaceSpec,
    a_part: tuple[str, str], b_part: tuple[str, str],
    joint_type: str | None = None,
) -> list[str]:
    """Legality of a mate between two declared ports — the pure rule set
    shared by assembly validation and ``forge compat``. ``*_part`` is
    (archetype_id, object_class) of each side. Returns [] when legal."""
    problems: list[str] = []
    if not types_mate(a.type, b.type):
        problems.append(f"types differ: {a.type} vs {b.type}")
        return problems
    decl = a.decl()
    pair = {a.gender, b.gender}
    if pair == {"neutral"}:
        pass
    elif pair == {"male", "female"}:
        pass
    else:
        problems.append(
            f"genders do not complement: {a.gender} vs {b.gender}")
    for spec, (peer_id, peer_class), side in (
        (a, b_part, "a"), (b, a_part, "b"),
    ):
        if spec.accepts and peer_id not in spec.accepts \
                and peer_class not in spec.accepts:
            problems.append(
                f"{side}:{spec.id} accepts {spec.accepts}, got "
                f"{peer_id} ({peer_class})")
    if joint_type is not None:
        if not decl.joints:
            problems.append(
                f"interface type {a.type!r} has no realizing joint yet "
                "(declared ahead of its joint)")
        elif joint_type not in decl.joints:
            problems.append(
                f"joint {joint_type!r} does not realize interface type "
                f"{a.type!r} (expects one of {list(decl.joints)})")
    if a.clearance is not None and b.clearance is not None:
        if abs(a.clearance - b.clearance) > 0.5:
            problems.append(
                f"declared clearances disagree: {a.clearance:g} vs "
                f"{b.clearance:g} (same fit, two numbers)")
    return problems
