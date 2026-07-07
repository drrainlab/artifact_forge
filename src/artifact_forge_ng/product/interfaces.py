"""Interface layer (wave A1, docs/ROADMAP.md) — typed connection ports.

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

from pydantic import BaseModel, ConfigDict, field_validator

from ..core.values import parse_quantity

Gender = Literal["male", "female", "neutral"]


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

    def keys_for(self, gender: str) -> tuple[str, ...]:
        if not self.frame_keys:
            return ()
        return self.frame_keys.get(gender, ()) + self.frame_keys.get("*", ())


def _decl(name: str, description: str, joints: tuple[str, ...], **kw: Any
          ) -> tuple[str, InterfaceTypeDecl]:
    return name, InterfaceTypeDecl(name, description, joints, **kw)


#: The A1 vocabulary. Types whose joints tuple is empty are declared ahead
#: of their joint (fluid line fittings land with the VF-3 adapters).
INTERFACE_TYPES: dict[str, InterfaceTypeDecl] = dict([
    _decl("screw_pattern",
          "bolt circle / hole pattern fastened with screws",
          ("screw_joint",), fastened=True,
          frame_keys={"*": ("mount_bc_r", "mount_bc_n")}),
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
          ("tongue_groove",), clearance_band=(0.1, 1.0)),
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
          "water/nutrient line entry (VF-3 adapters land the joint)",
          ()),
    _decl("fluid_outlet",
          "water/nutrient line exit / drip edge handover",
          ()),
    _decl("cable_pass",
          "cable/wire pass-through continuity point",
          (), genders=("neutral",)),
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


def mate_problems(
    a: InterfaceSpec, b: InterfaceSpec,
    a_part: tuple[str, str], b_part: tuple[str, str],
    joint_type: str | None = None,
) -> list[str]:
    """Legality of a mate between two declared ports — the pure rule set
    shared by assembly validation and ``forge compat``. ``*_part`` is
    (archetype_id, object_class) of each side. Returns [] when legal."""
    problems: list[str] = []
    if a.type != b.type:
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
