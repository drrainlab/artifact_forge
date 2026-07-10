"""Shared constants of the vertical-farm water ops (Cassette Interface
Standard tolerances and water-path bands)."""
from __future__ import annotations

#: Material the deepest channel point must keep beneath it.
FLOOR_MARGIN_MIN = 2.0
#: Corridor over the channel through the seat walls — brush-open by design.
CORRIDOR_MARGIN = 2.0
#: How far above the channel floor the FEED datum sits: the inlet cap's
#: drip tower releases the stream this far above the first rail's floor.
#: This is the ONLY place a fall survives after the VF correction — rails
#: hand water to each other flush, over lap lips, with no step at all.
FALL_ENTRY = 2.5
#: VF-9.2: the cap's drip point sits this far INBOARD of the rail face — safely
#: inside the channel run, not at its very edge. PAIRED between the rail's
#: `feed` datum and the cap's `spout` datum (both inset equally), so the row
#: pose is unchanged while the datums honestly mark the real drip point.
DRIP_INSET = 4.5
#: VF-9.2: the drip orifice below the cap's tube-stop shoulder is this long.
ORIFICE_LEN = 4.0
#: VF-9.2: the covered chamber under the cap's socket may be at most this long
#: in Y — a small drop shaft, never a closed horizontal water tunnel.
CAP_COVERED_RUN_MAX = 10.0


