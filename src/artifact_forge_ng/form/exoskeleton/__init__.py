"""Exoskeleton IR (Bio-2) — the checkable skeleton intent, no CAD.

Pipeline: masks (semantic keepouts, stricter than the global modifier set)
-> substrate (jittered samples, anchors, load seeds) -> graph (Gabriel,
seeded, mask-pruned, connectivity-repaired) -> ribs (root-to-tip taper)
-> windows (node-Voronoi organic cells) -> debug dumps. Everything is
stdlib-only and deterministic; Bio-3 materializes the IR in CAD.

Keep this __init__ import-light: form/part.py imports :mod:`.ir` at module
level for its optional ``exoskeleton`` field, and the heavier siblings
(masks/substrate/...) import form/part themselves — pulling them in here
would create the cycle the layering avoids.
"""

from .ir import ExoskeletonIR, LoadPathIR, RibGraph

__all__ = ["ExoskeletonIR", "LoadPathIR", "RibGraph"]
