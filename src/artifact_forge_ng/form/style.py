"""Surface styles — the named radius vocabulary of a form family.

``molded_utility_part`` is the flagship's family: large root blends,
rounded contact edges, softened externals, no random organic blobs. The
molded pass (:mod:`.molded`) picks a corner radius by the tags of the
segments meeting at each joint; first match wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SurfaceStyle:
    name: str
    external_edge_r: float = 1.8
    root_blend_r: float = 5.5
    contact_r: float = 2.0
    lip_tip_r: float = 1.5
    #: Ordered (tag, radius-attr) rules for corner rounding.
    corner_rules: tuple[tuple[str, str], ...] = field(
        default=(
            ("lip_tip", "lip_tip_r"),
            ("mouth_corner", "contact_r"),
            ("root", "root_blend_r"),
            ("external", "external_edge_r"),
        )
    )

    def corner_radius(self, tags: frozenset[str]) -> float:
        for tag, attr in self.corner_rules:
            if tag in tags:
                return float(getattr(self, attr))
        return self.external_edge_r


MOLDED_UTILITY_PART = SurfaceStyle(name="molded_utility_part")

STYLES: dict[str, SurfaceStyle] = {s.name: s for s in (MOLDED_UTILITY_PART,)}
